import streamlit as st
import pandas as pd
import sys
import os
import plotly.express as px
import plotly.graph_objects as go

try:
    from streamlit import fragment
except ImportError:
    try:
        from streamlit import experimental_fragment as fragment
    except ImportError:
        def fragment(func): return func

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import (
    load_data, delete_expense, update_expense, get_available_months, 
    DB_NAME, get_categories, add_category, delete_category_safe,
    get_category_mapping # DB에서 직접 매핑을 가져옵니다
)

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

# --- 1. 사이드바 (카테고리 성향 선택 기능 추가) ---
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
        # [수정] 카테고리 추가 시 소비 성향도 함께 받도록 UI 추가
        cat_type = st.radio("소비 성향", ["필수소비 (Needs)", "선택소비 (Wants)"], horizontal=True)
        new_cat = st.text_input("새 카테고리 추가", placeholder="예: 반려동물")
        
        if st.button("추가"):
            if new_cat and add_category(new_cat, cat_type):
                st.success(f"'{new_cat}' ({cat_type}) 추가됨")
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

# --- 2. 데이터 로드 및 매핑 ---
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
    st.info("데이터가 없습니다.")
    st.stop()

# [핵심] 하드코딩된 리스트 대신, DB에서 매핑을 불러와 동적으로 소비성향 부여
category_mapping = get_category_mapping()
df['소비성향'] = df['category'].map(lambda x: category_mapping.get(x, "미분류"))

# --- 3. 통계 (상단) ---
total = df['amount'].sum()
essential_total = df[df['소비성향'] == '필수소비 (Needs)']['amount'].sum()
discretionary_total = df[df['소비성향'] == '선택소비 (Wants)']['amount'].sum()

delta_str = None
if selected_month != "전체 기간" and available_months:
    try:
        current_idx = available_months.index(selected_month)
        if current_idx + 1 < len(available_months):
            prev_month_str = available_months[current_idx + 1]
            prev_df = full_df[full_df['date'].dt.strftime('%Y-%m') == prev_month_str]
            prev_total = prev_df['amount'].sum()
            
            diff = total - prev_total
            if diff > 0: delta_str = f"전월대비 {diff:,.0f}원 증가 🔺"
            elif diff < 0: delta_str = f"전월대비 {abs(diff):,.0f}원 감소 ⬇️"
            else: delta_str = "전월과 동일"
    except ValueError: pass

st.markdown("### 💡 소비 성향 요약")
c1, c2, c3 = st.columns(3)

if delta_str:
    c1.metric("💰 총 지출액", f"{total:,}원", delta=delta_str, delta_color="inverse")
else:
    c1.metric("💰 총 지출액", f"{total:,}원")

ess_percent = (essential_total / total * 100) if total > 0 else 0
disc_percent = (discretionary_total / total * 100) if total > 0 else 0

c2.metric("🛡️ 필수소비 (Needs)", f"{essential_total:,}원", f"비중: {ess_percent:.1f}%", delta_color="off")
c3.metric("🎯 선택소비 (Wants)", f"{discretionary_total:,}원", f"비중: {disc_percent:.1f}%", delta_color="off")

st.divider()

# --- 4. 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📈 소비 성향 & 추이", "📋 요약 및 랭킹", "📝 상세 내역 수정"])

with tab1:
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("#### ⚖️ 필수 vs 선택 소비 비율")
        type_df = df.groupby('소비성향')['amount'].sum().reset_index()
        fig_type = go.Figure(data=[go.Pie(
            labels=type_df['소비성향'], 
            values=type_df['amount'], 
            hole=0.6,
            marker=dict(colors=['#FF6B6B', '#4ECDC4', '#FFE66D'], line=dict(color='#FFFFFF', width=2)),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate="<b>%{label}</b><br>금액: %{value:,.0f}원<extra></extra>"
        )])
        fig_type.update_layout(height=400, showlegend=False, margin=dict(t=30, b=30))
        st.plotly_chart(fig_type, use_container_width=True, config={'displayModeBar': False})
        
    with col_chart2:
        st.markdown("#### 🍕 세부 카테고리 비중")
        cat_df = df.groupby('category')['amount'].sum().reset_index()
        custom_colors = ['#FF9F40', '#FFCD56', '#4BC0C0', '#36A2EB', '#9966FF', '#FF6384', '#FDB45C', '#46BFBD', '#F7464A']
        fig_pie = go.Figure(data=[go.Pie(
            labels=cat_df['category'], 
            values=cat_df['amount'], 
            hole=0.4,
            marker=dict(colors=custom_colors, line=dict(color='#FFFFFF', width=2)),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate="<b>%{label}</b><br>금액: %{value:,.0f}원<extra></extra>"
        )])
        fig_pie.update_layout(height=400, showlegend=False, margin=dict(t=30, b=30))
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

    st.divider()
    
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
        x=daily_df['date'], y=daily_df['총액_만'], mode='lines+markers',
        line=dict(color='#4361EE', width=3, shape='spline'),
        marker=dict(size=8, color='#4361EE', line=dict(width=2, color='white')),
        fill='tozeroy', fillcolor='rgba(67, 97, 238, 0.1)',
        customdata=daily_df[['총액', 'top_items']],
        hovertemplate="<b>총 지출: %{customdata[0]:,.0f}원</b><br><span style='font-size:12px; color:gray;'>🏆 Top: %{customdata[1]}</span><extra></extra>"
    ))
    fig_line.update_layout(yaxis=dict(tickformat=".0f", ticksuffix="만"), hovermode="x unified", dragmode=False, height=350, margin=dict(t=10, b=10))
    st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})


