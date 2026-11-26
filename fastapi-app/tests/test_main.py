from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy import select

import main
from database import Base, SessionLocal, TodoRow, engine
from main import app

client = TestClient(app)


def _counter_value(name: str) -> float:
    return REGISTRY.get_sample_value(name) or 0.0


def _gauge_value(name: str, status: str) -> float:
    return REGISTRY.get_sample_value(name, {"status": status}) or 0.0


def _seed(*todos: dict) -> list[int]:
    """DB에 항목을 바로 넣고 DB가 발급한 id 목록을 돌려준다 (API를 거치지 않아 지표도 건드리지 않는다)."""
    with SessionLocal() as session:
        rows = [TodoRow(**todo) for todo in todos]
        session.add_all(rows)
        session.commit()
        return [row.id for row in rows]


def _all_rows() -> list[TodoRow]:
    with SessionLocal() as session:
        return list(session.scalars(select(TodoRow).order_by(TodoRow.id)))


@pytest.fixture(autouse=True)
def fresh_database():
    # 테스트마다 테이블을 지우고 다시 만들어서, id 번호도 1부터 새로 시작한다.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_get_todos_empty():
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == []


def test_get_todos_with_items():
    _seed({"title": "Test", "description": "Test description", "completed": False})
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Test"


def test_create_todo():
    todo = {"title": "Test", "description": "Test description", "completed": False}
    response = client.post("/todos", json=todo)
    assert response.status_code == 201
    assert response.json()["title"] == "Test"
    assert response.json()["id"] == 1
    assert len(_all_rows()) == 1


def test_create_todo_invalid():
    todo = {"description": "Test description"}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


def test_update_todo():
    (todo_id,) = _seed({"title": "Test", "description": "Test description", "completed": False})
    updated_todo = {"title": "Updated", "description": "Updated description", "completed": True}
    response = client.put(f"/todos/{todo_id}", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert _all_rows()[0].title == "Updated"  # 응답만이 아니라 DB에도 반영됐는지 확인


def test_update_todo_not_found():
    updated_todo = {"title": "Updated", "description": "Updated description", "completed": True}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 404


def test_delete_todo():
    (todo_id,) = _seed({"title": "Test", "description": "Test description", "completed": False})
    response = client.delete(f"/todos/{todo_id}")
    assert response.status_code == 204
    assert _all_rows() == []


def test_delete_todo_not_found():
    response = client.delete("/todos/1")
    assert response.status_code == 404


def test_delete_completed_todos():
    active_id, _ = _seed(
        {"title": "Active", "description": "", "completed": False},
        {"title": "Done", "description": "", "completed": True},
    )
    response = client.delete("/todos/completed")
    assert response.status_code == 204
    remaining = _all_rows()
    assert len(remaining) == 1
    assert remaining[0].id == active_id


def test_delete_completed_todos_when_none_completed():
    _seed({"title": "Active", "description": "", "completed": False})
    response = client.delete("/todos/completed")
    assert response.status_code == 204
    assert len(_all_rows()) == 1


def test_create_todo_description_too_long_is_rejected():
    todo = {"title": "Test", "description": "x" * 1001}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


def test_response_has_security_headers():
    response = client.get("/todos")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_create_todo_increments_created_counter():
    before = _counter_value("todo_created_total")
    client.post("/todos", json={"title": "Test"})
    assert _counter_value("todo_created_total") == before + 1


def test_completing_todo_increments_completed_counter():
    (todo_id,) = _seed({"title": "Test", "description": "", "completed": False})
    before = _counter_value("todo_completed_total")
    client.put(f"/todos/{todo_id}", json={"title": "Test", "completed": True})
    assert _counter_value("todo_completed_total") == before + 1


def test_uncompleted_update_does_not_increment_completed_counter():
    (todo_id,) = _seed({"title": "Test", "description": "", "completed": False})
    before = _counter_value("todo_completed_total")
    client.put(f"/todos/{todo_id}", json={"title": "Updated", "completed": False})
    assert _counter_value("todo_completed_total") == before


def test_delete_todo_increments_deleted_counter():
    (todo_id,) = _seed({"title": "Test", "description": "", "completed": False})
    before = _counter_value("todo_deleted_total")
    client.delete(f"/todos/{todo_id}")
    assert _counter_value("todo_deleted_total") == before + 1


def test_delete_completed_increments_deleted_counter_by_count():
    _seed(
        {"title": "A", "description": "", "completed": True},
        {"title": "B", "description": "", "completed": True},
        {"title": "C", "description": "", "completed": False},
    )
    before = _counter_value("todo_deleted_total")
    client.delete("/todos/completed")
    assert _counter_value("todo_deleted_total") == before + 2


def test_items_current_gauge_reflects_active_and_completed_counts():
    # 게이지는 DB를 직접 세서 맞추므로, 쓰기 요청 한 번이면 그 시점의 DB 상태가 반영된다.
    _seed(
        {"title": "A", "description": "", "completed": True},
        {"title": "B", "description": "", "completed": False},
    )
    client.post("/todos", json={"title": "C"})
    assert _gauge_value("todo_items_current", "completed") == 1
    assert _gauge_value("todo_items_current", "active") == 2


def test_ids_are_issued_by_database_and_not_reused_after_delete():
    first = client.post("/todos", json={"title": "first"}).json()["id"]
    client.delete(f"/todos/{first}")
    second = client.post("/todos", json={"title": "second"}).json()["id"]
    assert second != first  # DB 시퀀스는 지운 번호를 다시 쓰지 않는다 (예전 "최대값 + 1" 방식과 다른 점)


def test_concurrent_creates_are_all_stored_without_duplicate_ids():
    # JMeter 부하 테스트에서 동시 요청이 몰리면 저장 파일이 깨지던 문제의 회귀 테스트.
    # 이제 동시성은 앱의 락이 아니라 DB가 처리한다.
    request_count = 30
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(
            lambda i: client.post("/todos", json={"title": f"concurrent-{i}"}),
            range(request_count),
        ))

    assert all(response.status_code == 201 for response in responses)
    rows = _all_rows()
    assert len(rows) == request_count
    assert len({row.id for row in rows}) == request_count  # id 중복(lost update) 없음
    assert {response.json()["id"] for response in responses} == {row.id for row in rows}


@pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="행 잠금(SELECT ... FOR UPDATE)은 PostgreSQL에서만 동작한다. TEST_DATABASE_URL로 PostgreSQL을 지정하면 실행된다.",
)
def test_update_reads_latest_state_after_waiting_for_row_lock():
    # 수정 API는 항목 행을 잠그고(SELECT ... FOR UPDATE) 읽는다. 다른 트랜잭션이 그 항목을 "완료"로 바꾸는 중이면,
    # 수정 요청은 그 트랜잭션이 끝날 때까지 기다렸다가 이미 완료된 최신 상태를 읽고, 완료 지표를 올리지 않는다.
    # (잠금 없이 읽으면 아직 반영 전인 "미완료" 상태를 읽어서 같은 완료를 지표에 두 번 센다.)
    # 타이밍 운에 기대지 않으려고, 다른 트랜잭션이 변경을 쥐고 있는 동안 수정 요청이 멈춰 있는지부터 직접 확인한다.
    (todo_id,) = _seed({"title": "race", "description": "", "completed": False})
    before = _counter_value("todo_completed_total")

    with SessionLocal() as holder, ThreadPoolExecutor(max_workers=1) as pool:
        holder.get(TodoRow, todo_id, with_for_update=True).completed = True
        holder.flush()  # UPDATE를 보내서 행 잠금을 쥐고 있지만 아직 commit하지 않았다
        future = pool.submit(lambda: client.put(f"/todos/{todo_id}", json={"title": "race", "completed": True}))

        with pytest.raises(FutureTimeoutError):
            future.result(timeout=0.5)  # 잠금이 풀리기 전에는 수정 요청이 끝나지 않는다

        holder.commit()  # 완료 상태를 확정하고 잠금 해제
        assert future.result(timeout=10).status_code == 200

    assert _counter_value("todo_completed_total") == before  # 이미 완료된 항목이라 지표가 오르지 않는다
