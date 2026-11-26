import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import psutil
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from database import SessionLocal, TodoRow, init_db

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "templates" / "index.html"

# 비즈니스 지표: HTTP 요청 수와는 별개로 Todo 앱 고유의 상태를 나타내는 지표
TODO_CREATED = Counter("todo_created_total", "Total number of to-do items created")
TODO_COMPLETED = Counter("todo_completed_total", "Total number of to-do items marked completed")
TODO_DELETED = Counter("todo_deleted_total", "Total number of to-do items deleted")
TODO_ITEMS_CURRENT = Gauge("todo_items_current", "Current number of to-do items by status", ["status"])

# 애플리케이션 로그: Docker가 stdout을 컨테이너 로그로 저장하고, Alloy가 읽어서 Loki로 전송한다.
# uvicorn 기본 액세스 로그는 끈다 (켜두면 요청 1건당 로그가 2줄씩 찍혀 대시보드 카운트가 2배가 됨).
custom_logger = logging.getLogger("custom.access")
custom_logger.setLevel(logging.DEBUG)
_log_handler = logging.StreamHandler(sys.stdout)
_log_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
custom_logger.addHandler(_log_handler)
custom_logger.propagate = False
logging.getLogger("uvicorn.access").disabled = True


def refresh_todo_gauge(session: Session) -> None:
    # 게이지 값은 메모리에 들고 있지 않고 DB를 직접 세서 맞춘다. 앱이 여러 개여도 모두 같은 DB를 보므로
    # 어느 앱에서 쓴 변경이든 같은 값을 보고한다.
    total = session.scalar(select(func.count()).select_from(TodoRow)) or 0
    completed = session.scalar(select(func.count()).select_from(TodoRow).where(TodoRow.completed.is_(True))) or 0
    TODO_ITEMS_CURRENT.labels(status="completed").set(completed)
    TODO_ITEMS_CURRENT.labels(status="active").set(total - completed)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as session:
        refresh_todo_gauge(session)
    yield


app = FastAPI(title="To-Do List API", lifespan=lifespan)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    client = request.client.host if request.client else "-"
    # 로깅 시점의 자원 사용률(psutil)을 모든 접속 로그에 같이 기록한다.
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent
    line = (
        f'{client} - "{request.method} {request.url.path} HTTP/1.1" '
        f"{response.status_code} {duration:.3f}s cpu={cpu:.1f}% mem={mem:.1f}%"
    )
    if response.status_code >= 500:
        custom_logger.error(line)
    elif response.status_code >= 400:
        custom_logger.warning(line)
    else:
        custom_logger.info(line)
    return response


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
    model_config = ConfigDict(from_attributes=True)  # DB 행(TodoRow)에서 바로 응답 모델을 만들기 위함

    id: int


def get_session():
    # 요청마다 DB 세션을 하나 열고, 응답이 끝나면 닫는다 (연결은 엔진의 연결 풀이 재사용한다).
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_todo_or_404(session: Session, todo_id: int, *, lock: bool = False) -> TodoRow:
    # lock=True: SELECT ... FOR UPDATE로 그 행을 잠그고 읽는다. 두 요청이 같은 항목을 동시에 고치면
    # 뒤 요청은 앞 요청이 끝날 때까지 기다렸다가 갱신된 값을 보고 처리한다 (완료 지표를 정확히 세기 위함).
    todo = session.get(TodoRow, todo_id, with_for_update=lock)
    if todo is None:
        custom_logger.warning(f"get_todo_or_404: id={todo_id} 를 찾을 수 없음")
        raise HTTPException(status_code=404, detail="To-Do item not found")
    return todo


@app.get("/todos")
def get_todos(session: SessionDep) -> list[TodoItem]:
    rows = session.scalars(select(TodoRow).order_by(TodoRow.id)).all()
    custom_logger.debug(f"get_todos: {len(rows)}건 조회")
    return [TodoItem.model_validate(row) for row in rows]


@app.post("/todos", status_code=201)
def create_todo(payload: TodoIn, session: SessionDep) -> TodoItem:
    row = TodoRow(**payload.model_dump())
    session.add(row)
    session.commit()  # 이 시점에 DB가 id를 발급한다
    refresh_todo_gauge(session)
    TODO_CREATED.inc()
    return TodoItem.model_validate(row)


@app.put("/todos/{todo_id}", responses={404: {"description": "To-Do item not found"}})
def update_todo(todo_id: int, payload: TodoIn, session: SessionDep) -> TodoItem:
    row = get_todo_or_404(session, todo_id, lock=True)
    just_completed = not row.completed and payload.completed
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    session.commit()
    refresh_todo_gauge(session)
    if just_completed:
        TODO_COMPLETED.inc()
    return TodoItem.model_validate(row)


@app.delete("/todos/completed", status_code=204)
def delete_completed_todos(session: SessionDep) -> None:
    result = session.execute(delete(TodoRow).where(TodoRow.completed.is_(True)))
    session.commit()
    refresh_todo_gauge(session)
    TODO_DELETED.inc(result.rowcount)


@app.delete(
    "/todos/{todo_id}",
    status_code=204,
    responses={404: {"description": "To-Do item not found"}},
)
def delete_todo(todo_id: int, session: SessionDep) -> None:
    row = get_todo_or_404(session, todo_id)
    session.delete(row)
    session.commit()
    refresh_todo_gauge(session)
    TODO_DELETED.inc()


@app.get("/", include_in_schema=False)
def read_root() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html")
