import os
import time
from datetime import date
from pathlib import Path

from sqlalchemy import Boolean, Date, Integer, String, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

BASE_DIR = Path(__file__).resolve().parent

# 저장소 주소는 환경변수 DATABASE_URL로 정한다.
# - compose/쿠버네티스: PostgreSQL (예: postgresql+psycopg://todo:비밀번호@postgres:5432/todos)
# - 환경변수가 없으면 앱 폴더의 SQLite 파일(todo.db)을 쓴다. DB 서버 없이 `uvicorn main:app`만으로 로컬 실행이 되게 하려는 용도다.
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'todo.db'}")

# 테이블 생성 쿼리를 동시에 보내는 복제본끼리 겹치지 않게 하는 PostgreSQL advisory lock 번호 (아무 고정 정수)
_SCHEMA_LOCK_KEY = 7017


class Base(DeclarativeBase):
    pass


class TodoRow(Base):
    __tablename__ = "todos"
    # SQLite는 기본적으로 지운 마지막 번호를 다시 쓴다. PostgreSQL 시퀀스처럼 번호를 재사용하지 않게 맞춘다 (SQLite에서만 적용되는 옵션).
    __table_args__ = {"sqlite_autoincrement": True}

    # id는 DB가 번호를 매긴다(PostgreSQL 시퀀스). 예전처럼 "현재 최대값 + 1"을 앱에서 계산하면
    # 앱이 여러 개일 때 같은 번호를 동시에 가져가는 문제가 생긴다.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


def _make_engine(url: str):
    if url.startswith("sqlite"):
        # SQLite는 한 번에 한 쓰기만 되므로, 다른 쓰기가 끝나길 최대 30초 기다리게 한다(기다리지 않으면 "database is locked" 오류).
        # check_same_thread=False: FastAPI가 요청을 스레드풀의 서로 다른 스레드에서 처리하기 때문이다.
        return create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    # pool_pre_ping: DB가 재시작되면서 끊어진 연결을 쓰기 전에 확인해서 새로 맺는다.
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(retries: int = 30, delay: float = 1.0) -> None:
    """테이블이 없으면 만든다. DB가 아직 뜨는 중이면(컨테이너 동시 시작) 잠시 기다리며 다시 시도한다."""
    for attempt in range(retries):
        try:
            with engine.begin() as conn:
                if engine.dialect.name == "postgresql":
                    # 복제본 여러 개가 동시에 시작하면 서로 CREATE TABLE을 보내서 한쪽이 "이미 존재" 오류로 죽을 수 있다.
                    # 트랜잭션이 끝날 때까지 유지되는 advisory lock으로 테이블 생성을 한 번에 하나씩 하게 한다.
                    conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SCHEMA_LOCK_KEY})
                Base.metadata.create_all(conn)
            return
        except OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
