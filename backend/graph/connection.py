"""[P2] Neo4j driver singleton + helper query.

Mọi module đi qua đây, không ai tự tạo driver riêng.
"""

from __future__ import annotations

import atexit
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.core.config import get_settings

_driver: Driver | None = None


def get_driver() -> Driver:
    """Driver dùng chung. Tạo lazy, tự đóng lúc thoát."""
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = GraphDatabase.driver(
            s.neo4j_uri,
            auth=(s.neo4j_user, s.neo4j_password),
            max_connection_lifetime=3600,
        )
        atexit.register(close)
    return _driver


def close() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run(cypher: str, **params: Any) -> list[dict]:
    """Query đọc. Trả list dict."""
    with get_driver().session() as session:
        return [record.data() for record in session.run(cypher, **params)]


def write(cypher: str, **params: Any) -> list[dict]:
    """Query ghi trong transaction có retry (driver tự retry khi deadlock)."""

    def _tx(tx):
        return [record.data() for record in tx.run(cypher, **params)]

    with get_driver().session() as session:
        return session.execute_write(_tx)


def write_batch(statements: list[tuple[str, dict]]) -> None:
    """Nhiều câu ghi trong MỘT transaction — vào hết hoặc không gì cả.

    Dùng khi nạp 1 văn bản: nửa cây Điều-Khoản-Điểm nằm trong graph còn tệ hơn
    là không có gì, vì query sau đó trả kết quả sai mà không báo lỗi.
    """

    def _tx(tx):
        for cypher, params in statements:
            tx.run(cypher, **params)

    with get_driver().session() as session:
        session.execute_write(_tx)


def healthcheck() -> bool:
    try:
        return run("RETURN 1 AS ok")[0]["ok"] == 1
    except Exception:
        return False


def wipe() -> None:
    """Xoá sạch graph. CHỈ dùng lúc dev để nạp lại fixture."""
    write("MATCH (n) DETACH DELETE n")
