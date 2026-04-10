import streamlit as st
import pandas as pd
import sys
import os
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import load_data, get_available_months, get_category_mapping, get_budgets, get_setting
from config import TARGET_DATE_YEAR, TARGET_DATE_MONTH, TARGET_EQUITY, VARIABLE_BUDGET_LIMIT, MONTHLY_SAVING_TARGET

st.set_page_config(page_title="Claude Export", page_icon="📤", layout="wide")

# ==========================================
# 마크다운 생성 함수
# ==========================================
# 변경 후
def _s(key, default):
    return type(default)(get_setting(key) or default)


def _anonymize(amount: int, total: int, label: str, anonymize: bool) -> str:
    """금액을 실제값 또는 익명화된 비율/등급으로 반환합니다."""
    if not anonymize:
        return f"{amount:,}원"
    pct = amount / total * 100 if total > 0 else 0
    if pct >= 30:
        grade = "매우높음"
    elif pct >= 20:
        grade = "높음"
    elif pct >= 10:
        grade = "보통"
    elif pct >= 5:
        grade = "낮음"
    else:
        grade = "매우낮음"
    return f"총지출의 {pct:.0f}% ({grade})"


def build_markdown(
    month_str: str,
    df: pd.DataFrame,
    category_mapping: dict,
    sections: dict,
    anonymize: bool = False,
) -> str:
    """
    선택한 월의 데이터를 Claude Project Knowledge용 마크다운으로 변환합니다.

    sections: 포함할 섹션 제어 딕셔너리
        {
          "goal_context": bool,   # 재정 목표 컨텍스트
          "budget_vs_actual": bool,  # 예산 대비 실적
          "category_summary": bool,  # 카테고리별 합계
          "tendency": bool,       # 소비 성향
          "detail": bool,         # 전체 상세 내역
        }
    anonymize: True이면 지출 금액을 비율/등급으로 치환
    """
    year, month = month_str.split("-")
    today_str = date.today().strftime("%Y-%m-%d")

    df = df.copy()
    df["소비성향"] = df["category"].map(lambda x: category_mapping.get(x, "미분류"))
    total = int(df["amount"].sum())

    def pct(val):
        return f"{val / total * 100:.0f}%" if total > 0 else "0%"

    blocks = []
    blocks.append(f"# [AI Ledger Export] {year}년 {int(month)}월 월간 리뷰")
    blocks.append(f"> 생성일: {today_str} | 익명화: {'ON' if anonymize else 'OFF'}\n")

    # ── 섹션 0: 재정 목표 컨텍스트 ──────────────────────────────    
    if sections.get("goal_context"):
        goal_year   = _s("goal_date_year",  TARGET_DATE_YEAR)
        goal_month  = _s("goal_date_month", TARGET_DATE_MONTH)
        goal_equity = _s("goal_equity",     TARGET_EQUITY)
        goal_price  = _s("goal_purchase_price", 825_000_000)
        retire_year = _s("goal_retirement_year", 2048)
        monthly_saving_target = MONTHLY_SAVING_TARGET

        blocks.append("## 🎯 재정 목표 컨텍스트")
        blocks.append(
            f"| 항목 | 내용 |\n|------|------|\n"
            f"| 매수 목표 시점 | {goal_year}년 {goal_month}월 |\n"
            f"| 목표 자기자본 | {goal_equity:,}원 |\n"
            f"| 목표 매수가 | {goal_price:,}원 |\n"
            f"| 은퇴 목표 연도 | {retire_year}년 |\n"
            f"| 월 저축 목표 | {monthly_saving_target:,}원 |\n"
        )
    else:
        # 재정 목표 미포함 시 Claude에게 분석 전 질문 요청
        blocks.append("## 🎯 재정 목표 컨텍스트")
        blocks.append(
            "> ⚠️ 이 파일에는 재정 목표 수치가 포함되어 있지 않습니다.\n"
            "> 아래 항목을 사용자에게 직접 물어본 후 분석을 시작하세요.\n"
            ">\n"
            "> 1. 월 저축 목표액은 얼마인가요?\n"
            "> 2. 목표 자기자본은 얼마인가요?\n"
            "> 3. 목표 매수가와 목표 시점은 언제인가요?\n"
        )

    # ── 섹션 1: 예산 대비 실적 ───────────────────────────────────
    if sections.get("budget_vs_actual"):
        budgets_df = get_budgets()
        if not budgets_df.empty:
            spent_by_cat = df.groupby("category")["amount"].sum()
            budget_total = int(budgets_df["amount"].sum())
            budget_rows  = []
            for _, row in budgets_df.sort_values("category").iterrows():
                cat    = row["category"]
                budget = int(row["amount"])
                spent  = int(spent_by_cat.get(cat, 0))
                diff   = budget - spent
                status = "✅ 절약" if diff >= 0 else "🔴 초과"
                spent_display  = _anonymize(spent,  total, cat, anonymize)
                budget_display = _anonymize(budget, total, cat, anonymize) if anonymize else f"{budget:,}원"
                budget_rows.append(
                    f"| {cat} | {budget_display} | {spent_display} | {status} |"
                )
            total_display  = _anonymize(total, total, "합계", anonymize)
            budget_total_d = _anonymize(budget_total, total, "예산합계", anonymize) if anonymize else f"{budget_total:,}원"
            blocks.append("## 📊 예산 대비 실적")
            blocks.append(
                "| 카테고리 | 예산 | 실지출 | 상태 |\n"
                "|---------|------|--------|------|\n" +
                "\n".join(budget_rows) +
                f"\n| **합계** | **{budget_total_d}** | **{total_display}** | |"
            )
        else:
            blocks.append("## 📊 예산 대비 실적\n> 설정된 예산이 없습니다.\n")

    # ── 섹션 2: 카테고리별 합계 ─────────────────────────────────
    if sections.get("category_summary"):
        cat_summary = (
            df.groupby("category")["amount"].sum()
            .reset_index().sort_values("amount", ascending=False)
        )
        cat_rows = "\n".join(
            f"| {row['category']} | {_anonymize(int(row['amount']), total, row['category'], anonymize)} | {pct(row['amount'])} |"
            for _, row in cat_summary.iterrows()
        )
        blocks.append("## 💰 카테고리별 지출")
        blocks.append(
            "| 카테고리 | 금액 | 비중 |\n|---------|------|------|\n" + cat_rows
        )

    # ── 섹션 3: 소비 성향 ────────────────────────────────────────
    if sections.get("tendency"):
        needs_total = int(df[df["소비성향"] == "필수소비 (Needs)"]["amount"].sum())
        wants_total = int(df[df["소비성향"] == "선택소비 (Wants)"]["amount"].sum())
        other_total = total - needs_total - wants_total
        tendency_rows = (
            f"| 필수소비 (Needs) | {_anonymize(needs_total, total, 'Needs', anonymize)} | {pct(needs_total)} |\n"
            f"| 선택소비 (Wants) | {_anonymize(wants_total, total, 'Wants', anonymize)} | {pct(wants_total)} |"
        )
        if other_total > 0:
            tendency_rows += f"\n| 미분류 | {_anonymize(other_total, total, '미분류', anonymize)} | {pct(other_total)} |"
        total_display = _anonymize(total, total, "합계", anonymize)
        blocks.append("## 🛒 소비 성향")
        blocks.append(
            "| 구분 | 금액 | 비중 |\n|------|------|------|\n" +
            tendency_rows +
            f"\n| **총 지출** | **{total_display}** | **100%** |"
        )

    # ── 섹션 4: 상세 내역 ────────────────────────────────────────
    if sections.get("detail"):
        detail_df   = df[["date", "item", "amount", "category", "spender"]].sort_values("date")
        detail_rows = "\n".join(
            f"| {row['date']} | {row['item']} | "
            f"{_anonymize(int(row['amount']), total, row['item'], anonymize)} | "
            f"{row['category']} | {row['spender']} |"
            for _, row in detail_df.iterrows()
        )
        blocks.append("## 📋 상세 내역")
        blocks.append(
            "| 날짜 | 항목 | 금액 | 카테고리 | 지출자 |\n"
            "|------|------|------|---------|-------|\n" +
            detail_rows
        )

    return "\n\n".join(blocks) + "\n"


