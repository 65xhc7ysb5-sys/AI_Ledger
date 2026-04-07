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


# ── 시나리오 비교 엔진 ────────────────────────────────────────

def simulate_scenario_a(
    purchase_price: float,
    equity: float,
    rate_annual: float,
    loan_years: int,
    price_growth_rate: float,
    sim_years: int,
) -> list[dict]:
    """
    시나리오 A: 상급지 매수
    연도별 {year, asset_value, cumulative_cost, net_asset} 반환
    """
    loan = purchase_price - equity
    r = rate_annual / 12
    n_total = loan_years * 12
    monthly_payment = loan * r / (1 - (1 + r) ** -n_total) if r > 0 else loan / n_total

    result = []
    for t in range(1, sim_years + 1):
        asset_value = purchase_price * (1 + price_growth_rate) ** t
        cumulative_cost = monthly_payment * 12 * t
        # 잔여 대출 잔액: 원리금 균등상환 잔액 공식
        n_paid = min(t * 12, n_total)
        if r > 0:
            remaining_loan = loan * ((1 + r) ** n_total - (1 + r) ** n_paid) / ((1 + r) ** n_total - 1)
        else:
            remaining_loan = max(loan - (loan / n_total) * n_paid, 0)
        net_asset = asset_value - remaining_loan
        result.append({
            "year": 2026 + t,
            "asset_value": asset_value,
            "cumulative_cost": cumulative_cost,
            "net_asset": net_asset,
        })
    return result


def simulate_scenario_b(
    uijeongbu_price: float,
    uijeongbu_growth: float,
    monthly_rent_saving: float,
    invest_rate: float,
    sim_years: int,
) -> list[dict]:
    """
    시나리오 B: 의정부 실거주 + 절약분 투자
    연도별 {year, house_value, invest_fv, net_asset} 반환
    """
    result = []
    for t in range(1, sim_years + 1):
        house_value = uijeongbu_price * (1 + uijeongbu_growth) ** t
        invest_fv = calculate_fv(monthly_rent_saving, invest_rate, t * 12)
        net_asset = house_value + invest_fv
        result.append({
            "year": 2026 + t,
            "house_value": house_value,
            "invest_fv": invest_fv,
            "net_asset": net_asset,
        })
    return result


def calc_education_opportunity_cost(
    hourly_wage: float,
    commute_hours_per_day: float,
    commute_days_per_month: int,
    monthly_transport_cost: float,
    months: int,
) -> float:
    """
    교육비 기회비용: 의정부 거주로 인한 월 시간비용 + 교통비 누적
    반환: 전체 기간 누적 기회비용 (원)
    """
    monthly_time_cost = hourly_wage * commute_hours_per_day * commute_days_per_month
    monthly_total = monthly_time_cost + monthly_transport_cost
    return monthly_total * months