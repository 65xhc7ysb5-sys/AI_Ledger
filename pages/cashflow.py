import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date

from database import load_data, get_available_months
from core.finance import calculate_fv as _sv_fv, calculate_asset_fv as _as_fv, calculate_max_loan
from components.formatters import format_korean

from config import TARGET_DATE_YEAR, TARGET_DATE_MONTH, TARGET_EQUITY, CURRENT_JEONSE_DEPOSIT, MONTHLY_SAVING_TARGET



# ── 상수 ────────────────────────────────────────────────────────
TARGET_DATE        = date(TARGET_DATE_YEAR, TARGET_DATE_MONTH, 1)


# ── 순수 계산 함수 ───────────────────────────────────────────────

def months_remaining(target: date = TARGET_DATE) -> int:
    today = date.today()
    return max(0, (target.year - today.year) * 12 + (target.month - today.month))


def build_yearly_chart(pmt, pv, annual_rate, chongsek, jeonse):
    """연도별 포인트 적립 추이 데이터 생성"""
    today = date.today()
    points = []
    year = today.year
    month = today.month

    while True:
        m = (TARGET_DATE.year - year) * 12 + (TARGET_DATE.month - month)
        if m < 0:
            break
        elapsed = months_remaining(TARGET_DATE) - m
        sv_fv = int(_sv_fv(pmt, annual_rate, elapsed))
        as_fv = int(_as_fv(pv, annual_rate, elapsed))
        total = sv_fv + as_fv + chongsek + jeonse
        points.append({"date": f"{year}-{month:02d}", "총 자기자본": total})

        # 다음 연도 같은 월 or 최종 목표월
        year += 1
        if year > TARGET_DATE.year or (year == TARGET_DATE.year and month > TARGET_DATE.month):
            # 마지막 포인트: 목표 시점
            sv_fv = int(_sv_fv(pmt, annual_rate, months_remaining(TARGET_DATE)))
            as_fv = int(_as_fv(pv, annual_rate, months_remaining(TARGET_DATE)))
            points.append({"date": f"{TARGET_DATE.year}-{TARGET_DATE.month:02d}", "총 자기자본": total})
            break

    return pd.DataFrame(points)


# ── 페이지 ──────────────────────────────────────────────────────

st.set_page_config(page_title="현금흐름 & 매수 시뮬레이터", layout="wide")
st.title("현금흐름 & 자기자본 시뮬레이터")

# ── Section A: 이번 달 현금흐름 요약 ────────────────────────────
st.header("Section A — 이번 달 현금흐름")

monthly_income = st.sidebar.number_input(
    "이번 달 실수령 합산 소득 (원)",
    min_value=0,
    value=10_800_000,
    step=10_000,
    format="%d",
)
st.sidebar.caption(f"= {format_korean(monthly_income)}")

current_month = datetime.today().strftime("%Y-%m")
df = load_data(current_month, None)
total_expense = int(df["amount"].sum()) if not df.empty else 0
net_savings   = monthly_income - total_expense

col1, col2, col3 = st.columns(3)
col1.metric("월 소득", f"{monthly_income:,}원")
col2.metric("총 지출", f"{total_expense:,}원")

st.divider()

# ── Section B: 2029년 2월 자기자본 적립 시뮬레이터 ──────────────
st.header("Section B — 2029년 2월 자기자본 적립 시뮬레이터")

remaining_months = months_remaining()
st.caption(f"오늘({date.today()}) 기준 목표까지 **{remaining_months}개월** 남음")

col_l, col_r = st.columns(2)
with col_l:
    monthly_saving = st.slider(
        "월 저축 목표액 (만원)",
        min_value=200, max_value=500, value=325, step=5
    ) * 10_000
    st.caption(f"= {format_korean(monthly_saving)}")

    annual_return = st.slider(
        "예상 투자 연수익률 (%)",
        min_value=0.0, max_value=8.0, value=3.0, step=0.5
    ) / 100

with col_r:
    current_investment = st.number_input(
        "현재 보유 투자자산 (원)", min_value=0, value=50_000_000, step=10_000, format="%d"
    )
    st.caption(f"= {format_korean(current_investment)}")
    current_savings_deposit = st.number_input(
        "현재 청약저축 (원)", min_value=0, value=25_000_000, step=10_000, format="%d"
    )
    st.caption(f"= {format_korean(current_savings_deposit)}")
    st.caption(f"전세보증금 회수 잔여: **{CURRENT_JEONSE_DEPOSIT:,}원** (고정)")

# 계산
sv_fv = int(_sv_fv(monthly_saving, annual_return, remaining_months))
as_fv = int(_as_fv(current_investment, annual_return, remaining_months))
total_equity  = sv_fv + as_fv + current_savings_deposit + CURRENT_JEONSE_DEPOSIT
progress_pct  = min(1.0, total_equity / TARGET_EQUITY)

st.subheader(f"예상 자기자본: {total_equity:,}원")
st.progress(progress_pct, text=f"목표 {TARGET_EQUITY:,}원 대비 {progress_pct*100:.1f}%")

if total_equity >= TARGET_EQUITY:
    st.success(f"목표 자기자본 {TARGET_EQUITY:,}원 달성 가능")
else:
    gap = TARGET_EQUITY - total_equity
    st.warning(f"목표까지 {gap:,}원 부족")

# 연도별 적립 추이 차트
chart_df = build_yearly_chart(
    monthly_saving, current_investment, annual_return,
    current_savings_deposit, CURRENT_JEONSE_DEPOSIT
)
if not chart_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart_df["date"],
        y=chart_df["총 자기자본"],
        mode="lines+markers+text",
        text=[f"{v/1e8:.2f}억" for v in chart_df["총 자기자본"]],
        textposition="top center",
        name="총 자기자본",
    ))
    fig.add_hline(y=TARGET_EQUITY, line_dash="dash", line_color="red",
                  annotation_text=f"목표 {TARGET_EQUITY/1e8:.1f}억")
    fig.update_layout(
        xaxis_title="시점",
        yaxis_title="자기자본 (원)",
        yaxis_tickformat=",",
        height=350,
        margin=dict(t=30, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)