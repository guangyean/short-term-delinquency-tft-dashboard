from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = Path("dataset.xlsx")
COMPANY_ORDER = ["전북은행", "광주은행", "우리캐피탈"]

LINE_STYLE_MAP = {
    "연체전이율 0→1": {"label": "0->1회차(%)", "color": "rgb(157,195,230)", "dash": "dot", "width": 2.13},
    "연체전이율 0→2": {"label": "0->2회차(%)", "color": "rgb(165,165,165)", "dash": "solid", "width": 3.0},
    "연체전이율 1→2": {"label": "1->2회차(%)", "color": "rgb(237,125,49)", "dash": "dot", "width": 2.13},
    "목표(0->2)": {"label": "목표(0->2)", "color": "rgb(255,0,0)", "dash": "solid", "width": 3.0},
    "실질연체율": {"label": "실질연체율(30+,당해상각)", "color": "rgb(91,155,213)", "dash": "solid", "width": 3.0},
    "단기정상화율 5일 內": {"label": "정상화율(5일)", "color": "rgb(91,155,213)", "dash": "solid", "width": 3.0},
    "단기정상화율 7일 內": {"label": "정상화율(7일)", "color": "rgb(237,125,49)", "dash": "solid", "width": 3.0},
    "단기정상화율 10일 內": {"label": "정상화율(10일)", "color": "rgb(165,165,165)", "dash": "solid", "width": 3.0},
    "단기정상화율 15일 內": {"label": "정상화율(15일)", "color": "rgb(237,125,49)", "dash": "solid", "width": 3.0},
    "단기정상화율 20일 內": {"label": "정상화율(20일)", "color": "rgb(165,165,165)", "dash": "solid", "width": 3.0},
}


def get_line_style(metric: str) -> dict:
    return LINE_STYLE_MAP.get(metric, {"label": metric, "color": None, "dash": "solid", "width": 2.25})

def ym_to_label(ym: str) -> str:
    ym = str(ym)
    return f"{ym[:4]}.{ym[4:]}"

@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    for col in ["년월", "자회사구분", "Section", "구분", "항목"]:
        df[col] = df[col].astype(str).str.strip()
    df["값_raw"] = df["값"]
    df["값"] = pd.to_numeric(df["값"], errors="coerce")

    percent_keywords = ["전이율", "단기정상화율", "실질연체율"]
    mask = df["항목"].astype(str).apply(lambda x: any(k in x for k in percent_keywords))
    df.loc[mask, "값"] = df.loc[mask, "값"] * 100
    return df


def company_list(df: pd.DataFrame) -> list[str]:
    in_data = df["자회사구분"].dropna().unique().tolist()
    return [c for c in COMPANY_ORDER if c in in_data]


def get_company_products(df: pd.DataFrame, company: str) -> list[str]:
    company_prod = df[(df["자회사구분"] == company) & (df["Section"] == "상품별현황")]
    return company_prod["구분"].dropna().drop_duplicates().tolist()


def shift_prev_month_str(ym: str) -> str:
    year = int(str(ym)[:4])
    month = int(str(ym)[4:6])
    month -= 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year}{month:02d}"


def build_compact_labels(ym_list: list[str], shift_x_label: bool = False) -> list[str]:
    labels = []
    prev_year = None
    for i, ym in enumerate(ym_list):
        base_ym = shift_prev_month_str(ym) if shift_x_label else ym
        yy = str(base_ym)[2:4]
        mm = int(str(base_ym)[4:6])
        labels.append(f"'{yy}.{mm}월" if i == 0 or yy != prev_year else f"{mm}월")
        prev_year = yy
    return labels


def keep_recent_n_months(series_df: pd.DataFrame, n: int = 13) -> pd.DataFrame:
    months = sorted(series_df["년월"].dropna().astype(str).unique().tolist())
    return series_df[series_df["년월"].isin(months[-n:])].copy()


def prev_month(df: pd.DataFrame, base_ym: str) -> str | None:
    months = sorted(df["년월"].dropna().astype(str).unique())
    if base_ym not in months:
        return None
    idx = months.index(base_ym)
    return None if idx == 0 else months[idx - 1]


def get_metric_value(prod_df: pd.DataFrame, product: str, ym: str, metric_name: str) -> float | None:
    temp = prod_df[(prod_df["구분"] == product) & (prod_df["년월"] == ym) & (prod_df["항목"] == metric_name)]
    if temp.empty:
        return None
    val = temp["값"].iloc[0]
    return None if pd.isna(val) else float(val)


def get_norm_metric_name(prod_df: pd.DataFrame, product: str) -> str | None:
    names = prod_df.loc[
        (prod_df["구분"] == product) & (prod_df["항목"].str.contains("단기정상화율", na=False)),
        "항목",
    ].dropna().unique().tolist()
    for name in ["단기정상화율 20일 內", "단기정상화율 10일 內"]:
        if name in names:
            return name
    return names[0] if names else None


