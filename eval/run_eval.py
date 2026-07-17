"""[P3] Do do chinh xac. BGK CHAC CHAN hoi "lam sao biet phan loai dung?"

Chay: python eval/run_eval.py
Doc eval/gold_set.jsonl -> chay pipeline -> in accuracy / precision / recall / F1
theo tung verdict + ty le citation dung.

Muc tieu toi thieu de demo: 50 claim gan nhan tay, accuracy >= 80%.
"""


def load_gold() -> list[dict]:
    raise NotImplementedError


def evaluate() -> dict:
    """Tra {verdict_accuracy, citation_accuracy, per_class_f1, confusion_matrix}."""
    raise NotImplementedError


if __name__ == "__main__":
    evaluate()
