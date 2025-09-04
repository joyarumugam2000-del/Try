import unicodedata
from typing import Tuple, Optional

from rapidfuzz import fuzz
try:
    from confusable_homoglyphs import confusables
    HAS_CONF = True
except Exception:
    HAS_CONF = False

def normalize_username(u: Optional[str]) -> str:
    if not u:
        return ""
    u = u.strip().lower()
    u = u.lstrip("@")
    table = str.maketrans({
        "0": "o",
        "1": "l",
        "3": "e",
        "5": "s",
        "7": "t",
        "8": "b",
        "$": "s",
    })
    u = u.translate(table)
    u = unicodedata.normalize("NFKC", u)
    return u

def skeleton(u: Optional[str]) -> str:
    if not u:
        return ""
    base = normalize_username(u)
    if HAS_CONF:
        try:
            return confusables.skeleton(base)
        except Exception:
            pass
    return base

def similarity(a: str, b: str) -> int:
    a = normalize_username(a)
    b = normalize_username(b)
    if not a or not b:
        return 0
    return int(fuzz.ratio(a, b))

def looks_like(a: str, b: str, min_ratio: int) -> Tuple[bool, int, str]:
    sk_a = skeleton(a)
    sk_b = skeleton(b)
    if sk_a and sk_a == sk_b and normalize_username(a) != normalize_username(b):
        return True, 100, "confusable-skeleton-match"
    score = similarity(a, b)
    if score >= min_ratio:
        return True, score, "fuzzy-similarity"
    return False, score, ""