def classify_change(delta: float | None, favorable_when: str, stable_threshold: float = 0.05) -> str:
    if delta is None or pd.isna(delta):
        return "중립"
    if abs(delta) <= stable_threshold:
        return "유지"
    if favorable_when == "down":
        return "양호" if delta < 0 else "악화"
    return "양호" if delta > 0 else "악화"


def summarize_overall(statuses: list[str]) -> tuple[str, str]:
    valid = [s for s in statuses if s in ["양호", "유지", "악화"]]
    
    if not valid:
        return "❔", "데이터 부족"
        
    bad_cnt = valid.count("악화")
    good_cnt = valid.count("양호")
    
    if bad_cnt >= 2:
        return "🔴", "전반적 악화"
    elif bad_cnt == 1:
        if good_cnt > 0:
            return "🟡", "일부 지표 악화"
        else:
            return "🟡", "전월대비 소폭 악화"
    else:
        if good_cnt >= 2:
            return "🔵", "전반적 개선"
        elif good_cnt == 1:
            return "🟢", "전월대비 양호"
        else:
            return "⚪", "전월 수준 유지"


def fmt_pp(delta: float | None, digits: int = 2) -> str:
    if delta is None or pd.isna(delta):
        return "비교 불가"
    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "-"
    return f"{abs(delta):.{digits}f}%p {arrow}" if delta != 0 else f"0.00%p {arrow}"


def build_summary(prod_df: pd.DataFrame, promo_df: pd.DataFrame, company: str, product: str, base_ym: str) -> dict:
    pm = prev_month(prod_df, base_ym)
    metrics = {
        "연체전이율 0→2": get_metric_value(prod_df, product, base_ym, "연체전이율 0→2"),
        "연체전이율 0→1": get_metric_value(prod_df, product, base_ym, "연체전이율 0→1"),
        "연체전이율 1→2": get_metric_value(prod_df, product, base_ym, "연체전이율 1→2"),
        "실질연체율": get_metric_value(prod_df, product, base_ym, "실질연체율"),
    }
    prev_metrics = {
        k: (get_metric_value(prod_df, product, pm, k) if pm else None)
        for k in metrics.keys()
    }
    norm_metric = get_norm_metric_name(prod_df, product)
    metrics["단기정상화율"] = get_metric_value(prod_df, product, base_ym, norm_metric) if norm_metric else None
    prev_metrics["단기정상화율"] = get_metric_value(prod_df, product, pm, norm_metric) if (norm_metric and pm) else None

    deltas = {k: (metrics[k] - prev_metrics[k]) if metrics[k] is not None and prev_metrics[k] is not None else None for k in metrics.keys()}
    status_roll = classify_change(deltas["연체전이율 0→2"], favorable_when="down")
    status_30 = classify_change(deltas["실질연체율"], favorable_when="down")
    status_norm = classify_change(deltas["단기정상화율"], favorable_when="up")
    promo_base = promo_df[(promo_df["자회사구분"] == company) & (promo_df["년월"] == base_ym)]
    promo_text = []
    for team in promo_base["구분"].dropna().unique().tolist():
        achieved = promo_base[(promo_base["구분"] == team) & (promo_base["항목"] == "달성여부")]
        if achieved.empty:
            continue
        val = str(achieved["값_raw"].iloc[0]).strip()
        if val == "Y":
            promo_text.append(f"{team} 목표 달성")
        elif val == "N":
            promo_text.append(f"{team} 목표 미달성")
    signal, text = summarize_overall([status_roll, status_30, status_norm])
    return {
        "overall_signal": signal,
        "overall_text": text,
        "metric_name_norm": norm_metric,
        "deltas": deltas,
        "promo_summary": ", ".join(promo_text) if promo_text else "프로모션 데이터 없음",
    }


def render_summary_card(prod_df: pd.DataFrame, promo_df: pd.DataFrame, company: str, product: str, base_ym: str):
    summary = build_summary(prod_df, promo_df, company, product, base_ym)
    st.markdown(f"### {product}")
    st.markdown(
        f"""
**(종합)** {summary['overall_signal']} {summary['overall_text']}  
**연체전이율**  
- 0→2 전이율: 전월대비 {fmt_pp(summary['deltas']['연체전이율 0→2'])}  
- 0→1 전이율: 전월대비 {fmt_pp(summary['deltas']['연체전이율 0→1'])}  
- 1→2 전이율: 전월대비 {fmt_pp(summary['deltas']['연체전이율 1→2'])}  
**30D+연체율**  
- 전월대비 {fmt_pp(summary['deltas']['실질연체율'])}  
**단기정상화율**  
- {summary['metric_name_norm'] or '기준 없음'} 기준, 전월대비 {fmt_pp(summary['deltas']['단기정상화율'])}  
**프로모션**  
- {summary['promo_summary']}
"""
    )


