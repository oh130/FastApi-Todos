import pytest
from fastapi.testclient import TestClient

import main
from main import app, save_todos, load_todos, TodoItem

client = TestClient(app)


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
