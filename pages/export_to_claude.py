import streamlit as st
import pandas as pd
import sys
import os
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import load_data, get_available_months, get_category_mapping

st.set_page_config(page_title="Claude Export", page_icon="📤", layout="wide")

# ==========================================
# 마크다운 생성 함수
# ==========================================
def build_markdown(month_str: str, df: pd.DataFrame, category_mapping: dict) -> str:
    """선택한 월의 데이터를 Claude Project Knowledge용 마크다운으로 변환합니다."""

    year, month = month_str.split("-")
    today_str = date.today().strftime("%Y-%m-%d")

    # 소비성향 컬럼 추가
    df = df.copy()
    df["소비성향"] = df["category"].map(lambda x: category_mapping.get(x, "미분류"))

    total = df["amount"].sum()

    # ── 섹션 1: 카테고리별 합계 ──
    cat_summary = (
        df.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    cat_rows = "\n".join(
        f"| {row['category']} | {row['amount']:,}원 |"
        for _, row in cat_summary.iterrows()
    )

    # ── 섹션 2: 필수/선택 소비 ──
    needs_total = df[df["소비성향"] == "필수소비 (Needs)"]["amount"].sum()
    wants_total = df[df["소비성향"] == "선택소비 (Wants)"]["amount"].sum()
    other_total = total - needs_total - wants_total

    def pct(val):
        return f"{val / total * 100:.0f}%" if total > 0 else "0%"

    tendency_rows = f"| 필수소비 (Needs) | {needs_total:,}원 | {pct(needs_total)} |\n"
    tendency_rows += f"| 선택소비 (Wants) | {wants_total:,}원 | {pct(wants_total)} |"
    if other_total > 0:
        tendency_rows += f"\n| 미분류 | {other_total:,}원 | {pct(other_total)} |"

    # ── 섹션 3: 전체 상세 내역 ──
    detail_df = df[["date", "item", "amount", "category", "spender"]].sort_values("date")
    detail_rows = "\n".join(
        f"| {row['date']} | {row['item']} | {row['amount']:,}원 | {row['category']} | {row['spender']} |"
        for _, row in detail_df.iterrows()
    )

    # ── 최종 마크다운 조합 ──
    md = f"""\
---
# [AI Ledger Export] {year}년 {int(month)}월 지출 요약
> 생성일: {today_str}

## 카테고리별 합계
| 카테고리 | 금액 |
|---------|------|
{cat_rows}

## 소비 성향
| 구분 | 금액 | 비중 |
|------|------|------|
{tendency_rows}
| **총 지출** | **{total:,}원** | **100%** |

## 상세 내역
| 날짜 | 항목 | 금액 | 카테고리 | 지출자 |
|------|------|------|---------|-------|
{detail_rows}
---
"""
    return md


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

# ── 미리보기 요약 ──
df_preview = df.copy()
df_preview["소비성향"] = df_preview["category"].map(lambda x: category_mapping.get(x, "미분류"))
total = df_preview["amount"].sum()
needs = df_preview[df_preview["소비성향"] == "필수소비 (Needs)"]["amount"].sum()
wants = df_preview[df_preview["소비성향"] == "선택소비 (Wants)"]["amount"].sum()

st.markdown(f"### 📊 {selected_month} 요약")
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 지출", f"{total:,}원")
c2.metric("거래 건수", f"{len(df)}건")
c3.metric("필수소비", f"{needs:,}원", f"{needs/total*100:.0f}%" if total else "0%", delta_color="off")
c4.metric("선택소비", f"{wants:,}원", f"{wants/total*100:.0f}%" if total else "0%", delta_color="off")

st.divider()

# ── 마크다운 생성 및 미리보기 ──
md_content = build_markdown(selected_month, df, category_mapping)

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
    type="primary"
)

st.caption(f"💡 다운로드한 `{file_name}` 파일을 Claude Project의 **Project Knowledge**에 업로드하세요.")