def make_line_chart(series_df: pd.DataFrame, title: str, shift_x_label: bool = False, add_target_line: bool = False) -> go.Figure:
    series_df = keep_recent_n_months(series_df, 13)
    fig = go.Figure()
    if series_df.empty:
        fig.update_layout(title=title, height=300)
        return fig

    metric_order = [
        "연체전이율 0→2", "연체전이율 0→1", "연체전이율 1→2",
        "실질연체율",
        "단기정상화율 5일 內", "단기정상화율 7일 內", "단기정상화율 10일 內",
        "단기정상화율 15일 內", "단기정상화율 20일 內",
    ]
    metric_list = [m for m in metric_order if m in series_df["항목"].dropna().unique().tolist()]
    annotations = []

    y_max = 0.0
    y_min = float('inf')
    y2_max = 0.0
    y2_min = float('inf')
    has_y2 = False

    for i, metric in enumerate(metric_list):
        temp = series_df[series_df["항목"] == metric].sort_values("년월").copy()
        temp["x_label"] = build_compact_labels(temp["년월"].astype(str).tolist(), shift_x_label=shift_x_label)

        if "단기정상화율" in metric:
            has_15 = "단기정상화율 15일 內" in metric_list
            has_20 = "단기정상화율 20일 內" in metric_list
            if has_15 and has_20:
                norm_map = {
                    "단기정상화율 10일 內": {"label": "정상화율(10일)", "color": "rgb(91,155,213)", "dash": "solid", "width": 3.0},
                    "단기정상화율 15일 內": {"label": "정상화율(15일)", "color": "rgb(237,125,49)", "dash": "solid", "width": 3.0},
                    "단기정상화율 20일 內": {"label": "정상화율(20일)", "color": "rgb(165,165,165)", "dash": "solid", "width": 3.0},
                }
            else:
                norm_map = {
                    "단기정상화율 5일 內": {"label": "정상화율(5일)", "color": "rgb(91,155,213)", "dash": "solid", "width": 3.0},
                    "단기정상화율 7일 內": {"label": "정상화율(7일)", "color": "rgb(237,125,49)", "dash": "solid", "width": 3.0},
                    "단기정상화율 10일 內": {"label": "정상화율(10일)", "color": "rgb(165,165,165)", "dash": "solid", "width": 3.0},
                }
            style = norm_map.get(metric, get_line_style(metric))
        else:
            style = get_line_style(metric)

        axis_ref = "y2" if (title == "연체전이율" and metric == "연체전이율 1→2") else "y"

        valid_vals = temp["값"].dropna()
        if not valid_vals.empty:
            curr_max = valid_vals.max()
            curr_min = valid_vals.min()
            if axis_ref == "y2":
                has_y2 = True
                if curr_max > y2_max: y2_max = curr_max
                if curr_min < y2_min: y2_min = curr_min
            else:
                if curr_max > y_max: y_max = curr_max
                if curr_min < y_min: y_min = curr_min

        temp["전월값"] = temp["값"].shift(1)
        temp["증감"] = temp["값"] - temp["전월값"]
        def format_hover(row):
            if pd.isna(row["증감"]) or row["증감"] == 0: return f"{row['값']:.2f}"
            arrow = "▲" if row["증감"] > 0 else "▼"
            return f"{row['값']:.2f} ({arrow}{abs(row['증감']):.2f}p)"
        temp["hover_text"] = temp.apply(format_hover, axis=1)

        fig.add_trace(go.Scatter(
            x=temp["x_label"], y=temp["값"], mode="lines+markers", name=style["label"],
            line=dict(color=style["color"], dash=style["dash"], width=style["width"]),
            marker=dict(size=6, color=style["color"]), yaxis=axis_ref,
            text=temp["hover_text"], hovertemplate="%{text}"
        ))

        base_shift = 10 + (i * 12)
        last_two = temp.tail(2)
        for _, row in last_two.iterrows():
            annotations.append(dict(
                x=row["x_label"], y=row["값"], xref="x", yref=axis_ref,
                text=f"{row['값']:.2f}", showarrow=False, textangle=0,
                yshift=base_shift,
                font=dict(size=11, color=style["color"]), xanchor="center", yanchor="bottom",
                bgcolor="rgba(255,255,255,0.7)"
            ))

    if add_target_line:
        temp = series_df.sort_values("년월").copy().drop_duplicates(subset=["년월"])
        temp["x_label"] = build_compact_labels(temp["년월"].astype(str).tolist(), shift_x_label=shift_x_label)
        style = get_line_style("목표(0->2)")

        y_max = max(y_max, 0.50)
        y_min = min(y_min, 0.50) if y_min != float('inf') else 0.50

        fig.add_trace(go.Scatter(
            x=temp["x_label"], y=[0.50] * len(temp), mode="lines", name=style["label"],
            line=dict(color=style["color"], dash=style["dash"], width=style["width"]), yaxis="y",
            hovertemplate="0.50"
        ))

        annotations.append(dict(
            x=temp["x_label"].iloc[-1], y=0.50, xref="x", yref="y", text="0.50",
            showarrow=False, textangle=0, yshift=10,
            font=dict(size=11, color=style["color"]), xanchor="center", yanchor="bottom",
            bgcolor="rgba(255,255,255,0.7)"
        ))

    if y_min == float('inf'): y_min = 0.0
    if y2_min == float('inf'): y2_min = 0.0

    if has_y2:
        # Separate the lines: Primary (y) in bottom half, Secondary (y2) in top half
        y_span = (y_max - y_min) / 0.35 if y_max > y_min else 2.0
        y_bottom = y_min - y_span * 0.10
        if y_min >= 0 and y_bottom < 0:
            y_bottom = 0.0
            y_top = y_max / 0.45 if y_max > 0 else 1.0
        else:
            y_top = y_bottom + y_span

        y2_span = (y2_max - y2_min) / 0.35 if y2_max > y2_min else 20.0
        y2_bottom = y2_min - y2_span * 0.45
        y2_top = y2_bottom + y2_span
    else:
        # Normal scaling (all in one axis)
        y_span = (y_max - y_min) / 0.70 if y_max > y_min else 2.0
        y_bottom = y_min - y_span * 0.10
        if y_min >= 0 and y_bottom < 0:
            y_bottom = 0.0
            y_top = y_max / 0.80 if y_max > 0 else 1.0
        else:
            y_top = y_bottom + y_span

    layout = dict(
        title=title, height=350, margin=dict(l=20, r=20, t=50, b=80), xaxis_title=None,
        xaxis=dict(tickangle=0),
        yaxis=dict(title=None, showticklabels=False, showgrid=False, zeroline=False, range=[y_bottom, y_top]),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
        legend_title="", plot_bgcolor="white", paper_bgcolor="white",
        showlegend=True, hovermode="x unified", annotations=annotations
    )
    
    if has_y2:
        layout["yaxis2"] = dict(title=None, overlaying="y", side="right", range=[y2_bottom, y2_top], showgrid=False, showticklabels=False)

    fig.update_layout(**layout)
    return fig