with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🗓️ 주차별 합산 지출")
        df_week = df.copy()
        df_week['주차(시작일)'] = df_week['date'].dt.to_period('W-MON').dt.start_time.dt.strftime('%Y-%m-%d (월)')
        weekly_summary = df_week.groupby('주차(시작일)').agg(지출건수=('id', 'count'), 총합계=('amount', 'sum')).reset_index()
        st.dataframe(weekly_summary, column_config={"총합계": st.column_config.NumberColumn(format="%d원")}, hide_index=True, use_container_width=True)

    with col2:
        st.markdown("#### 🏆 최다 지출 내역 Top 10")
        top_expenses = df.sort_values('amount', ascending=False)[['date', 'item', 'category', 'amount']].head(10)
        top_expenses['date'] = top_expenses['date'].dt.strftime('%Y-%m-%d')
        st.dataframe(top_expenses, column_config={"amount": st.column_config.NumberColumn("금액", format="%d원")}, hide_index=True, use_container_width=True)


with tab3:
    st.caption("💡 특정 카테고리만 골라서 카드사 앱과 비교(크로스체크)해 보세요. 표 내용 수정 시 스크롤이 유지됩니다.")

    @fragment
    def expense_editor_section():
        current_df = st.session_state['dashboard_data']
        latest_categories = get_categories()
        # 매핑 재조회
        current_mapping = get_category_mapping()

        col_filter, _ = st.columns([1, 3])
        with col_filter:
            selected_editor_cat = st.selectbox("🏷️ 카테고리로 좁혀보기", ["전체보기"] + latest_categories, key="editor_cat_filter")

        if selected_editor_cat != "전체보기":
            display_df = current_df[current_df['category'] == selected_editor_cat].copy()
        else:
            display_df = current_df.copy()

        edited_df = st.data_editor(
            display_df,
            column_config={
                "id": None,
                "소비성향": st.column_config.TextColumn("소비성향", disabled=True), # 소비성향을 보여주되 수정은 불가능하게 설정
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
                    real_id = display_df.iloc[idx]['id']
                    
                    for col, val in changes.items():
                        if col == 'date': val = str(val).split('T')[0]
                        # 1. DB 업데이트
                        update_expense(real_id, col, val)
                        
                        # 2. 메모리(전체 DF) 업데이트
                        st.session_state['dashboard_data'].loc[st.session_state['dashboard_data']['id'] == real_id, col] = val
                        
                        # [핵심] 만약 수정한 항목이 '카테고리'라면, '소비성향'도 즉시 알맞게 바꿔줌
                        if col == 'category':
                            new_type = current_mapping.get(val, "미분류")
                            st.session_state['dashboard_data'].loc[st.session_state['dashboard_data']['id'] == real_id, '소비성향'] = new_type

                    has_changes = True

            if deletes:
                for idx in sorted(deletes, reverse=True):
                    real_id = display_df.iloc[idx]['id']
                    delete_expense(real_id)
                    st.session_state['dashboard_data'] = st.session_state['dashboard_data'][st.session_state['dashboard_data']['id'] != real_id]
                
                st.session_state['dashboard_data'].reset_index(drop=True, inplace=True)
                has_changes = True

            if has_changes:
                st.toast("✅ 저장되었습니다! (상단 차트 갱신은 F5)")
                
    expense_editor_section()