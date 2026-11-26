import os
import tempfile

# main/database는 import되는 순간 DATABASE_URL로 DB 엔진을 만들기 때문에, 이 설정은 import보다 먼저 해야 한다.
# 테스트는 매번 테이블을 지우고 다시 만들므로 실제 DB(DATABASE_URL)를 절대 쓰지 않는다.
# 기본은 임시 폴더의 SQLite 파일이고, PostgreSQL에서 돌리고 싶으면 비어 있는 "테스트 전용" DB를 TEST_DATABASE_URL로 지정한다.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or (
    f"sqlite:///{tempfile.mkdtemp(prefix='todo-test-')}/test.db"
)