def render_promo_table(promo_show: pd.DataFrame):
    month_cols = sorted(promo_show["년월"].dropna().astype(str).unique().tolist())
    group_order = promo_show["구분"].dropna().drop_duplicates().tolist()
    wide = promo_show.pivot_table(index=["구분", "항목"], columns="년월", values="값_raw", aggfunc="first")
    normal_order = ["목표(정상화율, %)", "실적(정상화율, %)", "달성여부", "지급액(백만원)"]
    amt_order = ["목표(연체증가액, 백만원)", "실적(연체증가액, 백만원)", "달성여부", "지급액(백만원)"]
    display_rows = []
    for grp in group_order:
        grp_items = promo_show.loc[promo_show["구분"] == grp, "항목"].dropna().drop_duplicates().tolist()
        if "목표(정상화율, %)" in grp_items:
            item_order = [x for x in normal_order if x in grp_items]
        elif "목표(연체증가액, 백만원)" in grp_items:
            item_order = [x for x in amt_order if x in grp_items]
        else:
            item_order = grp_items
        for item in item_order:
            row = {"구분": grp, "항목": item}
            for m in month_cols:
                try:
                    val = wide.loc[(grp, item), m]
                except KeyError:
                    val = ""
                if pd.isna(val) or str(val).strip() in ["0", "0.0", "nan", "None"]:
                    val = ""
                else:
                    raw_str = str(val).strip().upper()
                    if item == "달성여부" and raw_str == "Y":
                        val = "<span style='color:blue; font-weight:bold;'>Y</span>"
                    elif item == "달성여부" and raw_str == "N":
                        val = "<span style='color:red; font-weight:bold;'>N</span>"
                    else:
                        try:
                            num = float(val)
                            if item == "달성여부":
                                pass
                            elif "지급액" in item or "증가액" in item:
                                val = f"{num:,.0f}" if float(num).is_integer() else f"{num:.1f}"
                            elif "정상화율" in item:
                                val = f"{num:.1f}"
                            else:
                                val = str(val)
                        except Exception:
                            val = str(val)
                row[m] = val
            display_rows.append(row)
    group_counts = {}
    for row in display_rows:
        group_counts[row["구분"]] = group_counts.get(row["구분"], 0) + 1
    html = ["<table style='border-collapse:collapse; width:100%; font-size:14px;'>", "<thead>", "<tr style='background:#f2f2f2; text-align:center;'>", "<th style='border:1px solid #999; padding:6px;'>구분</th>", "<th style='border:1px solid #999; padding:6px;'>항목</th>"]
    for m in month_cols:
        html.append(f"<th style='border:1px solid #999; padding:6px;'>{m}</th>")
    html += ["</tr>", "</thead>", "<tbody>"]
    printed_groups = set()
    for row in display_rows:
        grp = row["구분"]
        html.append("<tr>")
        if grp not in printed_groups:
            html.append(f"<td rowspan='{group_counts[grp]}' style='border:1px solid #999; padding:6px; text-align:center;'>{grp}</td>")
            printed_groups.add(grp)
        html.append(f"<td style='border:1px solid #999; padding:6px;'>{row['항목']}</td>")
        for m in month_cols:
            html.append(f"<td style='border:1px solid #999; padding:6px; text-align:center;'>{row[m]}</td>")
        html.append("</tr>")
    html += ["</tbody>", "</table>"]
    st.markdown("".join(html), unsafe_allow_html=True)


