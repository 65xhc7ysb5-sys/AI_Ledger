import streamlit as st
import pandas as pd
import sys
import os
import plotly.express as px
import plotly.graph_objects as go

# Streamlit 최신 기능(부분 갱신) 활용을 위한 임포트
try:
    from streamlit import fragment
except ImportError:
    try:
        from streamlit import experimental_fragment as fragment
    except ImportError:
        def fragment(func):
            return func

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import (
    load_data, delete_expense, update_expense, get_available_months, 
    DB_NAME, get_categories, add_category, delete_category_safe
)

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

# --- 1. 사이드바 (필터 및 백업) ---
with st.sidebar:
    st.header("🔍 조회 설정")
    spender_filter = st.radio("👤 사용자 선택", ["전체", "공동", "남편", "아내", "아이"])
    
    available_months = get_available_months()
    if available_months:
        options = ["전체 기간"] + available_months
        default_index = 1 
    else:
        options = ["전체 기간"]
        default_index = 0
        
    selected_month = st.selectbox("📅 월 선택", options, index=default_index)
    current_filter_key = f"{selected_month}_{spender_filter}"

    st.divider()
    
    with st.expander("🏷️ 카테고리 관리"):
        new_cat = st.text_input("새 카테고리 추가", placeholder="예: 반려동물")
        if st.button("추가"):
            if new_cat and add_category(new_cat):
                st.success(f"'{new_cat}' 추가됨")
                st.session_state.pop('dashboard_data', None)
                st.rerun()
        
        st.write("---")
        current_cats = get_categories()
        del_cat = st.selectbox("삭제할 카테고리", ["선택 안 함"] + current_cats)
        if del_cat != "선택 안 함":
            if st.button(f"🗑️ '{del_cat}' 삭제"):
                delete_category_safe(del_cat)
                st.session_state.pop('dashboard_data', None)
                st.rerun()

    st.divider()
    try:
        with open(DB_NAME, "rb") as f:
            st.download_button("💾 DB 원본 백업", f, "ledger_backup.db")
    except: pass

# --- 2. 데이터 로드 ---
full_df = load_data("전체 기간", spender_filter)
if not full_df.empty:
    full_df['date'] = pd.to_datetime(full_df['date'])

if 'dashboard_data' not in st.session_state or st.session_state.get('last_filter') != current_filter_key:
    raw_df = load_data(selected_month, spender_filter)
    if not raw_df.empty:
        raw_df['date'] = pd.to_datetime(raw_df['date'])
    st.session_state['dashboard_data'] = raw_df
    st.session_state['last_filter'] = current_filter_key

df = st.session_state['dashboard_data']

if selected_month == "전체 기간":
    st.title("📊 전체 소비 분석")
else:
    st.title(f"📊 {selected_month} 소비 분석")

if df.empty:
    st.info(f"선택하신 조건({selected_month}, {spender_filter})에 해당하는 데이터가 없습니다.")
    st.stop()

# --- 3. 통계 (상단) ---
total = df['amount'].sum()
count = len(df)
top = df.groupby('category')['amount'].sum().idxmax() if not df.empty else "-"

delta_str = None
if selected_month != "전체 기간" and available_months:
    try:
        current_idx = available_months.index(selected_month)
        if current_idx + 1 < len(available_months):
            prev_month_str = available_months[current_idx + 1]
            prev_df = full_df[full_df['date'].dt.strftime('%Y-%m') == prev_month_str]
            prev_total = prev_df['amount'].sum()
            
            diff = total - prev_total
            if diff > 0:
                delta_str = f"전월대비 {diff:,.0f}원 증가 🔺"
            elif diff < 0:
                delta_str = f"전월대비 {abs(diff):,.0f}원 감소 ⬇️"
            else:
                delta_str = "전월과 동일"
    except ValueError:
        pass

st.markdown("### 💡 이번 달 요약")
col1, col2, col3 = st.columns(3)

if delta_str:
    col1.metric("총 지출액", f"{total:,}원", delta=delta_str, delta_color="inverse")
else:
    col1.metric("총 지출액", f"{total:,}원")
    
col2.metric("총 결제 건수", f"{count}건")
col3.metric("최다 지출 카테고리", top)

st.divider()

