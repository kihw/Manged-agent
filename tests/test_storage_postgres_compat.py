from __future__ import annotations

from app.services.storage import _PostgresCompatConnection


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, query: str, params: tuple = ()) -> None:
        self.executed.append((query, params))


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, query: str, params: tuple = ()):
        self.executed.append((query, params))
        return self.cursor_obj

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_postgres_compat_connection_exposes_cursor_and_commit() -> None:
    fake = FakeConnection()
    wrapped = _PostgresCompatConnection(fake)

    wrapped.cursor().execute("SELECT 1")
    wrapped.commit()

    assert fake.cursor_obj.executed == [("SELECT 1", ())]
    assert fake.committed is True


def test_postgres_compat_connection_rewrites_placeholders_for_execute() -> None:
    fake = FakeConnection()
    wrapped = _PostgresCompatConnection(fake)

    wrapped.execute("SELECT * FROM runs WHERE run_id = ? AND status = ?", ("run_1", "running"))

    assert fake.executed == [("SELECT * FROM runs WHERE run_id = %s AND status = %s", ("run_1", "running"))]