def render_fund_table(fund_df: pd.DataFrame):
    month_cols = sorted(fund_df["년월"].dropna().astype(str).unique().tolist())
    wide = fund_df.pivot_table(index=["구분", "항목"], columns="년월", values="값", aggfunc="first")
    row_order = [("신청", "건수(건)"), ("신청", "금액(억원)"), ("매각", "건수(건)"), ("매각", "금액(억원)"), ("매각", "대금(억원)"), ("매각", "률(%)")]
    display_rows = []
    for grp, item in row_order:
        row = {"구분": grp, "항목": item}
        for m in month_cols:
            try:
                val = wide.loc[(grp, item), m]
            except KeyError:
                val = ""
            if pd.isna(val):
                val = ""
            else:
                try:
                    num = float(val)
                    if item == "률(%)":
                        val = f"{num:.1f}"
                    elif item == "건수(건)":
                        val = f"{num:,.0f}"
                    else:
                        val = f"{num:.1f}"
                except Exception:
                    pass
            row[m] = val
        display_rows.append(row)
    html = ["<table style='border-collapse:collapse; width:100%; font-size:14px;'>", "<thead>", "<tr style='background:#f2f2f2; text-align:center;'>", "<th style='border:1px solid #999; padding:6px;'>구분</th>", "<th style='border:1px solid #999; padding:6px;'>항목</th>"]
    for m in month_cols:
        html.append(f"<th style='border:1px solid #999; padding:6px;'>{m}</th>")
    html += ["</tr>", "</thead>", "<tbody>"]
    for idx, row in enumerate(display_rows):
        html.append("<tr>")
        if idx == 0:
            html.append("<td rowspan='2' style='border:1px solid #999; padding:6px; text-align:center;'>신청</td>")
        elif idx == 2:
            html.append("<td rowspan='4' style='border:1px solid #999; padding:6px; text-align:center;'>매각</td>")
        html.append(f"<td style='border:1px solid #999; padding:6px;'>{row['항목']}</td>")
        for m in month_cols:
            html.append(f"<td style='border:1px solid #999; padding:6px; text-align:center;'>{row[m]}</td>")
        html.append("</tr>")
    html += ["</tbody>", "</table>"]
    st.markdown("".join(html), unsafe_allow_html=True)


def render_debt_adjust_table(adj_df: pd.DataFrame):
    month_cols = sorted(adj_df["년월"].dropna().astype(str).unique().tolist())
    wide = adj_df.pivot_table(index=["구분", "항목"], columns="년월", values="값", aggfunc="first")
    row_order = [("신청", "건수"), ("신청", "금액(억원)"), ("승인", "건수"), ("승인", "금액(억원)"), ("승인", "율(금액,%)"), ("실행", "건수"), ("실행", "금액(억원)"), ("실행", "율(금액,%)")]
    display_rows = []
    for grp, item in row_order:
        row = {"구분": grp, "항목": item}
        for m in month_cols:
            try:
                val = wide.loc[(grp, item), m]
            except KeyError:
                val = ""
            if pd.isna(val):
                val = ""
            else:
                try:
                    num = float(val)
                    if item == "건수":
                        val = f"{num:,.0f}"
                    elif item == "율(금액,%)":
                        val = f"{num:.1f}%"
                    else:
                        val = f"{num:.1f}"
                except Exception:
                    pass
            row[m] = val
        display_rows.append(row)
    html = ["<table style='border-collapse:collapse; width:100%; font-size:14px;'>", "<thead>", "<tr style='background:#f2f2f2; text-align:center;'>", "<th style='border:1px solid #999; padding:6px; text-align:center;'>구분</th>", "<th style='border:1px solid #999; padding:6px; text-align:center;'>항목</th>"]
    for m in month_cols:
        html.append(f"<th style='border:1px solid #999; padding:6px; text-align:center;'>{m}</th>")
    html += ["</tr>", "</thead>", "<tbody>"]
    for idx, row in enumerate(display_rows):
        html.append("<tr>")
        if idx == 0:
            html.append("<td rowspan='2' style='border:1px solid #999; padding:6px; text-align:center;'>신청</td>")
        elif idx == 2:
            html.append("<td rowspan='3' style='border:1px solid #999; padding:6px; text-align:center;'>승인</td>")
        elif idx == 5:
            html.append("<td rowspan='3' style='border:1px solid #999; padding:6px; text-align:center;'>실행</td>")
        html.append(f"<td style='border:1px solid #999; padding:6px;'>{row['항목']}</td>")
        for m in month_cols:
            html.append(f"<td style='border:1px solid #999; padding:6px; text-align:center;'>{row[m]}</td>")
        html.append("</tr>")
    html += ["</tbody>", "</table>"]
    st.markdown("".join(html), unsafe_allow_html=True)