# ==========================================
# 페이지 UI
# ==========================================
st.title("📤 Claude Export")
st.caption("월별 지출 데이터를 Claude Project Knowledge에 업로드하기 좋은 마크다운 파일로 내보냅니다.")
st.divider()

available_months = get_available_months()

if not available_months:
    st.info("📭 내보낼 지출 데이터가 없습니다. 먼저 지출을 입력해 주세요.")
    st.stop()

# ── 월 선택 ──
col_sel, col_empty = st.columns([1, 3])
with col_sel:
    selected_month = st.selectbox("📅 내보낼 월 선택", available_months)

# ── 데이터 로드 ──
df = load_data(selected_month)
category_mapping = get_category_mapping()

if df.empty:
    st.warning(f"⚠️ {selected_month}에 해당하는 지출 내역이 없습니다.")
    st.stop()

# ── 요약 지표 ──
df_preview = df.copy()
df_preview["소비성향"] = df_preview["category"].map(lambda x: category_mapping.get(x, "미분류"))
total = int(df_preview["amount"].sum())
needs = int(df_preview[df_preview["소비성향"] == "필수소비 (Needs)"]["amount"].sum())
wants = int(df_preview[df_preview["소비성향"] == "선택소비 (Wants)"]["amount"].sum())

st.markdown(f"### 📊 {selected_month} 요약")
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 지출", f"{total:,}원")
c2.metric("거래 건수", f"{len(df)}건")
c3.metric("필수소비", f"{needs:,}원", f"{needs/total*100:.0f}%" if total else "0%", delta_color="off")
c4.metric("선택소비", f"{wants:,}원", f"{wants/total*100:.0f}%" if total else "0%", delta_color="off")

