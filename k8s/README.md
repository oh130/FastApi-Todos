# 쿠버네티스 실습 (로컬)

docker-compose로 돌리던 FastAPI 앱을 로컬 쿠버네티스(Docker Desktop 내장, kind 모드)에 올려 보는 실습이다.
운영 배포용이 아니라, compose에서 하던 설정이 쿠버네티스에서 어떻게 표현되는지 확인하는 것이 목적이다.

> v9.0.0부터 데이터를 파일(`todo.json`)이 아니라 PostgreSQL에 저장한다. **실험 1~6은 파일 저장 방식(v8.0.0)에서 한 기록**이고,
> 그 실험에서 드러난 한계를 DB로 해결한 결과는 [실험 7](#7-db로-바꾸면-복제본을-늘려도-유실이-없다)에 있다.

## compose 설정과의 대응

| compose (`docker-compose.yml`, `Dockerfile`) | 쿠버네티스 (`fastapi-todo.yaml`) |
| --- | --- |
| `restart: unless-stopped` | Deployment가 파드 수를 유지 (죽으면 새로 띄움) |
| `ports: "5017:8000"` | Service (+ `kubectl port-forward`) |
| `mem_limit: 128m`, `cpus: 0.5` | `resources.limits` (memory 128Mi, cpu 500m) |
| named volume (예: `postgres-data`) | StatefulSet의 `volumeClaimTemplates` (PVC `data-postgres-0`) |
| `POSTGRES_PASSWORD`(`.env`) | Secret `todo-db` (yaml에 적지 않고 명령으로 생성) |
| `depends_on: condition: service_healthy` | readinessProbe + 앱 시작 시 DB 연결 재시도 |
| (없음) | `readinessProbe`, `livenessProbe` |
| `no-new-privileges`, `cap_drop: ALL`, non-root 유저 | `securityContext` |

## 준비

Docker Desktop의 Settings > Kubernetes에서 Enable. 클러스터가 뜨면:

```bash
docker build -t fastapi-todo:db ./fastapi-app
kubectl create secret generic todo-db --from-literal=POSTGRES_PASSWORD='원하는비밀번호'   # DB 비밀번호는 yaml에 적지 않는다
kubectl apply -f k8s/fastapi-todo.yaml
kubectl get pods,pvc
kubectl port-forward svc/fastapi-todo 8000:8000   # 브라우저에서 http://localhost:8000
```

이 클러스터는 kind 모드라 NodePort로 `localhost`에 바로 접속되지 않아서 `port-forward`를 쓴다.
로컬에서 빌드한 이미지는 같은 Docker Desktop 클러스터에서 그대로 쓸 수 있었다.

주의: 같은 태그(`:local`)로 이미지를 다시 빌드해서 `apply`하면 노드에 캐시된 옛 이미지가 계속 쓰인다.
실제로 코드를 고쳤는데도 파드가 옛 코드로 도는 것을 겪었다(`kubectl get pod -o jsonpath='{..imageID}'`로 이미지 해시를 비교해서 확인).
코드를 바꿀 때마다 태그를 바꾸고(`fastapi-todo:db` 등) yaml의 `image:`도 같이 바꾼다.

HPA와 부하테스트(실험 8)를 하려면 CPU 사용량을 읽는 metrics-server와 JMeter 이미지가 더 필요하다.

```bash
# metrics-server 설치. kind 모드 클러스터는 kubelet 인증서를 검증하지 못해서 --kubelet-insecure-tls가 필요하다 (실습용)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.7.2/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl top pods   # CPU/메모리가 보이면 준비 끝

docker build -t jmeter-todo:local ./jmeter
kubectl create configmap jmeter-plan --from-file=jmeter/fastapi_test_plan.jmx
```

## 실험과 결과

아래는 실제로 실행해서 확인한 결과다. 실험 1~6은 파일 저장 방식, 실험 7은 DB 방식이다.

### 1. 파드를 지우면 자동으로 복구된다

```bash
kubectl delete pod -l app=fastapi-todo
kubectl get pods
```

새 파드가 몇 초 안에 `Running`이 된다. 볼륨을 붙이기 전(컨테이너 안의 `todo.json`을 쓰던 때)에는 새 파드의 데이터가 이미지에 들어 있던 초기 상태로 돌아갔다. 실험 5에서 이 문제를 해결한다.

### 2. 복제본을 2개로 늘리면 데이터가 갈라진다 (볼륨 없이)

```bash
kubectl scale deployment fastapi-todo --replicas=2
# 클러스터 안에서 Service 주소로 POST 6번 후 GET을 반복
kubectl run tester --rm -i --restart=Never --image=curlimages/curl -- sh -c '...'
```

GET할 때마다 todo 개수가 5건, 3건으로 다르게 나왔다. 요청이 두 파드에 나뉘어 들어가고, 파드마다 자기 `todo.json`을 따로 갖기 때문이다.
`main.py`의 락(`threading.Lock`)도 프로세스 안에서만 유효해서 파드 사이의 동시성은 막지 못한다.
상태를 가진 앱은 복제본을 그냥 늘릴 수 없고, DB나 공유 볼륨 같은 외부 저장소로 빼야 한다는 것을 확인했다.

```bash
kubectl scale deployment fastapi-todo --replicas=1   # 원복
```

### 3. 메모리 한도를 넘으면 OOMKilled

```bash
kubectl set resources deployment/fastapi-todo --requests=memory=16Mi --limits=memory=20Mi
kubectl describe pod <새 파드>   # Last State: Terminated, Reason: OOMKilled, Exit Code: 137
```

새 파드는 `CrashLoopBackOff`가 되었다. 이때 기존 파드는 계속 `Running`이라 서비스가 끊기지 않았다.
(롤링 업데이트는 새 파드가 Ready가 되기 전에는 기존 파드를 내리지 않는다.)
`requests`가 `limits`보다 크면 설정 자체가 거부되므로 둘을 같이 낮춰야 한다.

```bash
kubectl apply -f k8s/fastapi-todo.yaml   # 원복
```

### 4. 롤링 업데이트와 롤백

```bash
docker tag fastapi-todo:local fastapi-todo:v2
kubectl set image deployment/fastapi-todo fastapi-app=fastapi-todo:v2
kubectl rollout status deployment/fastapi-todo
kubectl rollout history deployment/fastapi-todo
kubectl rollout undo deployment/fastapi-todo
```

리비전이 1, 2로 기록되고, `undo`로 이전 이미지로 되돌아갔다.

### 5. PVC로 데이터를 파드 밖에 두면 파드를 지워도 남는다

`main.py`가 저장 파일 경로를 환경변수 `TODO_FILE`로 받도록 고쳤다(기본값은 기존과 같은 앱 폴더의 `todo.json`이라 compose 배포는 그대로).
yaml에서는 PVC(`todo-data`, 1Gi)를 만들어 `/data`에 마운트하고 `TODO_FILE=/data/todo.json`으로 지정했다.
앱이 non-root(uid 10001)로 돌기 때문에 새 볼륨(root 소유)에 쓰려면 `fsGroup: 10001`이 필요하다.

```bash
# 할 일을 추가한 뒤
kubectl delete pod -l app=fastapi-todo
# 새 파드에서 다시 조회하면 추가한 할 일이 그대로 남아 있다
```

파드를 지우기 전에 추가한 `persist-1`, `persist-2`가 새 파드에서도 조회되었다.

### 6. 볼륨을 공유해도 복제본을 늘릴 수는 없다

PVC를 붙인 상태에서 복제본을 2개로 늘리고 동시에 POST 40번을 보냈다.
GET 결과는 매번 29건으로 같았다(실험 2처럼 갈라지지는 않는다). 하지만 기대한 42건에 못 미쳤다. 13건이 사라진 것이다.
두 파드가 같은 파일을 읽고-수정하고-쓰는데, `main.py`의 락(`threading.Lock`)은 한 프로세스 안에서만 유효해서 파드 사이의 동시 쓰기를 막지 못한다(마지막에 쓴 쪽이 이긴다).
파일 저장 방식은 복제본 1개를 전제로 한 구조이고, 복제본을 늘리려면 DB처럼 동시성을 처리해 주는 저장소가 필요하다.

```bash
kubectl scale deployment fastapi-todo --replicas=1   # 원복
```

### 7. DB로 바꾸면 복제본을 늘려도 유실이 없다

실험 6의 한계(복제본이 같은 파일을 덮어써서 동시 쓰기가 유실됨)를 없애려고 저장소를 PostgreSQL로 바꿨다.
Postgres는 StatefulSet(`postgres-0`, PVC 1Gi)으로 두고, 앱은 복제본 2개로 올렸다. 비밀번호는 Secret(`todo-db`)으로 넘긴다.
같은 시험(`fastapi-app/tests_deploy/test_concurrency_live.py`: 동시 등록 40건을 두 복제본에 번갈아 보내고, 등록한 id가 전부 조회되는지 확인)을 전/후로 돌렸다.
복제본마다 `kubectl port-forward`로 따로 접속해서 요청을 두 곳에 나눠 보냈다.

| | 저장소 | 복제본 | 결과 |
| --- | --- | --- | --- |
| 전 (v8.0.0) | `todo.json`, PVC 공유 | 2 | 동시 등록 중 **500 오류**로 시험 실패 (2회 모두) |
| 후 (v9.0.0) | PostgreSQL | 2 | **3회 모두 통과** (40건 전부 저장, id 중복 없음, 어느 복제본으로 읽어도 보임) |

- 한 복제본에서 등록한 항목이 다른 복제본에서 바로 조회된다 (둘 다 같은 DB를 본다).
- `postgres-0` 파드를 지우면 StatefulSet이 같은 이름으로 다시 띄우고 같은 PVC를 붙여서, 등록해 둔 데이터가 그대로 남았다.
- 앱은 파일을 쓰지 않아서 `readOnlyRootFilesystem: true`로 루트 파일시스템을 잠가도 정상 동작했다.
- 앱의 동시성 처리는 `threading.Lock`(한 프로세스 안에서만 유효)에서 DB로 옮겨 갔다. id는 DB 시퀀스가 발급하고,
  항목 수정은 행 잠금(`SELECT ... FOR UPDATE`)으로 읽어서 같은 항목을 동시에 완료로 바꿔도 완료 지표를 한 번만 센다.

```bash
# 복제본 두 곳에 번갈아 보내기
kubectl port-forward pod/<앱 파드 1> 18001:8000 &
kubectl port-forward pod/<앱 파드 2> 18002:8000 &
cd fastapi-app
API_BASE_URLS=http://localhost:18001,http://localhost:18002 pytest tests_deploy/test_concurrency_live.py
```

### 8. HPA로 부하에 따라 복제본이 자동으로 늘고 준다

저장소가 DB가 되어 복제본을 늘려도 되는 구조가 됐으니, 부하에 따라 복제본 수를 자동으로 조절하는 HPA(`hpa.yaml`)를 붙였다.
CPU 사용률이 requests(100m)의 60%를 넘으면 늘리고(최소 2, 최대 6), 부하가 사라지면 1분(안정화 창) 뒤에 줄인다.
같은 JMeter 시험(`jmeter-job.yaml`: 동시 사용자 50명, 20초에 걸쳐 증가, 150초 유지)을 클러스터 안에서 Service 주소로 보내 HPA 없이/있이 비교했다.
시험 중에는 15초마다 복제본 수와 파드 CPU를 기록했다.

| | 복제본 | 처리량 | 평균 응답 | 95% 응답 | 최대 응답 | 오류 |
| --- | --- | --- | --- | --- | --- | --- |
| HPA 없음 (고정) | 2 | 154.3건/초 | 302ms | 504ms | 1098ms | 0건 |
| HPA (2~6) | 2 → 6 → 2 | 234.3건/초 | 199ms | 458ms | 1202ms | 0건 |

- 고정 2개일 때는 두 파드가 모두 CPU 한도(500m)에 붙어 포화되었다 (파드 CPU 약 500m 유지, 메모리는 80Mi 안팎으로 안정적).
- HPA는 부하가 시작되고 약 45초 안에 복제본을 2개에서 6개(최대)로 늘렸고, 부하가 끝나자 1분쯤 뒤 2개로 줄였다 (`SuccessfulRescale` 이벤트로 확인).
- 처리량은 약 52% 늘고 평균 응답은 34% 줄었다. 95% 응답은 504ms에서 458ms로 조금만 줄었다.
  파드를 늘려도 한 대의 로컬 노드 CPU를 JMeter와 Postgres가 같이 쓰기 때문에, 복제본 수만큼 선형으로 빨라지지는 않는다고 본다 (최대 6개에 도달해 있었으므로 상한을 올려도 이 환경에서는 한계가 있을 것이다).
- 복제본이 늘어나는 동안에도 오류는 0건이었다. 새 파드는 readinessProbe(`/todos`, DB 조회 포함)를 통과한 뒤에야 Service에서 요청을 받는다.
- 앱 파드 하나가 쓰는 DB 연결은 연결 풀 기본값(기본 5개, 초과 시 최대 10개 더)이라, 6개로 늘면 최대 90개까지 쓸 수 있다. PostgreSQL 기본 최대 연결(100)에 가까워서 복제본 상한을 더 올리려면 풀 크기나 PgBouncer를 함께 봐야 한다.

```bash
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/jmeter-job.yaml
kubectl get hpa fastapi-todo -w        # 다른 터미널에서 복제본 수 관찰
kubectl logs -f job/jmeter-load        # 마지막 RESULT 줄에 요청 수/오류/응답시간 집계
```

## 아직 해보지 않은 것

- 학교 서버(k3s)에 올리기. 로컬 클러스터에서만 실습했다.
- InfluxDB/Grafana에 클러스터 부하테스트 결과를 보내서 대시보드로 보기 (지금은 Job 로그의 집계로만 확인).
- DB 연결 풀 크기와 PgBouncer 조정, Postgres 자체의 병목 확인.
- 학교 서버(k3s)에는 올리지 않았다. 로컬 클러스터에서만 실습했다.
