import json
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
    TODO_FILE.write_text(data, encoding="utf-8")
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
    return load_todos()


@app.post("/todos", status_code=201)
def create_todo(payload: TodoIn) -> TodoItem:
    todos = load_todos()
    new_id = max((todo.id for todo in todos), default=0) + 1
    todo = TodoItem(id=new_id, **payload.model_dump())
    save_todos(todos + [todo])
    TODO_CREATED.inc()
    return todo


@app.put("/todos/{todo_id}", responses={404: {"description": "To-Do item not found"}})
def update_todo(todo_id: int, payload: TodoIn) -> TodoItem:
    todos = load_todos()
    index = find_index(todos, todo_id)
    just_completed = not todos[index].completed and payload.completed
    todos[index] = TodoItem(id=todo_id, **payload.model_dump())
    save_todos(todos)
    if just_completed:
        TODO_COMPLETED.inc()
    return todos[index]


@app.delete("/todos/completed", status_code=204)
def delete_completed_todos() -> None:
    todos = load_todos()
    remaining = [todo for todo in todos if not todo.completed]
    save_todos(remaining)
    TODO_DELETED.inc(len(todos) - len(remaining))


@app.delete(
    "/todos/{todo_id}",
    status_code=204,
    responses={404: {"description": "To-Do item not found"}},
)
def delete_todo(todo_id: int) -> None:
    todos = load_todos()
    del todos[find_index(todos, todo_id)]
    save_todos(todos)
    TODO_DELETED.inc()


@app.get("/", include_in_schema=False)
def read_root() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html")
