"""Project-scoped lightweight semantic retrieval without external services."""

import math
import re
from collections import Counter

from story_ml.types import ContextDocument, RetrievedContext

# _TOKEN = re.compile(r"[a-z0-9]+")
_TOKEN = re.compile(r"[a-z0-9]+")

def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class SemanticContextRetriever:
    """TF-IDF cosine retrieval suitable for small project context collections.

    This is lexical-semantic retrieval, not an embedding model. Scores are evidence
    for ordering only and are never treated as proof that a claim is supported.
    """

    def __init__(
        self, documents: list[ContextDocument], minimum_score: float = 0.05
    ) -> None:
        self.documents = documents
        self.minimum_score = minimum_score

    def retrieve(
        self, project_id: str, query: str, limit: int = 8
    ) -> list[RetrievedContext]:
        scoped = [
            doc
            for doc in self.documents
            if doc.project_id == project_id and doc.text.strip()
        ]
        if not scoped or not query.strip():
            return []
        query_tokens = _tokens(query)
        corpus = [_tokens(doc.text) for doc in scoped]
        document_frequency = Counter(
            token for tokens in corpus for token in set(tokens)
        )

        def vector(tokens: list[str]) -> dict[str, float]:
            counts = Counter(tokens)
            return {
                token: (1 + math.log(count))
                * (1 + math.log((1 + len(corpus)) / (1 + document_frequency[token])))
                for token, count in counts.items()
            }

        query_vector = vector(query_tokens)
        query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
        results: list[RetrievedContext] = []
        for document, tokens in zip(scoped, corpus, strict=True):
            doc_vector = vector(tokens)
            denominator = query_norm * math.sqrt(
                sum(value * value for value in doc_vector.values())
            )
            score = sum(
                query_vector.get(key, 0.0) * value for key, value in doc_vector.items()
            )
            score = score / denominator if denominator else 0.0
            if score >= self.minimum_score:
                results.append(RetrievedContext(document=document, score=score))
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]
