import os
import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CIF = 100550
DEFAULT_PROFILE = {
    "cif": 100550,
    "name": "Shane Parker",
    "lang": "en",
    "account_type": "Basic",
    "region": "Jakarta",
    "risk_profile": "Low",
}

CATEGORY_MAP = {
    1: "Groceries",
    2: "Dining",
    3: "Fuel & Gas",
    4: "Shopping",
    5: "Healthcare",
    6: "Transportation",
    7: "Entertainment",
    8: "Utilities",
    9: "Education",
    10: "Insurance",
}

# Loads transaction data from Excel or CSV file into a pandas DataFrame.
@st.cache_data
def load_data(filename="resources/customer_transactions.xlsx"):
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        df = pd.read_excel(filename)
    else:
        df = pd.read_csv(filename, sep=";")
    
    df.columns = df.columns.str.strip().str.lower()
    if "trx_date" in df.columns:
        df["trx_date"] = pd.to_datetime(df["trx_date"])
    return df

# Retrieves unique subheaders, notes, and details for each category ID in transactions.
def get_category_descriptors(df):
    
    mapping_suggestions = []
    for cat_id, group in df.groupby("category_by_system"):
        subheaders = group["subheader"].dropna().unique().tolist()
        notes = group["notes"].dropna().unique().tolist()
        details = group["detail_information"].dropna().unique().tolist()
        sample_string = f"ID {cat_id}:\nSubheaders: {subheaders}\nNotes: {notes}\nDetails: {details}"
        mapping_suggestions.append(sample_string)
    return "\n\n".join(mapping_suggestions)

# Extracts string content from LLM response, handling strings or list of content blocks.
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

# Generates standardized category summary string using LLM or structured fallback.
def get_custom_category_list(df, model=None):
    
    if model is not None:
        try:
            mapping_suggestions = get_category_descriptors(df)
            system_prompt = f"""
            CONTEXT:
            You are a Financial Data Analyst specializing in categorizing banking transaction patterns.
            There is a list of unique 'Subheaders', 'Notes', and 'Detail Information' grouped by a numerical 'Category ID'. 
            INPUT DATA: {mapping_suggestions}

            TASK:
            1. Identify one-word representing high-level spending theme for each Category ID (e.g., Dining, Groceries, Education).
            2. List most common merchants, brands, or keywords found in that category, maximum of 6.
            3. Return the results in a strict format below.

            FORMAT OF STRING OUTPUT SHOULD ONLY BE :
            [CATEGORY NUMBER] : [MAIN TOPIC] ([EXAMPLE1, EXAMPLE2, EXAMPLE3, EXAMPLE4, EXAMPLE5])

            EXAMPLE OUTPUT: 
            1 : Groceries (Indomaret, Alfamart, Carrefour, Giant, Superindo)
            2 : Dining (Starbucks, McDonalds, Pizza Hut, KFC, Burger King)
            """
            raw = model.invoke(system_prompt).content
            return extract_text_content(raw)
        except Exception as e:
            print(f"LLM category generation fallback: {e}")


    lines = []
    for cat_id, group in df.groupby("category_by_system"):
        topic = CATEGORY_MAP.get(int(cat_id), f"Category {cat_id}")
        examples = group["subheader"].dropna().unique().tolist()[:5]
        example_str = ", ".join(examples)
        lines.append(f"{cat_id} : {topic} ({example_str})")
    return "\n".join(lines)

# Fetches customer profile information by CIF ID.
def get_customer_profile(cif_id=DEFAULT_CIF, profile_file="resources/customer_profiles.csv"):
    
    if not os.path.exists(profile_file):
        return DEFAULT_PROFILE

    try:
        profile_df = pd.read_csv(profile_file, sep=";")
        profile_df.columns = profile_df.columns.str.strip().str.lower()
        match = profile_df[profile_df["cif"].astype(str) == str(cif_id)]
        if match.empty:
            return DEFAULT_PROFILE

        row = match.iloc[0]
        prefs = {}
        try:
            prefs = json.loads(row["preferences"])
        except Exception:
            pass

        return {
            "cif": int(row["cif"]),
            "name": row["customer_name"],
            "lang": prefs.get("language", "en"),
            "account_type": row.get("account_type", "Standard"),
            "region": row.get("region", "-"),
            "risk_profile": row.get("risk_profile", "-"),
        }
    except Exception as e:
        print(f"Error loading customer profile: {e}")
        return DEFAULT_PROFILE
