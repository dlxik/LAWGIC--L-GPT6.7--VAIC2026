"""[P2] Nap JSON da cau truc hoa vao Neo4j. Dung MERGE -> idempotent."""


def load_document(doc: dict) -> None:
    """Nap LegalDocument + cay Dieu-Khoan-Diem + entity."""
    raise NotImplementedError


def load_entities(entities: list[dict]) -> None:
    raise NotImplementedError


def load_post(post: dict, claims: list[dict]) -> None:
    """Nap Post + Claim + REFERS_TO + INSTANCE_OF."""
    raise NotImplementedError
