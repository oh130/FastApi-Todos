import os
from concurrent.futures import ThreadPoolExecutor

import httpx2

# 복제본(앱 컨테이너/파드)이 여러 개일 때는 API_BASE_URLS에 쉼표로 여러 주소를 주면, 요청을 번갈아 보낸다.
# 파일 저장 방식에서는 복제본끼리 같은 파일을 덮어써서 동시 등록이 유실됐던 문제(k8s 실험 6)를 DB로 해결했는지 확인하는 용도다.
BASE_URLS = [
    url.strip()
    for url in os.environ.get(
        "API_BASE_URLS", os.environ.get("API_BASE_URL", "http://163.239.77.78:5017")
    ).split(",")
]
REQUEST_COUNT = 40


def _create(index: int) -> dict:
    with httpx2.Client(base_url=BASE_URLS[index % len(BASE_URLS)], timeout=20) as client:
        response = client.post("/todos", json={"title": f"동시 등록 확인 {index}"})
        assert response.status_code == 201
        return response.json()


def test_concurrent_creates_are_not_lost_across_replicas():
    with ThreadPoolExecutor(max_workers=10) as pool:
        created = list(pool.map(_create, range(REQUEST_COUNT)))

    created_ids = {todo["id"] for todo in created}
    assert len(created_ids) == REQUEST_COUNT  # 발급된 id가 서로 겹치지 않는다

    try:
        # 어느 복제본으로 조회해도 방금 등록한 항목이 전부 보여야 한다 (유실 없음)
        for base_url in BASE_URLS:
            with httpx2.Client(base_url=base_url, timeout=20) as client:
                listed_ids = {todo["id"] for todo in client.get("/todos").json()}
            assert created_ids <= listed_ids, f"{base_url}: {len(created_ids - listed_ids)}건이 보이지 않는다"
    finally:
        with httpx2.Client(base_url=BASE_URLS[0], timeout=20) as client:
            for todo_id in created_ids:
                client.delete(f"/todos/{todo_id}")
