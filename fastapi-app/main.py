import json
import os
import threading
import time
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
TODO_FILE = BASE_DIR / "todo.json"
INDEX_FILE = BASE_DIR / "templates" / "index.html"

if not TODO_FILE.exists():
    TODO_FILE.write_text("[]", encoding="utf-8")

# todo.json은 동시 요청 간 공유 자원이라, 읽기-수정-쓰기를 이 락으로 직렬화한다.
# 부하 테스트에서 락 없이 동시 쓰기가 몰리면 파일이 깨지면서(JSONDecodeError) 500이 발생함을 확인했다.
_todo_lock = threading.Lock()

app = FastAPI(title="To-Do List API")

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# 비즈니스 지표: HTTP 요청 수와는 별개로 Todo 앱 고유의 상태를 나타내는 지표
TODO_CREATED = Counter("todo_created_total", "Total number of to-do items created")
TODO_COMPLETED = Counter("todo_completed_total", "Total number of to-do items marked completed")
TODO_DELETED = Counter("todo_deleted_total", "Total number of to-do items deleted")
TODO_ITEMS_CURRENT = Gauge("todo_items_current", "Current number of to-do items by status", ["status"])


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


class TodoIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    completed: bool = False
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: date | None = None


class TodoItem(TodoIn):
    id: int


def load_todos() -> list[TodoItem]:
    raw = TODO_FILE.read_text(encoding="utf-8") if TODO_FILE.exists() else "[]"
    return [TodoItem(**todo) for todo in json.loads(raw)]


def save_todos(todos: list[TodoItem]) -> None:
    data = json.dumps(
        [todo.model_dump(mode="json") for todo in todos], indent=2, ensure_ascii=False
    )
    tmp_path = TODO_FILE.with_suffix(".json.tmp")
    tmp_path.write_text(data, encoding="utf-8")
    for attempt in range(3):
        try:
            os.replace(tmp_path, TODO_FILE)  # 원자적 교체: 쓰는 도중 상태의 파일이 노출되지 않음
            break
        except PermissionError:
            # Windows에서 백신 등이 파일을 순간적으로 잠그면 발생할 수 있음(부하테스트로 확인).
            # Linux 배포 환경에서는 발생하지 않지만 방어적으로 짧게 재시도한다.
            if attempt == 2:
                raise
            time.sleep(0.05)
    completed_count = sum(1 for todo in todos if todo.completed)
    TODO_ITEMS_CURRENT.labels(status="completed").set(completed_count)
    TODO_ITEMS_CURRENT.labels(status="active").set(len(todos) - completed_count)


def find_index(todos: list[TodoItem], todo_id: int) -> int:
    for index, todo in enumerate(todos):
        if todo.id == todo_id:
            return index
    raise HTTPException(status_code=404, detail="To-Do item not found")


@app.get("/todos")
def get_todos() -> list[TodoItem]:
    with _todo_lock:
        return load_todos()


@app.post("/todos", status_code=201)
def create_todo(payload: TodoIn) -> TodoItem:
    with _todo_lock:
        todos = load_todos()
        new_id = max((todo.id for todo in todos), default=0) + 1
        todo = TodoItem(id=new_id, **payload.model_dump())
        save_todos(todos + [todo])
    TODO_CREATED.inc()
    return todo


@app.put("/todos/{todo_id}", responses={404: {"description": "To-Do item not found"}})
def update_todo(todo_id: int, payload: TodoIn) -> TodoItem:
    with _todo_lock:
        todos = load_todos()
        index = find_index(todos, todo_id)
        just_completed = not todos[index].completed and payload.completed
        todos[index] = TodoItem(id=todo_id, **payload.model_dump())
        save_todos(todos)
        result = todos[index]
    if just_completed:
        TODO_COMPLETED.inc()
    return result


@app.delete("/todos/completed", status_code=204)
def delete_completed_todos() -> None:
    with _todo_lock:
        todos = load_todos()
        remaining = [todo for todo in todos if not todo.completed]
        save_todos(remaining)
        removed = len(todos) - len(remaining)
    TODO_DELETED.inc(removed)


@app.delete(
    "/todos/{todo_id}",
    status_code=204,
    responses={404: {"description": "To-Do item not found"}},
)
def delete_todo(todo_id: int) -> None:
    with _todo_lock:
        todos = load_todos()
        del todos[find_index(todos, todo_id)]
        save_todos(todos)
    TODO_DELETED.inc()


@app.get("/", include_in_schema=False)
def read_root() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html")
