import streamlit as st
import pandas as pd

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")
st.title("📊 소비 분석 대시보드")

# 데이터 확인
if 'ledger' not in st.session_state or not st.session_state.ledger:
    st.info("아직 데이터가 없습니다. 'Home' 탭에서 내역을 입력해주세요.")
    st.stop()

# 데이터프레임 변환
df = pd.DataFrame(st.session_state.ledger)

# [중요] 날짜 변환 (문자열 -> 날짜객체)
try:
    df['date'] = pd.to_datetime(df['date'])
except:
    df['date'] = pd.to_datetime('today')

# 1. 상단 요약 (Metrics)
total_spend = df['amount'].sum()
col1, col2, col3 = st.columns(3)
col1.metric("총 지출액", f"{total_spend:,}원")
col2.metric("총 건수", f"{len(df)}건")
if not df.empty:
    top_cat = df.groupby('category')['amount'].sum().idxmax()
    col3.metric("최다 지출", top_cat)

st.divider()

# 2. 그래프 섹션
tab1, tab2 = st.tabs(["📈 날짜별 추이", "🍕 카테고리별 비중"])

with tab1:
    st.subheader("일별 지출 흐름")
    # 날짜별로 그룹화하여 합계 계산
    daily_spend = df.groupby('date')['amount'].sum().reset_index()
    # 꺾은선 그래프 (Line Chart)
    st.line_chart(daily_spend, x='date', y='amount', color='#FF4B4B')

with tab2:
    st.subheader("카테고리별 지출")
    category_spend = df.groupby('category')['amount'].sum()
    st.bar_chart(category_spend)

st.divider()

# 3. 상세 내역 관리 (삭제/수정)
st.subheader("📋 상세 내역 리스트")

# 최신순 정렬
df_display = df.sort_values(by='date', ascending=False).reset_index(drop=True)

# 데이터 에디터 (여기서 수정하면 반영되도록 설정)
edited_df = st.data_editor(
    df_display,
    column_config={
        "amount": st.column_config.NumberColumn("금액", format="%d원"),
        "date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
    },
    num_rows="dynamic", # 행 추가/삭제 허용
    use_container_width=True,
    key="editor"
)

# 수정된 내용이 있으면 세션에 저장 (JSON 호환 위해 날짜를 다시 문자로 변환)
if len(edited_df) != len(df) or not edited_df.equals(df_display):
    # 날짜 객체를 다시 문자열("YYYY-MM-DD")로 변환하여 저장
    edited_df['date'] = edited_df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    st.session_state.ledger = edited_df.to_dict('records')
    st.rerun()