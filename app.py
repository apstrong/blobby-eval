import streamlit as st
from omni_python_sdk import OmniAPI
from dotenv import load_dotenv
import os
import pandas as pd
import json
import requests
import random

# Load API key and base url from .env
load_dotenv()
api_key = os.getenv("OMNI_API_KEY")
base_url = os.getenv("OMNI_BASE_URL")

# Define dataset info
DATASET = {
    "topic": "orders_ai",
    "description": "Ask questions about sales, orders, and revenue"
}

# Set up page
st.set_page_config(page_title="Blobby's Evaluation MVP", page_icon="🤖", layout="wide")
st.title("Blobby's Evaluation MVP 🤖")

# Model ID configuration
st.sidebar.header("⚙️ Configure Models")
model_1_id = st.sidebar.text_input("Model A ID", value="7f250d4f-75bd-45ab-a58d-22db81174793")
model_2_id = st.sidebar.text_input("Model B ID", value="e29c35ca-39f6-4a6b-bcb8-0bfc8f5be64b")

# Initialize session state
for key in ["prompt_text", "evaluations", "feedback_a", "feedback_b",
            "model_a_result", "model_a_query", "model_b_result", "model_b_query", "last_prompt_submitted"]:
    if key not in st.session_state:
        st.session_state[key] = None if "feedback" not in key else {"rating": None, "note": "", "submitted": False}

# Initialize Omni client
client = OmniAPI(api_key, base_url=base_url)

def query_data(prompt, model_id):
    try:
        data = {
            "currentTopicName": DATASET["topic"],
            "modelId": model_id,
            "prompt": prompt
        }
        response = requests.post(
            f"{base_url}/api/unstable/ai/generate-query",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=data
        )
        if response.status_code != 200:
            st.error(f"API Error: {response.status_code}")
            return None, None

        query_dict = response.json()
        query_result = client.run_query_blocking(query_dict)
        if query_result is None:
            st.error("No query result returned")
            return None, None

        result, _ = query_result
        df = result.to_pandas()

        # Clean up
        df = df.loc[:, ~df.columns.str.contains("raw|pivot|sort", case=False)]
        df.columns = [col.split(".")[-1].replace("_", " ") for col in df.columns]

        return df, query_dict

    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None, None

# Prompt input
with st.form("prompt_form"):
    prompt = st.text_input("Ask a question:", value=st.session_state.prompt_text or "")
    submitted = st.form_submit_button("✨Let's go✨")

if submitted and prompt.strip():
    st.session_state.prompt_text = prompt
    st.session_state.last_prompt_submitted = prompt
    st.session_state.model_a_result, st.session_state.model_a_query = query_data(prompt, model_1_id)
    st.session_state.model_b_result, st.session_state.model_b_query = query_data(prompt, model_2_id)

# Only show results if prompt has been submitted
if st.session_state.last_prompt_submitted:
    col1, col2 = st.columns(2)

    for label, model_id, df_key, query_key, feedback_key, col in [
        ("Model A", model_1_id, "model_a_result", "model_a_query", "feedback_a", col1),
        ("Model B", model_2_id, "model_b_result", "model_b_query", "feedback_b", col2)
    ]:
        with col:
            st.markdown(f"### {label} Results")
            df = st.session_state[df_key]
            query = st.session_state[query_key]

            if df is not None:
                st.dataframe(df, use_container_width=True)
                with st.expander("Query Details"):
                    if query and "query" in query:
                        query_details = query["query"]
                        filtered_query = {
                            "fields": query_details.get("fields", []),
                            "filters": query_details.get("filters", {}),
                            "limit": query_details.get("limit"),
                            "sort": query_details.get("sorts", [])
                        }
                        # Remove None values and empty lists/dicts
                        filtered_query = {k: v for k, v in filtered_query.items() if v not in [None, [], {}, ""]}
                        st.json(filtered_query)

    st.markdown("### Feedback")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Model A Rating**")
        rating_a = st.radio("Model A Rating", ["👍", "👎"], key="rating_a", horizontal=True, label_visibility="collapsed")
        st.session_state.feedback_a["rating"] = rating_a if rating_a != "No rating" else None
        note_a = st.text_area("Feedback for Model A:", value=st.session_state.feedback_a["note"], key="note_a")
        st.session_state.feedback_a["note"] = note_a

    with col2:
        st.write("**Model B Rating**")
        rating_b = st.radio("Model B Rating", ["👍", "👎"], key="rating_b", horizontal=True, label_visibility="collapsed")
        st.session_state.feedback_b["rating"] = rating_b if rating_b != "No rating" else None
        note_b = st.text_area("Feedback for Model B:", value=st.session_state.feedback_b["note"], key="note_b")
        st.session_state.feedback_b["note"] = note_b

    if st.button("Submit Feedback", key="submit_feedback_combined"):
        if st.session_state.feedback_a["rating"]:
            st.session_state.evaluations = st.session_state.evaluations or []
            st.session_state.evaluations.append({
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "model": "Model A",
                "model_id": model_1_id,
                "prompt": st.session_state.prompt_text,
                "feedback": st.session_state.feedback_a["rating"],
                "note": note_a
            })
        if st.session_state.feedback_b["rating"]:
            st.session_state.evaluations = st.session_state.evaluations or []
            st.session_state.evaluations.append({
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "model": "Model B",
                "model_id": model_2_id,
                "prompt": st.session_state.prompt_text,
                "feedback": st.session_state.feedback_b["rating"],
                "note": note_b
            })
        st.success("Feedback submitted!")

# Evaluation history
if st.session_state.evaluations:
    evals_df = pd.DataFrame(st.session_state.evaluations)
    st.markdown("### Evaluation History")
    st.dataframe(evals_df, use_container_width=True)

    st.markdown("### 📊 Model Performance Summary")
    grouped = evals_df.groupby("model")["feedback"].value_counts().unstack().fillna(0)
    grouped["Total"] = grouped.sum(axis=1)
    grouped["Net Positive %"] = (grouped.get("👍", 0) / grouped["Total"] * 100).round(1)
    grouped = grouped.rename(columns={"👍": "Thumbs Up", "👎": "Thumbs Down"})
    st.dataframe(grouped.reset_index(), use_container_width=True)

st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.8rem; font-style: italic;">
        Built on <a href="https://omni.co/" style="color: #666; text-decoration: none;">Omni</a> and vibes ✨
    </div>
""", unsafe_allow_html=True)
