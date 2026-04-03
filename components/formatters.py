# components/formatters.py
from __future__ import annotations

def format_korean(n: int | float) -> str:
    n = int(n)
    eok = n // 100_000_000
    man = (n % 100_000_000) // 10_000
    won = n % 10_000
    parts = []
    if eok:
        parts.append(f"{eok}억")
    if man:
        parts.append(f"{man:,}만")
    if won:
        parts.append(f"{won:,}원")
    return " ".join(parts) if parts else "0원"