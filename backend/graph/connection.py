"""[P2] Neo4j driver singleton + helper query.

Mọi module đi qua đây, không ai tự tạo driver riêng.
"""

from __future__ import annotations

import atexit
import os
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.core.config import get_settings

_driver: Driver | None = None

# Timeout transaction (giay): mot query Neo4j treo se giu 1 worker threadpool cua API
# vo han -> chan bang transaction timeout. Doc tu env de tinh chinh.
def _query_timeout() -> float:
    try:
        return float(os.environ.get("NEO4J_QUERY_TIMEOUT", "30"))
    except (TypeError, ValueError):
        return 30.0


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
    """Query đọc. Explicit transaction có TIMEOUT (chống query Neo4j treo giữ worker).

    Managed tx (execute_read) không nhận timeout ở driver 5.x -> dùng begin_transaction
    với timeout. Đọc không cần auto-retry deadlock nên đánh đổi này hợp lý.
    """
    with get_driver().session() as session:
        with session.begin_transaction(timeout=_query_timeout()) as tx:
            data = [record.data() for record in tx.run(cypher, **params)]
            tx.commit()
            return data


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
    """Xoá sạch graph. CHỐT AN TOÀN: chỉ chạy khi ALLOW_WIPE=1.

    `MATCH (n) DETACH DELETE n` là thao tác huỷ diệt. Nếu NEO4J_URI vô tình trỏ vào
    graph THẬT (vd chạy pytest/loader nhầm), một lần gọi là mất sạch. Bắt buộc đặt
    env ALLOW_WIPE=1 để xác nhận có chủ đích. Loader CLI `--wipe` tự đặt biến này.
    """
    if os.environ.get("ALLOW_WIPE") not in ("1", "true", "True"):
        raise RuntimeError(
            "wipe() bị chặn: đặt ALLOW_WIPE=1 để xác nhận xoá sạch graph "
            "(chốt chống chạy pytest/loader nhầm lên Neo4j thật)."
        )
    write("MATCH (n) DETACH DELETE n")