# --- 4. 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📈 차트 분석", "📋 요약 및 랭킹", "📝 상세 내역 수정"])

# ==========================================
# TAB 1: 인터랙티브 차트
# ==========================================
with tab1:
    st.markdown("#### 📅 일별 지출 추이")
    
    def format_item(item, amount):
        short_item = item if len(item) <= 10 else item[:10] + ".."
        return f"{short_item}({amount:,})"

    daily_df = df.groupby('date').apply(
        lambda x: pd.Series({
            '총액': x['amount'].sum(),
            'top_items': ' / '.join([format_item(row['item'], row['amount']) for _, row in x.sort_values('amount', ascending=False).head(3).iterrows()])
        })
    ).reset_index()
    
    daily_df['총액_만'] = daily_df['총액'] / 10000

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=daily_df['date'],
        y=daily_df['총액_만'],
        mode='lines+markers',
        line=dict(color='#4361EE', width=3, shape='spline'),
        marker=dict(size=8, color='#4361EE', line=dict(width=2, color='white')),
        fill='tozeroy',
        fillcolor='rgba(67, 97, 238, 0.1)',
        customdata=daily_df[['총액', 'top_items']],
        hovertemplate=(
            "<b>총 지출: %{customdata[0]:,.0f}원</b><br>"
            "<span style='font-size:12px; color:gray;'>🏆 Top: %{customdata[1]}</span>"
            "<extra></extra>"
        )
    ))
    
    fig_line.update_layout(
        xaxis_title="",
        yaxis_title="지출 금액",
        yaxis=dict(tickformat=".0f", ticksuffix="만"),
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.95)", font_size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        height=400
    )
    st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})

    st.divider()

    st.markdown("#### 🍕 카테고리별 비중 및 증감")
    
    cat_df = df.groupby('category')['amount'].sum().reset_index()
    latest_date = df['date'].max()

    def get_change(category, current_amt, date_ref, period_type="Q"):
        if pd.isnull(date_ref): return "N/A"
        try:
            if period_type == "Q":
                prev_period = date_ref.to_period('Q') - 1
                prev_data = full_df[(full_df['date'].dt.to_period('Q') == prev_period) & (full_df['category'] == category)]
            else: 
                prev_period = date_ref.to_period('M') - 1
                prev_data = full_df[(full_df['date'].dt.to_period('M') == prev_period) & (full_df['category'] == category)]
            
            prev_amt = prev_data['amount'].sum()
            if prev_amt == 0: return "이전 데이터 없음"
            change = ((current_amt - prev_amt) / prev_amt) * 100
            return f"{change:+.1f}%"
        except:
            return "계산 불가"

    cat_df['전분기대비'] = cat_df.apply(lambda r: get_change(r['category'], r['amount'], latest_date, "Q"), axis=1)
    cat_df['전월대비'] = cat_df.apply(lambda r: get_change(r['category'], r['amount'], latest_date, "M"), axis=1)

    custom_colors = ['#FF9F40', '#FFCD56', '#4BC0C0', '#36A2EB', '#9966FF', '#FF6384', '#FDB45C', '#46BFBD', '#F7464A']

    fig_pie = go.Figure(data=[go.Pie(
        labels=cat_df['category'], 
        values=cat_df['amount'], 
        hole=0.55,  
        pull=[0.01] * len(cat_df),
        customdata=cat_df[['전월대비', '전분기대비']],
        hovertemplate=(
            "<b>%{label}</b><br><br>"
            "결제 금액: <b>%{value:,.0f}원</b><br>"
            "전체 비중: <b>%{percent:.1%}</b><br><br>"
            "전월대비: %{customdata[0]}<br>"
            "전분기비: %{customdata[1]}"
            "<extra></extra>"
        ),
        marker=dict(
            colors=custom_colors,
            line=dict(color='#FFFFFF', width=3)
        ),
        textposition='outside', 
        textinfo='label+percent',
        textfont=dict(size=14, color='#262730'), 
    )])

    fig_pie.update_layout(
        showlegend=False,
        height=550, 
        margin=dict(l=50, r=50, t=50, b=100),
        dragmode=False,
        hoverlabel=dict(
            bgcolor="white", 
            bordercolor="#E0E0E0",
            font_size=14,
            font_family="sans-serif"
        )
    )
    st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False}, theme=None)


