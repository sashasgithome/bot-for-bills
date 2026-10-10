import streamlit as st
from dotenv import load_dotenv
from prefilter import load_data, get_customer_profile, get_custom_category_list

load_dotenv()

st.set_page_config(page_title="Finance Assistant Prototype", page_icon="🏦", layout="wide")

profile = get_customer_profile()

if "user_name" not in st.session_state:
    st.session_state.user_name = profile["name"]
    st.session_state.user_lang = profile["lang"]
    st.session_state.cif_id = profile["cif"]
    st.session_state.user_df = load_data("resources/customer_transactions.xlsx")
    st.session_state.category_list = get_custom_category_list(st.session_state.user_df)

with st.sidebar:
    st.title("Customer Portal")
    st.info("Demo Account")
    st.markdown(f"""
    - **CIF ID:** `{profile['cif']}`
    - **Name:** {profile['name']}
    - **Account Type:** {profile['account_type']}
    - **Region:** {profile['region']}
    - **Language:** `{profile['lang']}`
    """)

    st.divider()
    if st.button("Reset Chat History", use_container_width=True):
        st.session_state.messages = []
        if "chat_memory" in st.session_state and st.session_state.chat_memory:
            st.session_state.chat_memory.clear()
        st.rerun()

transactions_page = st.Page("pages/transactions.py", title="Transaction List", icon="📋", default=True)
chatbot_page = st.Page("pages/chatbot.py", title="Finance Assistant", icon="💬")

pg = st.navigation([transactions_page, chatbot_page])
pg.run()
