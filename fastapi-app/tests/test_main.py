from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

import main
from main import app, save_todos, load_todos, TodoItem

client = TestClient(app)


def _counter_value(name: str) -> float:
    return REGISTRY.get_sample_value(name) or 0.0


def _gauge_value(name: str, status: str) -> float:
    return REGISTRY.get_sample_value(name, {"status": status}) or 0.0


@pytest.fixture(autouse=True)
def setup_todo_file(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "TODO_FILE", tmp_path / "todo.json")
    save_todos([])


def test_get_todos_empty():
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == []


def test_get_todos_with_items():
    todo = TodoItem(id=1, title="Test", description="Test description", completed=False)
    save_todos([todo])
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
    assert len(load_todos()) == 1


def test_create_todo_invalid():
    todo = {"description": "Test description"}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


def test_update_todo():
    todo = TodoItem(id=1, title="Test", description="Test description", completed=False)
    save_todos([todo])
    updated_todo = {"title": "Updated", "description": "Updated description", "completed": True}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


def test_update_todo_not_found():
    updated_todo = {"title": "Updated", "description": "Updated description", "completed": True}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 404


def test_delete_todo():
    todo = TodoItem(id=1, title="Test", description="Test description", completed=False)
    save_todos([todo])
    response = client.delete("/todos/1")
    assert response.status_code == 204
    assert load_todos() == []


def test_delete_todo_not_found():
    response = client.delete("/todos/1")
    assert response.status_code == 404


def test_delete_completed_todos():
    active = TodoItem(id=1, title="Active", description="", completed=False)
    done = TodoItem(id=2, title="Done", description="", completed=True)
    save_todos([active, done])
    response = client.delete("/todos/completed")
    assert response.status_code == 204
    remaining = load_todos()
    assert len(remaining) == 1
    assert remaining[0].id == 1


def test_delete_completed_todos_when_none_completed():
    todo = TodoItem(id=1, title="Active", description="", completed=False)
    save_todos([todo])
    response = client.delete("/todos/completed")
    assert response.status_code == 204
    assert len(load_todos()) == 1


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
    todo = TodoItem(id=1, title="Test", description="", completed=False)
    save_todos([todo])
    before = _counter_value("todo_completed_total")
    client.put("/todos/1", json={"title": "Test", "completed": True})
    assert _counter_value("todo_completed_total") == before + 1


def test_uncompleted_update_does_not_increment_completed_counter():
    todo = TodoItem(id=1, title="Test", description="", completed=False)
    save_todos([todo])
    before = _counter_value("todo_completed_total")
    client.put("/todos/1", json={"title": "Updated", "completed": False})
    assert _counter_value("todo_completed_total") == before


def test_delete_todo_increments_deleted_counter():
    todo = TodoItem(id=1, title="Test", description="", completed=False)
    save_todos([todo])
    before = _counter_value("todo_deleted_total")
    client.delete("/todos/1")
    assert _counter_value("todo_deleted_total") == before + 1


def test_delete_completed_increments_deleted_counter_by_count():
    save_todos([
        TodoItem(id=1, title="A", description="", completed=True),
        TodoItem(id=2, title="B", description="", completed=True),
        TodoItem(id=3, title="C", description="", completed=False),
    ])
    before = _counter_value("todo_deleted_total")
    client.delete("/todos/completed")
    assert _counter_value("todo_deleted_total") == before + 2


def test_items_current_gauge_reflects_active_and_completed_counts():
    save_todos([
        TodoItem(id=1, title="A", description="", completed=True),
        TodoItem(id=2, title="B", description="", completed=False),
        TodoItem(id=3, title="C", description="", completed=False),
    ])
    assert _gauge_value("todo_items_current", "completed") == 1
    assert _gauge_value("todo_items_current", "active") == 2


def test_concurrent_creates_do_not_corrupt_todo_file():
    # JMeter 부하 테스트에서 락 없이 동시 쓰기가 몰리면 todo.json이 깨지는 것을 확인했던 회귀 테스트.
    request_count = 30
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(
            lambda i: client.post("/todos", json={"title": f"concurrent-{i}"}),
            range(request_count),
        ))

    assert all(response.status_code == 201 for response in responses)
    todos = load_todos()  # 파일이 손상됐다면 json.JSONDecodeError로 여기서 바로 실패한다
    assert len(todos) == request_count
    assert len({todo.id for todo in todos}) == request_count  # id 중복(lost update) 없음