def render_product_section(df, company, base_ym, product):
    prod_df = df[(df["자회사구분"] == company) & (df["Section"] == "상품별현황")].copy()

    st.markdown(f"### {product}")

    c1, c2, c3 = st.columns(3)

    roll_metrics = ["연체전이율 0→2", "연체전이율 0→1", "연체전이율 1→2"]
    roll_df = prod_df[(prod_df["구분"] == product) & (prod_df["항목"].isin(roll_metrics))].copy()
    d30_df = prod_df[(prod_df["구분"] == product) & (prod_df["항목"] == "실질연체율")].copy()
    norm_df = prod_df[(prod_df["구분"] == product) & (prod_df["항목"].str.contains("단기정상화율", na=False))].copy()

    with c1:
        st.plotly_chart(
            make_line_chart(roll_df, "연체전이율", shift_x_label=True, add_target_line=True),
            use_container_width=True,
            key=f"{company}_{product}_{base_ym}_roll",
        )

    with c2:
        st.plotly_chart(
            make_line_chart(d30_df, "30D+연체율"),
            use_container_width=True,
            key=f"{company}_{product}_{base_ym}_30d",
        )

    with c3:
        st.plotly_chart(
            make_line_chart(norm_df, "단기정상화율"),
            use_container_width=True,
            key=f"{company}_{product}_{base_ym}_norm",
        )

def render_combined_summary(df, company, base_ym, selected_products):
    prod_df = df[(df["자회사구분"] == company) & (df["Section"] == "상품별현황")].copy()
    promo_df = df[df["Section"] == "프로모션"].copy()

    if not selected_products:
        return

    table_data = []

    for product in selected_products:
        summary = build_summary(prod_df, promo_df, company, product, base_ym)
        
        norm_name = summary["metric_name_norm"] if summary["metric_name_norm"] else ""
        norm_str = fmt_pp(summary['deltas']['단기정상화율'])
        if norm_name:
            norm_str += f" ({norm_name})"
            
        table_data.append({
            "상품명": product,
            "시그널": summary['overall_signal'],
            "종합평가": summary['overall_text'],
            "0→2 전이율": fmt_pp(summary['deltas']['연체전이율 0→2']),
            "0→1 전이율": fmt_pp(summary['deltas']['연체전이율 0→1']),
            "1→2 전이율": fmt_pp(summary['deltas']['연체전이율 1→2']),
            "30D+연체율": fmt_pp(summary['deltas']['실질연체율']),
            "단기정상화율": norm_str
        })

    summary_df = pd.DataFrame(table_data)
    
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.subheader(f"단기연체지표 요약 ({ym_to_label(base_ym)})")
    with col2:
        csv = summary_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 CSV 다운로드", data=csv, file_name=f"{company}_단기연체요약_{base_ym}.csv", mime="text/csv", use_container_width=True)

    def highlight_delinquency(val):
        if not isinstance(val, str): return ''
        try:
            num = float(val.split("%")[0].strip())
            if "↑" in val and num >= 0.3: return 'color: #D32F2F; font-weight: bold;'
            if "↓" in val and num >= 0.3: return 'color: #1976D2; font-weight: bold;'
        except: pass
        return ''

    def highlight_normalization(val):
        if not isinstance(val, str): return ''
        try:
            num = float(val.split("%")[0].strip())
            if "↑" in val and num >= 1.0: return 'color: #1976D2; font-weight: bold;'
            if "↓" in val and num >= 1.0: return 'color: #D32F2F; font-weight: bold;'
        except: pass
        return ''

    bad_cols = [c for c in summary_df.columns if "전이율" in c or "연체율" in c]
    good_cols = [c for c in summary_df.columns if "정상화율" in c]
    
    styler = summary_df.style
    styler = styler.set_properties(subset=["시그널", "종합평가"], **{'text-align': 'center'})
    if bad_cols: styler = styler.applymap(highlight_delinquency, subset=bad_cols)
    if good_cols: styler = styler.applymap(highlight_normalization, subset=good_cols)

    help_signal = (
        "**[ 🎯 종합 평가 시그널 기준 ]**\n\n"
        "- 🔴: **전반적 악화** (핵심지표 2개 이상 악화)\n"
        "- 🟡: **일부 악화** (핵심지표 1개 악화)\n"
        "- 🟢: **전월대비 양호** (악화된 지표 없이 1개 이상 개선)\n"
        "- 🔵: **전반적 개선** (핵심지표 2개 이상 개선)\n"
        "- ⚪: **전월 수준 유지** (모든 지표 전월과 동일)\n\n"
        "*(※ 평가 대상: 0→2 전이율, 30D+ 실질연체율, 단기정상화율)*"
    )
    
    st.dataframe(
        styler, 
        hide_index=True, 
        use_container_width=True,
        column_config={
            "시그널": st.column_config.TextColumn("시그널", help=help_signal),
            "종합평가": st.column_config.TextColumn("종합평가", help=help_signal)
        }
    )

    # 프로모션은 회사 단위라 한 번만
    promo_base = promo_df[(promo_df["자회사구분"] == company) & (promo_df["년월"] == base_ym)]
    promo_text = []
    for team in promo_base["구분"].dropna().unique().tolist():
        achieved = promo_base[(promo_base["구분"] == team) & (promo_base["항목"] == "달성여부")]
        if achieved.empty:
            continue
        val = str(achieved["값_raw"].iloc[0]).strip()
        if val == "Y":
            promo_text.append(f"{team} 목표 달성")
        elif val == "N":
            promo_text.append(f"{team} 목표 미달성")

    if promo_text:
        st.info("**[프로모션 현황]** " + ", ".join(promo_text))

