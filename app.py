import streamlit as st
from dashboard_components import (
    DATA_PATH,
    COMPANY_ORDER,
    load_data,
    company_list,
    get_company_products,
    render_product_section,
    render_company_tables,
    render_combined_summary,
    render_comprehensive_tab
)

st.set_page_config(page_title="단기연체 관리현황 Dashboard", layout="wide")


def init_product_selection(company: str, products: list[str]):
    key = f"selected_products_{company}"
    if key not in st.session_state:
        st.session_state[key] = products.copy()
    return key


def render_company_tab(df, company, base_ym):
    products = get_company_products(df, company)

    mode = st.radio(
        "상품 선택",
        ["전체 선택", "전체 해제", "직접 선택"],
        horizontal=True,
        key=f"{company}_mode"
    )

    if mode == "전체 선택":
        default_products = products
    elif mode == "전체 해제":
        default_products = []
    else:
        default_products = products[:1]

    selected_products = st.multiselect(
        "상품 선택",
        products,
        default=default_products,
        key=f"{company}_products"
    )

    if not selected_products:
        st.info("선택된 상품이 없습니다.")
        return

    render_combined_summary(df, company, base_ym, selected_products)

    st.divider()
    st.subheader("그래프")

    for product in selected_products:
        render_product_section(df, company, base_ym, product)
        st.divider()

    render_company_tables(df, company)


def main():
    st.title("단기연체 관리현황 Dash-Board")
    if not DATA_PATH.exists():
        st.error("동일 경로에 dataset.xlsx 파일이 필요합니다.")
        st.stop()

    df = load_data(DATA_PATH)
    companies = company_list(df)
    all_months = sorted(df["년월"].dropna().unique().tolist())
    latest_ym = all_months[-1]

    with st.sidebar:
        st.header("조회 조건")
        base_ym = st.selectbox("기준연월", all_months, index=all_months.index(latest_ym))
        st.markdown("---")
        st.caption("회사 탭에서 원하는 회사와 상품을 선택하세요.")

    tabs = st.tabs(["종합"] + companies)
    
    with tabs[0]:
        render_comprehensive_tab(df, companies, base_ym)
        
    for tab, company in zip(tabs[1:], companies):
        with tab:
            render_company_tab(df, company, base_ym)


if __name__ == "__main__":
    main()
