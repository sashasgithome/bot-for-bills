import streamlit as st
from process import GeminiAgent, ConversationMemory, validate_query, get_query_params, execute_query, generate_final_response
from prefilter import load_data, get_custom_category_list

st.title("🏦 Finance Assistant")

if "user_df" not in st.session_state:
    st.session_state.user_df = load_data("resources/customer_transactions.xlsx")

if "category_list" not in st.session_state:
    st.session_state.category_list = get_custom_category_list(st.session_state.user_df)

if "chat_memory" not in st.session_state:
    st.session_state.chat_memory = ConversationMemory(window_size=3)

user_name = st.session_state.get("user_name", "Shane Parker")
user_lang = st.session_state.get("user_lang", "en")

if user_lang == "id":
    st.caption(f"Selamat datang, {user_name}! Silakan tanyakan riwayat transaksi atau pengeluaran Anda.")
else:
    st.caption(f"Welcome, {user_name}! Ask any question regarding your transaction history and spending.")

agent = GeminiAgent()
model = agent.llm

if not model:
    st.warning("⚠️ `GEMINI_API_KEY` is not set in `.env`. Please provide your key in `.env` to start chatting with the assistant.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about your spending (e.g., How much did I spend on groceries?)..."):
    if not model:
        st.error("Please add `GEMINI_API_KEY` to your local `.env` file first.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Preparing your financial insights..."):
        conversation_context = st.session_state.chat_memory.get_context()

        validation = validate_query(prompt, model, conversation_context)
        if validation != "VALID":
            full_response = validation
            with st.chat_message("assistant"):
                st.markdown(full_response)
        else:
            params = get_query_params(prompt, st.session_state.category_list, model, conversation_context)
            context = execute_query(user_name, user_lang, st.session_state.user_df, params)
            full_response = generate_final_response(prompt, context, model, conversation_context)

            with st.chat_message("assistant"):
                st.markdown(full_response)

                with st.expander("SEE CHATBOT LOGIC DETAILS"):
                    st.write("**LLM Reasoning (JSON Params):**")
                    st.json(params)
                    st.write(f"**Data Grounding:** Found {context['transaction_count']} transactions totaling Rp {int(context['total_spend']):,}")

                    if conversation_context:
                        st.write("**Conversation Memory Context:**")
                        st.text(conversation_context)

                    if context["transaction_data"]:
                        st.write("**Transactions given as LLM Context:**")
                        st.dataframe(
                            context["transaction_data"],
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info("No individual transaction records were found for this query.")

        st.session_state.chat_memory.add_turn(prompt, full_response, model)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
