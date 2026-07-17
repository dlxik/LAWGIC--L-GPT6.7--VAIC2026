"""[P1] Trich entity tu moi Dieu/Khoan/Diem bang LLM.

Prompt: prompts/extract_entities.txt
Output: ExtractedEntities (backend/models/schemas.py)
"""


def extract_entities(node_text: str, node_id: str) -> dict:
    raise NotImplementedError


def extract_all(doc: dict) -> list[dict]:
    """Chay batch cho toan bo node cua 1 van ban."""
    raise NotImplementedError
