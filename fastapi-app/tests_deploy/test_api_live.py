import os

import httpx2
import pytest

BASE_URL = os.environ.get("API_BASE_URL", "http://163.239.77.78:5002")


@pytest.fixture(scope="module")
def client():
    with httpx2.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


def test_full_crud_flow(client):
    create = client.post(
        "/todos",
        json={"title": "배포 테스트", "description": "live API test", "completed": False},
    )
    assert create.status_code == 201
    todo_id = create.json()["id"]

    listing = client.get("/todos")
    assert listing.status_code == 200
    assert any(t["id"] == todo_id for t in listing.json())

    update = client.put(
        f"/todos/{todo_id}",
        json={"title": "배포 테스트 수정", "description": "updated", "completed": True},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "배포 테스트 수정"

    delete = client.delete(f"/todos/{todo_id}")
    assert delete.status_code == 204


def test_create_todo_missing_title(client):
    response = client.post("/todos", json={"description": "no title"})
    assert response.status_code == 422


def test_delete_todo_not_found(client):
    response = client.delete("/todos/999999")
    assert response.status_code == 404
