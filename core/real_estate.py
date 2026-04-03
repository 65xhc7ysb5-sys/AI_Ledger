# core/real_estate.py
from __future__ import annotations

def project_price(price_2026: float, growth_rate: float, years: int = 3) -> float:
    return price_2026 * (1 + growth_rate) ** years

def calculate_gap_series(
    uijeongbu_price: float, uijeongbu_rate: float,
    seongbuk_price: float, seongbuk_rate: float,
    start_year: int = 2026, end_year: int = 2032,
) -> list[dict]:
    result = []
    for y in range(start_year, end_year + 1):
        n = y - start_year
        u = uijeongbu_price * (1 + uijeongbu_rate) ** n
        s = seongbuk_price * (1 + seongbuk_rate) ** n
        result.append({"year": y, "의정부": u, "성북구": s, "gap": s - u})
    return result

def can_purchase(equity: float, loan: float, target_price: float, ltv: float = 0.7) -> bool:
    required_equity = target_price * (1 - ltv)
    return (equity + loan) >= target_price and equity >= required_equity

def opportunity_cost(tax_amount: float, r_annual: float, years: int) -> float:
    return tax_amount * (1 + r_annual) ** years - tax_amount