import plotly.graph_objects as go


def make_radar_chart(df, theta_cols) -> go.Figure:
    fig = go.Figure()
    for _, row in df.iterrows():
        fig.add_trace(go.Scatterpolar(
            r=[row[c] for c in theta_cols],
            theta=theta_cols,
            fill="toself",
            name=row["지역"],
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
    )
    return fig


def make_gap_chart(gap_df, equity_series=None, target_year=2029) -> go.Figure:
    # 실제 gap_df 컬럼: 연도 / 의정부 신일유토빌 / 성북구 길음뉴타운 / 내 자기자본
    x_col      = "연도"
    ui_col     = "의정부 신일유토빌"
    sb_col     = "성북구 길음뉴타운"
    equity_col = "내 자기자본"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=gap_df[x_col], y=gap_df[sb_col],
        mode="lines+markers", name=sb_col,
    ))
    fig.add_trace(go.Scatter(
        x=gap_df[x_col], y=gap_df[ui_col],
        mode="lines+markers", name=ui_col,
    ))
    fig.add_trace(go.Scatter(
        x=gap_df[x_col], y=gap_df[equity_col],
        mode="lines+markers", name=equity_col,
        line=dict(dash="dot"),
    ))

    fig.add_vline(x=target_year, line_dash="dash", line_color="red",
                  annotation_text=f"{target_year}년 목표", annotation_position="top right")

    target_row = gap_df[gap_df[x_col] == target_year]
    if not target_row.empty:
        row = target_row.iloc[0]
        gap = row[sb_col] - row[ui_col]
        fig.add_annotation(
            x=target_year, y=row[sb_col],
            text=f"Gap {gap:.2f}억",
            showarrow=True, arrowhead=2, ax=40, ay=-20,
            font=dict(size=12), bgcolor="white",
        )

    fig.update_layout(
        xaxis_title="연도",
        yaxis_title="가격 / 자기자본 (억원)",
        showlegend=True,
    )
    return fig


def make_equity_progress_chart(monthly_data) -> go.Figure:
    years = [d["year"] for d in monthly_data]
    equities = [d["equity"] for d in monthly_data]

    fig = go.Figure(go.Scatter(
        x=years, y=equities,
        mode="lines+markers",
        name="자기자본",
    ))
    fig.update_layout(
        xaxis_title="연도",
        yaxis_title="억원",
    )
    return fig
