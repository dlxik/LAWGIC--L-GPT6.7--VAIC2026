"""[P2] Semantic diff giua van ban moi va van ban cu.

Ghep Diem cu <-> Diem moi, phan loai thay doi, tao SUPERSEDED_BY.
change_type: UNCHANGED | REWORDED | TIGHTENED | LOOSENED | ADDED | REMOVED
"""


def diff_documents(old_doc_id: str, new_doc_id: str) -> list[dict]:
    """Tra list[PointDiff]."""
    raise NotImplementedError


def law_as_of(topic: str, date: str) -> list[dict]:
    """Time-travel: luat co hieu luc tai ngay `date`. Diem an cua demo."""
    raise NotImplementedError
