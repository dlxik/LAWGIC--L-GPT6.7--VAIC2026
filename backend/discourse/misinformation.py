"""[P3] Gan nhan dung/sai + gom cum hieu nham + phat hien trend.

Prompt: prompts/detect_misunderstanding.txt
Canh bao khi 1 cach hieu sai lap >= TREND_MIN_OCCURRENCES trong TREND_WINDOW_HOURS.
"""


def verdict_for_claim(claim_text: str, citations: list[dict]) -> dict:
    """Tra {verdict, confidence, explanation, correct_statement}."""
    raise NotImplementedError


def cluster_misconceptions(claims: list[dict]) -> list[dict]:
    """Gom claim sai giong nhau ve 1 Misconception."""
    raise NotImplementedError


def detect_trends() -> list[dict]:
    """Tra list[TrendAlert]. Day la output canh bao chinh cua he thong."""
    raise NotImplementedError
