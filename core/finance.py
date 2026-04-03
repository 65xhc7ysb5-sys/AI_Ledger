# core/finance.py
from __future__ import annotations

def calculate_fv(pmt: float, r_annual: float, n_months: int) -> float:
    if r_annual == 0:
        return pmt * n_months
    r = r_annual / 12
    return pmt * ((1 + r) ** n_months - 1) / r

def calculate_asset_fv(pv: float, r_annual: float, n_months: int) -> float:
    r = r_annual / 12
    return pv * (1 + r) ** n_months

def calculate_max_loan(monthly_income: float, rate_annual: float, years: int) -> float:
    annual_limit = monthly_income * 12 * 0.4
    r = rate_annual / 12
    n = years * 12
    if r == 0:
        return annual_limit / 12 * n
    return (annual_limit / 12) / r * (1 - (1 + r) ** -n)

def calculate_total_equity(
    monthly_saving: float, r_annual: float, n_months: int,
    current_investment: float, jeonse_return: float, subscription: float,
) -> float:
    return (
        calculate_fv(monthly_saving, r_annual, n_months)
        + calculate_asset_fv(current_investment, r_annual, n_months)
        + jeonse_return
        + subscription
    )

def opportunity_cost(tax_amount: float, r_annual: float, years: int) -> float:
    """취득세를 복리 운용 시 기회비용 (원금 제외 순이익)."""
    return tax_amount * (1 + r_annual) ** years - tax_amount