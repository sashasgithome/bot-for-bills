import os
import json
from datetime import datetime
import pandas as pd
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# Extracts clean string text from LLM content (string or list of content blocks).
def extract_text_content(content):
    
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif hasattr(item, "text"):
                parts.append(str(item.text))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    return str(content).strip()

# Sliding Window + Summary Buffer memory for session conversation history.
class ConversationMemory:
    
    def __init__(self, window_size=3):
        self.window_size = window_size
        self.turns = []
        self.summary = ""

    def add_turn(self, question, answer, model=None):
        self.turns.append({"question": question, "answer": answer})
        if len(self.turns) > self.window_size:
            evicted = self.turns.pop(0)
            self._update_summary(evicted, model)

    def _update_summary(self, turn, model=None):
        if model is not None:
            try:
                prompt = f"""
                CONVERSATION SUMMARY SO FAR:
                {self.summary if self.summary else "None"}

                NEW CONVERSATION TURN:
                User: {turn['question']}
                Assistant: {turn['answer']}

                TASK: Update the conversation summary concisely in 2-3 sentences.
                """
                raw = model.invoke(prompt).content
                self.summary = extract_text_content(raw)
                return
            except Exception as e:
                print(f"Summary buffer update fallback: {e}")

        new_entry = f"User asked: '{turn['question']}' -> Assistant answered: '{turn['answer'][:120]}'"
        if self.summary:
            self.summary = f"{self.summary}\n{new_entry}"
        else:
            self.summary = new_entry

    def get_context(self):
        parts = []
        if self.summary:
            parts.append(f"Summary of earlier conversation:\n{self.summary}")
        if self.turns:
            recent_str = "\n".join([
                f"User: {t['question']}\nAssistant: {t['answer']}"
                for t in self.turns
            ])
            parts.append(f"Recent conversation:\n{recent_str}")
        return "\n\n".join(parts)

    def clear(self):
        self.turns = []
        self.summary = ""

class GeminiAgent:
    def __init__(self):
        self.name = "Gemini"
        self.model = "gemini-3.5-flash-lite"
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if self.api_key:
            self.llm = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
            )
        else:
            self.llm = None

# Validates if user query falls within chatbot's financial analysis capabilities.
@st.cache_data
def validate_query(user_query, _model, conversation_context=""):
    
    history_block = f"\nCONVERSATION HISTORY:\n{conversation_context}\n" if conversation_context else ""
    system_prompt = f"""
    CONTEXT:
    You are an 'Intelligent and Helpful Customer Assistant Bot' for a national bank in Indonesia. 
    Your assistant capabilities are limited to: counting amount of transactions, checking total spending, or listing transactions.
    {history_block}
    CURRENT CUSTOMER QUERY:
    {user_query}

    TASK: 
    1. If the query (in context of conversation history, if any) is within capabilities, return "VALID" only.
    2. If query is related to finance/banking but outside capabilities list, return a polite sentence clarifying your limitations.  
    3. If query is unrelated to finance/banking, return a polite sentence explaining your specific role as a finance assistant only.
    """
    raw = _model.invoke(system_prompt).content
    response = extract_text_content(raw)
    return response

# Translates natural language user query into structured filtering parameters.
@st.cache_data
def get_query_params(user_query, category_list, _model, conversation_context=""):
    
    history_block = f"\nCONVERSATION HISTORY:\n{conversation_context}\n" if conversation_context else ""
    system_prompt = f"""
    CONTEXT:
    Today is {datetime.now().strftime('%Y-%m-%d')}. Convert user query into a JSON object for filtering a pandas dataframe.
    CATEGORIES: {category_list}
    {history_block}
    CURRENT USER QUERY:
    {user_query}

    TASK: Translate the current user query into the following parameters, resolving any references from CONVERSATION HISTORY:
    - operation: one of "sum", "count", "max", or "list".
    - category_id: numerical Category ID from CATEGORIES list as integer, or null if all.
    - search_terms: list of keywords to search for in subheaders/notes.
    - start_date: start date in "YYYY-MM-DD" format, default to one year ago if not specified.
    - end_date: end date in "YYYY-MM-DD" format, default to today if not specified.
    
    JSON SCHEMA:
    {{
        "operation": "sum" | "count" | "max" | "list",
        "category_id": int | null,
        "search_terms": [string],
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD"
    }}
    """
    try:
        raw = _model.invoke(system_prompt).content
        response = extract_text_content(raw)
        clean_json = response.replace("```json", "").replace("```", "").strip()
        if not clean_json:
            return {"operation": "list", "category_id": None, "search_terms": []}
        return json.loads(clean_json)
    except Exception as e:
        print(f"Error parsing query parameters: {e}")
        return {"operation": "list", "category_id": None, "search_terms": []}


# Filters dataframe by extracted parameters and computes relevant metrics.
def execute_query(user_name, user_lang, df, params):
    
    relevant_df = df.copy()

    if params.get("category_id"):
        relevant_df = relevant_df[relevant_df["category_by_system"] == params["category_id"]]

    if params.get("start_date") and params.get("end_date"):
        start_date = pd.to_datetime(params["start_date"])
        end_date = pd.to_datetime(params["end_date"])
        relevant_df = relevant_df[(relevant_df["trx_date"] >= start_date) & (relevant_df["trx_date"] <= end_date)]

    if params.get("search_terms"):
        pattern = "|".join(params["search_terms"])
        text_mask = relevant_df["subheader"].str.contains(pattern, case=False, na=False) | \
                    relevant_df["notes"].str.contains(pattern, case=False, na=False)
        relevant_df = relevant_df[text_mask]

    relevant_df = relevant_df.sort_values(by="trx_date", ascending=False)
    relevant_data_amount = len(relevant_df)

    selected_columns = ["trx_date", "subheader", "detail_information", "notes", "amount", "debit_credit"]
    available_cols = [col for col in selected_columns if col in relevant_df.columns]

    if relevant_data_amount > 10:
        recent_transactions = relevant_df[available_cols].head(10).to_dict(orient="records")
    else:
        recent_transactions = relevant_df[available_cols].to_dict(orient="records")

    for item in recent_transactions:
        if "trx_date" in item and hasattr(item["trx_date"], "strftime"):
            item["trx_date"] = item["trx_date"].strftime("%Y-%m-%d")

    return {
        "user_name": user_name,
        "user_lang": user_lang,
        "total_spend": float(relevant_df["amount"].sum()),
        "transaction_count": relevant_data_amount,
        "transaction_data": recent_transactions,
    }

# Generates natural language response grounded strictly on retrieved context.
@st.cache_data
def generate_final_response(user_query, context, _model, conversation_context=""):
    
    history_block = f"\nCONVERSATION HISTORY:\n{conversation_context}\n" if conversation_context else ""
    polisher_prompt = f"""
    You are an 'Intelligent Customer Assistant', a helpful and professional financial bot for customer named {context['user_name']}.
    {history_block}
    CURRENT USER QUERY: "{user_query}"
    
    INPUT DATA:
    - Total Amount: Rp {int(context['total_spend']):,}
    - Number of Transactions: {context['transaction_count']}
    - Recent Details: {context['transaction_data']}

    GOAL:
    1. Answer user query directly and clearly in {context['user_lang']} language with professional yet friendly tone.
    2. Maintain natural continuity with CONVERSATION HISTORY when answering follow-up queries.
    3. Always format currency in Rupiah (Rp).
    
    STRICT RULE: Only use INPUT DATA provided above. Do not hallucinate transactions.
    """
    raw = _model.invoke(polisher_prompt).content
    response = extract_text_content(raw)
    return response