def render_company_tables(df: pd.DataFrame, company: str):
    promo_df = df[(df["자회사구분"] == company) & (df["Section"] == "프로모션")].copy()
    fund_df = df[(df["자회사구분"] == company) & (df["Section"] == "새출발기금 월별 현황")].copy()
    adj_df = df[(df["자회사구분"] == company) & (df["Section"] == "자체 채무조정")].copy()

    st.divider()
    st.subheader("기타")
    st.markdown("#### 프로모션")
    if promo_df.empty:
        st.info("프로모션 데이터가 없습니다.")
    else:
        render_promo_table(promo_df)

    st.markdown("#### 새출발기금")
    if fund_df.empty:
        st.info("새출발기금 데이터가 없습니다.")
    else:
        render_fund_table(fund_df)

    st.markdown("#### 자체 채무조정")
    if adj_df.empty:
        st.info("자체 채무조정 데이터가 없습니다.")
    else:
        render_debt_adjust_table(adj_df)


def make_metric_comparison_chart(df: pd.DataFrame, company: str, products: list[str], metric_family: str, title: str) -> go.Figure:
    fig = go.Figure()
    if not products:
        fig.update_layout(title=title, height=300)
        return fig
        
    prod_df = df[(df["자회사구분"] == company) & (df["Section"] == "상품별현황")].copy()
    
    # We need recent 13 months globally
    months = sorted(prod_df["년월"].dropna().astype(str).unique().tolist())
    recent_months = months[-13:]
    
    y_max = 0.0
    y_min = float('inf')
    
    # Predefined colors for products
    colors = [
        "rgb(91,155,213)", "rgb(237,125,49)", "rgb(165,165,165)",
        "rgb(255,192,0)", "rgb(68,114,196)", "rgb(112,173,71)",
        "rgb(37,94,145)", "rgb(158,72,14)", "rgb(99,99,99)", "rgb(0,0,0)"
    ]
    
    annotations = []
    
    for i, product in enumerate(products):
        if metric_family == "단기정상화율":
            m_name = get_norm_metric_name(prod_df, product)
            if not m_name: continue
        else:
            m_name = metric_family
            
        temp = prod_df[(prod_df["구분"] == product) & (prod_df["항목"] == m_name) & (prod_df["년월"].isin(recent_months))].sort_values("년월").copy()
        if temp.empty: continue
        
        temp["x_label"] = build_compact_labels(temp["년월"].astype(str).tolist(), shift_x_label=(metric_family=="연체전이율 0→2"))
        
        valid_vals = temp["값"].dropna()
        if not valid_vals.empty:
            curr_max = valid_vals.max()
            curr_min = valid_vals.min()
            if curr_max > y_max: y_max = curr_max
            if curr_min < y_min: y_min = curr_min
            
        color = colors[i % len(colors)]
        legend_name = f"{product}({m_name})" if metric_family == "단기정상화율" else product
        
        temp["전월값"] = temp["값"].shift(1)
        temp["증감"] = temp["값"] - temp["전월값"]
        def format_hover_comp(row):
            if pd.isna(row["증감"]) or row["증감"] == 0: return f"{row['값']:.2f}"
            arrow = "▲" if row["증감"] > 0 else "▼"
            return f"{row['값']:.2f} ({arrow}{abs(row['증감']):.2f}p)"
        temp["hover_text"] = temp.apply(format_hover_comp, axis=1)

        fig.add_trace(go.Scatter(
            x=temp["x_label"], y=temp["값"], mode="lines+markers", name=legend_name,
            line=dict(color=color, width=2.25, dash="solid"), marker=dict(size=6, color=color),
            text=temp["hover_text"], hovertemplate="%{text}"
        ))

    if y_min == float('inf'): y_min = 0.0
    
    y_diff = y_max - y_min
    if y_diff == 0: y_diff = y_max if y_max > 0 else 1.0
    y_bottom = max(0.0, y_min - y_diff * 0.15) if y_min >= 0 else y_min - y_diff * 0.15
    y_top = y_max + y_diff * 0.20

    layout = dict(
        title=title, height=350, margin=dict(l=20, r=20, t=50, b=30), xaxis_title=None,
        xaxis=dict(tickangle=0),
        yaxis=dict(title=None, showticklabels=False, showgrid=False, zeroline=False, range=[y_bottom, y_top]),
        plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False, hovermode="x unified"
    )
    fig.update_layout(**layout)
    return fig


