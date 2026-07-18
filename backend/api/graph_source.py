"""[P4] Thin wrapper: probe Neo4j -> chuyen sang mock neu chua co du lieu.

P2 chua nap graph -> tra 'mock'. Khi P2 nap xong (>0 LegalDocument) -> tra 'neo4j'.
Cac endpoint chi can biet 'source' de goi mock_* hay chuyen sang cypher.

De nghiem thu bang tay:
  curl :8000/health -> "graph_source": "neo4j" | "mock"
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

_probe_cache: tuple[float, str] | None = None
_PROBE_TTL = 5.0  # tranh mo lai driver moi request khi debug


def get_source() -> str:
    """Tra 'neo4j' neu graph co it nhat 1 LegalDocument, nguoc lai 'mock'."""
    global _probe_cache
    now = time.time()
    if _probe_cache and now - _probe_cache[0] < _PROBE_TTL:
        return _probe_cache[1]

    source = "mock"
    try:
        from backend.graph.connection import run  # noqa: WPS433

        rows = run("MATCH (d:LegalDocument) RETURN count(d) AS n")
        if rows and rows[0].get("n", 0) > 0:
            source = "neo4j"
    except NotImplementedError:
        source = "mock"
    except Exception as e:  # driver mat ket noi, chua co container, ...
        log.warning(f"[graph_source] Neo4j probe failed ({e.__class__.__name__}) -> mock")
        source = "mock"

    _probe_cache = (now, source)
    return source


def invalidate() -> None:
    """Buoc probe lai lan sau — dung sau khi P2 vua nap xong."""
    global _probe_cache
    _probe_cache = None


__all__ = ["get_source", "invalidate"]