st.divider()

# ── 내보내기 옵션 ──────────────────────────────────────────────
st.markdown("#### ⚙️ 내보내기 옵션")

col_opt1, col_opt2 = st.columns([2, 1])

with col_opt1:
    st.markdown("**포함할 섹션 선택**")
    sec_goal = st.checkbox("🎯 재정 목표 컨텍스트", value=True,
                           help="미포함 시 Claude가 분석 전 목표 수치를 직접 질문합니다.")
    sec_budget  = st.checkbox("📊 예산 대비 실적",      value=True,
                              help="설정 예산 vs 실지출 카테고리별 비교")
    sec_cat     = st.checkbox("💰 카테고리별 지출 합계", value=True)
    sec_tend    = st.checkbox("🛒 소비 성향 (Needs/Wants)", value=True)
    sec_detail  = st.checkbox("📋 전체 상세 내역",       value=False,
                              help="건별 내역 포함 — 파일 크기 증가, 민감도 높음")

with col_opt2:
    st.markdown("**보안 설정**")
    anonymize = st.toggle(
        "💡 금액 익명화",
        value=False,
        help="ON: 실제 금액 대신 '총지출의 N% (등급)' 형태로 변환\nOFF: 실제 금액 그대로 포함",
    )
    if anonymize:
        st.info("금액이 비율/등급으로 치환됩니다.\n재정 목표 수치는 유지됩니다.")
    else:
        st.warning("실제 금액이 파일에 포함됩니다.\n공유 전 확인하세요.")

sections = {
    "goal_context":    sec_goal,
    "budget_vs_actual": sec_budget,
    "category_summary": sec_cat,
    "tendency":        sec_tend,
    "detail":          sec_detail,
}

st.divider()

# ── 마크다운 생성 및 미리보기 ──
md_content = build_markdown(selected_month, df, category_mapping, sections, anonymize)

with st.expander("👀 마크다운 미리보기", expanded=False):
    st.code(md_content, language="markdown")

# ── 다운로드 버튼 ──
file_name = f"ledger_{selected_month}.md"
st.download_button(
    label=f"⬇️ {file_name} 다운로드",
    data=md_content.encode("utf-8"),
    file_name=file_name,
    mime="text/markdown",
    use_container_width=True,
    type="primary",
)

st.caption(
    f"💡 다운로드한 `{file_name}` 파일을 Claude Project의 **Project Knowledge**에 업로드하세요.  \n"
    "재정 목표 컨텍스트 섹션을 포함하면 Claude가 훨씬 구체적인 진단을 제공합니다."
)