# ==========================================
# TAB 2: 주간 요약 및 랭킹 표
# ==========================================
with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🗓️ 주차별 합산 지출")
        df_week = df.copy()
        df_week['주차(시작일)'] = df_week['date'].dt.to_period('W-MON').dt.start_time.dt.strftime('%Y-%m-%d (월)')
        weekly_summary = df_week.groupby('주차(시작일)').agg(
            지출건수=('id', 'count'),
            총합계=('amount', 'sum')
        ).reset_index()
        
        st.dataframe(
            weekly_summary, 
            column_config={"총합계": st.column_config.NumberColumn(format="%d원")},
            hide_index=True, 
            use_container_width=True
        )

    with col2:
        st.markdown("#### 🏆 최다 지출 내역 Top 10")
        top_expenses = df.sort_values('amount', ascending=False)[['date', 'item', 'category', 'amount']].head(10)
        top_expenses['date'] = top_expenses['date'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            top_expenses,
            column_config={
                "date": "날짜", "item": "내역", "category": "카테고리", 
                "amount": st.column_config.NumberColumn("금액", format="%d원")
            },
            hide_index=True,
            use_container_width=True
        )

# ==========================================
# TAB 3: 상세 내역 (수정 에디터) - 카테고리 필터 추가
# ==========================================
with tab3:
    st.caption("💡 특정 카테고리만 골라서 카드사 앱과 비교(크로스체크)해 보세요. 표 내용 수정 시 스크롤이 유지됩니다.")

    @fragment
    def expense_editor_section():
        current_df = st.session_state['dashboard_data']
        latest_categories = get_categories()

        # [신규 기능] 에디터 내부 카테고리 필터
        col_filter, _ = st.columns([1, 3])
        with col_filter:
            selected_editor_cat = st.selectbox("🏷️ 카테고리로 좁혀보기", ["전체보기"] + latest_categories, key="editor_cat_filter")

        # 필터 적용
        if selected_editor_cat != "전체보기":
            display_df = current_df[current_df['category'] == selected_editor_cat].copy()
        else:
            display_df = current_df.copy()

        edited_df = st.data_editor(
            display_df,
            column_config={
                "id": None,
                "spender": st.column_config.SelectboxColumn("사용자", options=["공동", "남편", "아내", "아이"]),
                "amount": st.column_config.NumberColumn("금액", format="%d원"),
                "date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
                "category": st.column_config.SelectboxColumn("카테고리", options=latest_categories, required=True),
            },
            hide_index=True,
            num_rows="dynamic",
            key="editor_fragment",
            use_container_width=True
        )

        editor_state = st.session_state.get("editor_fragment")
        if editor_state:
            updates = editor_state.get("edited_rows", {})
            deletes = editor_state.get("deleted_rows", [])
            has_changes = False

            if updates:
                for idx, changes in updates.items():
                    idx = int(idx)
                    # 화면에 보이는 필터링된 DF의 순서를 기반으로 '실제 DB ID'를 찾아냄 (데이터 꼬임 방지)
                    real_id = display_df.iloc[idx]['id']
                    
                    for col, val in changes.items():
                        if col == 'date': val = str(val).split('T')[0]
                        # 1. DB 업데이트
                        update_expense(real_id, col, val)
                        
                        # 2. 메모리(전체 DF)에서 ID로 정확히 찾아서 업데이트
                        st.session_state['dashboard_data'].loc[st.session_state['dashboard_data']['id'] == real_id, col] = val
                    has_changes = True

            if deletes:
                for idx in sorted(deletes, reverse=True):
                    real_id = display_df.iloc[idx]['id']
                    # 1. DB 삭제
                    delete_expense(real_id)
                    # 2. 메모리(전체 DF)에서 ID 기반으로 안전하게 행 삭제
                    st.session_state['dashboard_data'] = st.session_state['dashboard_data'][st.session_state['dashboard_data']['id'] != real_id]
                
                st.session_state['dashboard_data'].reset_index(drop=True, inplace=True)
                has_changes = True

            if has_changes:
                st.toast("✅ 저장되었습니다! (상단 차트 갱신은 F5)")
                
    expense_editor_section()