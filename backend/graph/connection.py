"""[P2] Neo4j driver singleton + helper query."""


def get_driver():
    raise NotImplementedError


def run(cypher: str, **params) -> list[dict]:
    raise NotImplementedError
