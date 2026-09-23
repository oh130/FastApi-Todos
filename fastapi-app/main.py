import json
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
TODO_FILE = BASE_DIR / "todo.json"
INDEX_FILE = BASE_DIR / "templates" / "index.html"

if not TODO_FILE.exists():
    TODO_FILE.write_text("[]", encoding="utf-8")

app = FastAPI(title="To-Do List API")


class TodoIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
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
    return todo


@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, payload: TodoIn) -> TodoItem:
    todos = load_todos()
    todos[find_index(todos, todo_id)] = TodoItem(id=todo_id, **payload.model_dump())
    save_todos(todos)
    return todos[find_index(todos, todo_id)]


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int) -> None:
    todos = load_todos()
    del todos[find_index(todos, todo_id)]
    save_todos(todos)


@app.get("/", include_in_schema=False)
def read_root() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html")
