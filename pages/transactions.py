import streamlit as st
import pandas as pd
from prefilter import load_data, CATEGORY_MAP, get_custom_category_list

st.title("📋 Transaction History")

if "messages" in st.session_state and st.session_state.messages:
    st.session_state.messages = []
if "chat_memory" in st.session_state and st.session_state.chat_memory:
    st.session_state.chat_memory.clear()

df = load_data("resources/customer_transactions.xlsx")

if "category_name" not in df.columns:
    df["category_name"] = df["category_by_system"].map(CATEGORY_MAP)

category_summary = get_custom_category_list(df)

with st.expander("System Spending Categories", expanded=False):
    st.caption("Transactions are mapped into the following system categories:")
    st.text(category_summary)

st.subheader("Filter Transactions")
col1, col2 = st.columns([2, 2])

category_options = ["All Categories"] + [
    f"{cat_id} - {CATEGORY_MAP.get(cat_id, 'Other')}"
    for cat_id in sorted(df["category_by_system"].unique())
]

with col1:
    selected_cat_str = st.selectbox("Category", category_options)

with col2:
    search_keyword = st.text_input("Search Merchant or Note", placeholder="e.g., Starbucks, Indomaret, Fuel")

filtered_df = df.copy()

if selected_cat_str != "All Categories":
    selected_cat_id = int(selected_cat_str.split(" - ")[0])
    filtered_df = filtered_df[filtered_df["category_by_system"] == selected_cat_id]

if search_keyword:
    mask = (
        filtered_df["subheader"].str.contains(search_keyword, case=False, na=False) |
        filtered_df["notes"].str.contains(search_keyword, case=False, na=False) |
        filtered_df["detail_information"].str.contains(search_keyword, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

filtered_df = filtered_df.sort_values(by="trx_date", ascending=False)

m1, m2, m3 = st.columns(3)
total_spend = filtered_df["amount"].sum()
m1.metric("Total Amount", f"Rp {total_spend:,.0f}")
m2.metric("Transactions Found", f"{len(filtered_df)}")
m3.metric("Categories Active", f"{filtered_df['category_by_system'].nunique()}")

st.subheader("Records")

display_cols = ["trx_date", "subheader", "detail_information", "category_name", "debit_credit", "amount", "notes"]
available_cols = [c for c in display_cols if c in filtered_df.columns]

presentation_df = filtered_df[available_cols].copy()
if "trx_date" in presentation_df.columns:
    presentation_df["trx_date"] = presentation_df["trx_date"].dt.strftime("%Y-%m-%d")

st.dataframe(
    presentation_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "trx_date": "Date",
        "subheader": "Merchant / Brand",
        "detail_information": "Description",
        "category_name": "Category",
        "debit_credit": "Type",
        "amount": st.column_config.NumberColumn("Amount (Rp)", format="Rp %d"),
        "notes": "Notes",
    }
)

st.subheader("Category Breakdown")
cat_totals = df.groupby("category_name")["amount"].sum().sort_values(ascending=False)
st.bar_chart(cat_totals)
