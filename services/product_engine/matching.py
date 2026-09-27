"""Product identity matching.

Conservative policy (per blueprint):
    score >= 0.995  auto-match
    0.95 <= score < 0.995  review candidate (never merged automatically)
    score < 0.95  never merge

Score = max of {identifier match (1.0 when exact), attribute-weighted similarity,
text similarity, embedding similarity}. Identifier equality short-circuits to 1.0
only when the identifier is strong (gtin/ean/upc/sku/model#) AND not generic.
"""

from typing import Any

AUTO_MATCH_THRESHOLD = 0.995
REVIEW_MATCH_THRESHOLD = 0.95

STRONG_IDENTIFIER_KEYS = ("gtin", "ean", "upc", "sku", "mpn", "model")
_GENERIC_IDENTIFIERS = {"", "unknown", "n/a", "generic", "none", "0"}


def normalize_identifier(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ",".join(str(v) for v in value)
    return str(value).strip().lower().replace(" ", "").replace("-", "")


def is_strong_identifier(key: str, value: Any) -> bool:
    norm = normalize_identifier(value)
    return key in STRONG_IDENTIFIER_KEYS and norm not in _GENERIC_IDENTIFIERS


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    tokens: set[str] = set()
    for word in str(text).lower().split():
        cleaned = "".join(ch for ch in word if ch.isalnum())
        if len(cleaned) >= 2:
            tokens.add(cleaned)
    return tokens


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _attr_overlap(query: dict[str, Any], candidate: dict[str, Any]) -> float:
    keys = ("brand", "model", "color", "storage", "size", "condition", "category", "subcategory")
    matched = 0
    total = 0
    for key in keys:
        q = str(query.get(key) or "").strip().lower()
        c = str(candidate.get(key) or "").strip().lower()
        if not q and not c:
            continue
        total += 1
        if q and c and (q == c or q in c or c in q):
            matched += 1
    return matched / total if total else 0.0


def _identifier_score(query: dict[str, Any], candidate: dict[str, Any]) -> float:
    """1.0 on strong identifier equality; 0.5 on weak (title-derived) equality."""
    for key in STRONG_IDENTIFIER_KEYS:
        q = normalize_identifier(query.get(key))
        c = normalize_identifier(candidate.get(key))
        if q and c and q == c:
            return 1.0
        if q and c and key in ("gtin", "ean", "upc") and len(q) >= 8 and len(c) >= 8 and q[-8:] == c[-8:]:
            return 0.99  # truncated identifiers (common scrapes)
    return 0.0


def _text_score(query: dict[str, Any], candidate: dict[str, Any]) -> float:
    q_tokens = tokenize(query.get("title") or query.get("canonical_name"))
    c_tokens = tokenize(candidate.get("title") or candidate.get("canonical_name"))
    if not q_tokens or not c_tokens:
        return 0.0
    base = jaccard(q_tokens, c_tokens)
    q_brand = tokenize(str(query.get("brand") or ""))
    c_brand = tokenize(str(candidate.get("brand") or ""))
    brand_boost = 0.15 if q_brand and c_brand and q_brand == c_brand else 0.0
    return min(1.0, base + brand_boost)


class TextEmbedder:
    """Default: deterministic character n-gram hashing (no heavy deps).

    Swap in sentence-transformers in ml/ later; the contract is
    embed(text) -> list[float] and similarity(a, b) -> [0, 1].
    """

    def __init__(self, n_grams: tuple[int, ...] = (2, 3), dim: int = 256, seed: int = 0) -> None:
        self.n_grams = n_grams
        self.dim = dim
        self._rng = __import__("random").Random(seed)

    def embed(self, text: str | None) -> list[float]:
        tokens = tokenize(text)
        vec = [0.0] * self.dim
        for tok in sorted(tokens):
            for n in self.n_grams:
                for i in range(0, max(0, len(tok) - n + 1)):
                    h = hash(f"{tok[i:i+n]}#{n}") % self.dim
                    vec[h] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0:
            return vec
        return [v / norm for v in vec]

    def similarity(self, a: str | None, b: str | None) -> float:
        va = self.embed(a)
        vb = self.embed(b)
        return sum(x * y for x, y in zip(va, vb))


def match_score(
    query: dict[str, Any],
    candidate: dict[str, Any],
    embedder: TextEmbedder | None = None,
) -> float:
    """Overall identity score in [0, 1]."""
    ident = _identifier_score(query, candidate)
    if ident >= 1.0:
        return 1.0
    attr = _attr_overlap(query, candidate)
    text = _text_score(query, candidate)
    emb = 0.0
    if embedder is not None:
        emb = embedder.similarity(
            query.get("title") or query.get("canonical_name"),
            candidate.get("title") or candidate.get("canonical_name"),
        )
    return max(ident, attr, text, emb)


def decide(score: float) -> str:
    """AUTO_MATCH / REVIEW / NO_MATCH per the conservative policy."""
    if score >= AUTO_MATCH_THRESHOLD:
        return "AUTO_MATCH"
    if score >= REVIEW_MATCH_THRESHOLD:
        return "REVIEW"
    return "NO_MATCH"


def find_best_match(
    query: dict[str, Any],
    candidates: list[tuple[Any, dict[str, Any]]],
    embedder: TextEmbedder | None = None,
) -> tuple[Any | None, float, str, dict[str, float]]:
    """candidates: [(variant_or_listing, identity_dict)]. Returns (best, score, decision, details)."""
    best_obj: Any | None = None
    best_score = 0.0
    best_component = "none"
    details: dict[str, float] = {}
    for obj, identity in candidates:
        score = match_score(query, identity, embedder)
        if score > best_score:
            best_obj, best_score = obj, score
            best_component = (
                "identifier"
                if _identifier_score(query, identity) >= 1.0
                else "embedding" if embedder is not None and embedder.similarity(
                    query.get("title") or query.get("canonical_name"),
                    identity.get("title") or identity.get("canonical_name"),
                ) >= max(0.5, score - 0.1)
                else "attributes/text"
            )
    details = {"top": best_score, "top_component": best_component}
    return best_obj, best_score, decide(best_score), details