def render_comprehensive_tab(df: pd.DataFrame, companies: list[str], base_ym: str):
    st.subheader("종합 현황 (회사별 일부 상품 직접 비교)")

    months = sorted(df["년월"].dropna().astype(str).unique().tolist())
    if base_ym in months and months.index(base_ym) > 0:
        prev_ym = months[months.index(base_ym) - 1]
        d30 = df[(df["항목"] == "실질연체율") & (df["Section"] == "상품별현황")].copy()
        
        curr = d30[d30["년월"] == base_ym].groupby(["자회사구분", "구분"])["값"].first()
        prev = d30[d30["년월"] == prev_ym].groupby(["자회사구분", "구분"])["값"].first()
        
        diff = (curr - prev).dropna().sort_values(ascending=False)
        worst_3 = diff[diff > 0].head(3)
        
        if not worst_3.empty:
            st.error("🚨 **[리스크 조기경보] 전월 대비 30D+ 연체율 상승 폭 WORST TOP 3 상품**")
            cols = st.columns(len(worst_3))
            for i, (idx_tuple, val) in enumerate(worst_3.items()):
                comp, prod = idx_tuple
                curr_val = curr.loc[idx_tuple]
                with cols[i]:
                    st.metric(f"#{i+1} {comp} - {prod}", f"{curr_val:.2f}%", f"+{val:.2f}%p", delta_color="inverse")
            st.markdown("<br>", unsafe_allow_html=True)

    selected_products_by_company = {}
    with st.expander("비교할 상품 선택", expanded=True):
        cols = st.columns(len(companies))
        for col, company in zip(cols, companies):
            with col:
                st.markdown(f"**{company}**")
                all_prods = get_company_products(df, company)
                default_prods = all_prods[:2] if len(all_prods) >= 2 else all_prods
                
                def _norm(s):
                    return s.lower().replace(" ", "").replace("(", "").replace(")", "")
                
                if company == "전북은행":
                    wanted = all_prods[:2] + ["외국인전체", "자동차담보", "자동차담보(SP)", "쏙대출", "카카오 공동대출"]
                    default_prods = []
                    for w in wanted:
                        for p in all_prods:
                            if _norm(w) == _norm(p) and p not in default_prods:
                                default_prods.append(p)
                elif company == "광주은행":
                    wanted = all_prods[:2] + ["토스 공동대출", "외국인"]
                    default_prods = []
                    for w in wanted:
                        for p in all_prods:
                            if _norm(w) == _norm(p) and p not in default_prods:
                                default_prods.append(p)
                else: 
                    default_prods = all_prods.copy()

                selected_products_by_company[company] = st.multiselect(
                    f"{company} 상품", all_prods, default=default_prods, label_visibility="collapsed", key=f"comp_m_{company}"
                )

    st.divider()

    for company in companies:
        selected_prods = selected_products_by_company[company]
        if not selected_prods:
            continue
            
        st.markdown(f"### {company}")
        
        colors = [
            "rgb(91,155,213)", "rgb(237,125,49)", "rgb(165,165,165)",
            "rgb(255,192,0)", "rgb(68,114,196)", "rgb(112,173,71)",
            "rgb(37,94,145)", "rgb(158,72,14)", "rgb(99,99,99)", "rgb(0,0,0)"
        ]
        legend_html = []
        for i, prod in enumerate(selected_prods):
            c = colors[i % len(colors)]
            legend_html.append(f"<span style='display:inline-block; margin-right:20px;'><span style='color:{c}; font-size:16px;'>●</span> <span style='font-size:14px; color:#333; font-weight:500;'>{prod}</span></span>")
        st.markdown("<div style='margin-bottom: 10px; padding: 12px 15px; background-color: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef;'>" + "".join(legend_html) + "</div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        
        with c1:
            fig = make_metric_comparison_chart(df, company, selected_prods, "실질연체율", "30D+연체율")
            st.plotly_chart(fig, use_container_width=True, key=f"comp_{company}_30d")
        with c2:
            fig = make_metric_comparison_chart(df, company, selected_prods, "단기정상화율", "단기정상화율")
            st.plotly_chart(fig, use_container_width=True, key=f"comp_{company}_norm")
        with c3:
            fig = make_metric_comparison_chart(df, company, selected_prods, "연체전이율 0→2", "0->2 전이율")
            st.plotly_chart(fig, use_container_width=True, key=f"comp_{company}_02")
            
        st.markdown("---")

