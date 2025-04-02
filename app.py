import streamlit as st
from omni_python_sdk import OmniAPI
from dotenv import load_dotenv
import os
import pandas as pd
import json
import requests
import random
import csv

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
st.set_page_config(page_title="Blobby's Evaluation Suite", page_icon="🤖", layout="wide")
st.title("Blobby's Evaluation Suite 🤖🧪")

def extract_model_id_from_url(url):
    """Extract model ID from Omni URL."""
    try:
        # Split by /models/ and take the second part
        model_part = url.split('/models/')[1]
        # Take everything before the next slash or end of string
        model_id = model_part.split('/')[0]
        return model_id
    except:
        return None

# Environment configuration
st.sidebar.header("🔑 Environment Setup")
api_key = st.sidebar.text_input("API Key", 
                               type="password",
                               value=st.session_state.get('api_key', ''),
                               help="Enter your Omni API key")
base_url = st.sidebar.text_input("Base URL", 
                                value=st.session_state.get('base_url', 'https://partners.omniapp.co'),
                                help="Enter the Omni API base URL")
topic_name = st.sidebar.text_input("Topic Name",
                                  value=st.session_state.get('topic_name', 'orders_ai'),
                                  help="Enter the topic name for queries")

# Store in session state
st.session_state['api_key'] = api_key
st.session_state['base_url'] = base_url
st.session_state['topic_name'] = topic_name

# Model configuration
model_a_url = st.sidebar.text_input("Model A URL", 
                                   value="https://partners.omniapp.co/models/7f250d4f-75bd-45ab-a58d-22db81174793/ide/model?mode=combined",
                                   help="Enter the Omni URL from the IDE for the first model you want to evaluate")
model_b_url = st.sidebar.text_input("Model B URL", 
                                   value="https://partners.omniapp.co/models/e29c35ca-39f6-4a6b-bcb8-0bfc8f5be64b/ide/model?mode=combined",
                                   help="Enter the Omni URL from the IDE for the first model you want to evaluate")

# Extract model IDs from URLs
model_1_id = extract_model_id_from_url(model_a_url)
model_2_id = extract_model_id_from_url(model_b_url)

if not model_1_id:
    st.sidebar.error("Invalid URL format for Model A. Please enter a valid Omni model URL.")

if not model_2_id:
    st.sidebar.error("Invalid URL format for Model B. Please enter a valid Omni model URL.")

# Mode selection using tabs
manual_tab, automated_tab = st.tabs(["Manual Evaluation", "Automated Evaluation"])

# Initialize session state variables
if "evaluation_suite" not in st.session_state:
    st.session_state.evaluation_suite = {
        "questions": [],
        "current_question": 0,
        "running": False
    }

for key in ["feedback_a", "feedback_b", "evaluations", 
            "model_a_result", "model_a_query", "model_b_result", "model_b_query"]:
    if key not in st.session_state:
        if key in ["feedback_a", "feedback_b"]:
            st.session_state[key] = {"rating": None, "note": "", "submitted": False}
        elif key == "evaluations":
            st.session_state[key] = []
        else:
            st.session_state[key] = None

# Initialize Omni client
client = OmniAPI(st.session_state['api_key'], base_url=st.session_state['base_url'])

def parse_expected_response(response_str):
    """Parse expected response string into either a single value or dataframe."""
    try:
        # First try to parse as JSON
        try:
            data = json.loads(response_str)
            if isinstance(data, dict):
                # Create DataFrame preserving original column names
                df = pd.DataFrame(data)
                return df
            elif isinstance(data, list):
                # Create DataFrame from list of dicts preserving original column names
                df = pd.DataFrame(data)
                return df
        except json.JSONDecodeError:
            pass
        
        # Try to parse as CSV
        try:
            # StringIO to simulate file for read_csv
            from io import StringIO
            df = pd.read_csv(StringIO(response_str))
            return df
        except:
            pass
        
        # If not JSON or CSV, treat as single value
        return response_str
    except Exception as e:
        st.error(f"Error parsing expected response: {str(e)}")
        return None

def compare_results(result_df, expected_response):
    """Compare query results with expected response."""
    try:
        # If expected response is a dataframe
        if isinstance(expected_response, pd.DataFrame):
            # Check if same number of rows
            if result_df.shape[0] != expected_response.shape[0]:
                return False
            
            # Convert both dataframes to sets of tuples for order-independent comparison
            # First sort each dataframe's columns alphabetically
            result_cols = sorted(result_df.columns)
            expected_cols = sorted(expected_response.columns)
            
            # Check if same columns exist (ignoring order)
            if set(result_cols) != set(expected_cols):
                return False
            
            # Convert each row to a tuple of values, sorted by column name
            result_rows = {tuple(sorted(row.items())) for _, row in result_df[result_cols].to_dict('index').items()}
            expected_rows = {tuple(sorted(row.items())) for _, row in expected_response[expected_cols].to_dict('index').items()}
            
            # Compare the sets of rows
            return result_rows == expected_rows
            
        # If result is a single value
        elif result_df.shape == (1, 1):
            return str(result_df.iloc[0, 0]) == str(expected_response)
        else:
            st.warning("Result is a dataframe but expected response is not. Cannot compare directly.")
            return False
    except Exception as e:
        st.error(f"Comparison error: {str(e)}")
        return False

def query_data(prompt, model_id):
    try:
        if not prompt or not model_id:
            st.error("Missing prompt or model ID")
            return None, None

        data = {
            "currentTopicName": st.session_state['topic_name'],
            "modelId": model_id,
            "prompt": prompt
        }
        
        response = requests.post(
            f"{st.session_state['base_url']}/api/unstable/ai/generate-query",
            headers={"Authorization": f"Bearer {st.session_state['api_key']}", "Content-Type": "application/json"},
            json=data
        )
        
        if response.status_code != 200:
            st.error(f"API Error: {response.status_code}")
            return None, None

        query_dict = response.json()
        if not query_dict:
            st.error("Empty response from API")
            return None, None
            
        query_result = client.run_query_blocking(query_dict)
        if query_result is None:
            st.error("No query result returned")
            return None, None

        result, _ = query_result
        if result is None:
            st.error("Query result is None")
            return None, None
            
        df = result.to_pandas()
        if df is None or df.empty:
            st.warning("Query returned empty result")
            return pd.DataFrame(), query_dict
            
        return df, query_dict

    except Exception as e:
        st.error(f"Error in query_data: {str(e)}")
        return None, None

# Manual Evaluation
with manual_tab:
    # Prompt input
    with st.form("prompt_form"):
        prompt = st.text_input("Ask a question:")
        submitted = st.form_submit_button("✨Let's go✨")

    # --- Query Flow ---
    if submitted and prompt.strip():
        st.session_state.model_a_result, st.session_state.model_a_query = query_data(prompt, model_1_id)
        st.session_state.model_b_result, st.session_state.model_b_query = query_data(prompt, model_2_id)

    # Show results if we have them
    if st.session_state.model_a_result is not None or st.session_state.model_b_result is not None:
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
                    try:
                        # Reset index to start at 1
                        df.index = range(1, len(df) + 1)
                        # Convert DataFrame to a format Streamlit can safely display
                        display_df = df.fillna('')  # Replace NaN with empty string
                        st.dataframe(display_df, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error displaying results: {str(e)}")
                        st.write("Raw data:", df.to_dict())
                    
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
                st.session_state.evaluations.append({
                    "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "model": "Model A",
                    "model_id": model_1_id,
                    "prompt": prompt,
                    "feedback": st.session_state.feedback_a["rating"],
                    "note": note_a
                })
            if st.session_state.feedback_b["rating"]:
                st.session_state.evaluations.append({
                    "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "model": "Model B",
                    "model_id": model_2_id,
                    "prompt": prompt,
                    "feedback": st.session_state.feedback_b["rating"],
                    "note": note_b
                })
            st.success("Feedback submitted!")

# Automated Evaluation
with automated_tab:
    st.markdown("### Automated Evaluation Setup")
    
    # Add tab for choosing input method
    input_method = st.radio("Choose input method:", ["Upload CSV", "Manual Entry"], horizontal=True)
    
    if input_method == "Upload CSV":
        st.markdown("""Upload a CSV file with test cases. The CSV should have two columns:
        1. **Question**: The question to test
        2. **Answer**: The expected response (can be a single value, CSV format, or JSON)
        """)
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        if uploaded_file is not None:
            try:
                # Read CSV with a different delimiter since the test data contains commas
                df = pd.read_csv(uploaded_file, delimiter=",", quoting=csv.QUOTE_MINIMAL)
                if "Question" not in df.columns or "Answer" not in df.columns:
                    st.error("CSV must contain 'Question' and 'Answer' columns")
                else:
                    if st.button("Load Test Cases"):
                        # Clear existing questions
                        st.session_state.evaluation_suite["questions"] = []
                        
                        # Add each row as a test case
                        for _, row in df.iterrows():
                            parsed_response = parse_expected_response(row["Answer"])
                            if parsed_response is not None:
                                st.session_state.evaluation_suite["questions"].append({
                                    "question": row["Question"],
                                    "expected_response": row["Answer"],
                                    "parsed_response": parsed_response
                                })
                        st.success(f"Loaded {len(df)} test cases!")
            except Exception as e:
                st.error(f"Error loading CSV: {str(e)}")
    
    else:  # Manual Entry
        st.markdown("""Add test cases with their expected responses. Each test case should include:
        1. A question to test
        2. The expected response (single value, JSON, or CSV format)
        """)
        
        # Add new question form
        with st.form("add_question"):
            question = st.text_input("Question:")
            expected_response = st.text_area("Expected Response (single value, JSON, or CSV):", height=150)
            add_submitted = st.form_submit_button("Add Test Case")
            
            if add_submitted and question and expected_response:
                if len(st.session_state.evaluation_suite["questions"]) < 5:
                    parsed_response = parse_expected_response(expected_response)
                    if parsed_response is not None:
                        st.session_state.evaluation_suite["questions"].append({
                            "question": question,
                            "expected_response": expected_response,
                            "parsed_response": parsed_response
                        })
                        st.success("Test case added!")
                else:
                    st.error("Maximum 5 test cases allowed!")

    # Display added questions
    if st.session_state.evaluation_suite["questions"]:
        st.markdown("### Test Cases")
        for i, q in enumerate(st.session_state.evaluation_suite["questions"]):
            with st.expander(f"Test Case {i+1}"):
                st.write(f"**Question:** {q['question']}")
                st.write("**Expected Response:**")
                if isinstance(q['parsed_response'], pd.DataFrame):
                    st.dataframe(q['parsed_response'])
                else:
                    st.write(q['expected_response'])
                if st.button(f"Remove Test Case {i+1}"):
                    st.session_state.evaluation_suite["questions"].pop(i)
                    st.rerun()

        # Start evaluation suite button
        if len(st.session_state.evaluation_suite["questions"]) > 0:
            if st.button("Run All Tests"):
                st.session_state.evaluation_suite["running"] = True
                st.rerun()

    # Run evaluation suite
    if st.session_state.evaluation_suite["running"]:
        st.markdown("### Running Tests...")
        progress_bar = st.progress(0)
        
        # Run through all questions automatically
        for idx, question_data in enumerate(st.session_state.evaluation_suite["questions"]):
            progress_bar.progress((idx + 1) / len(st.session_state.evaluation_suite["questions"]))
            
            # Query both models
            model_a_result, model_a_query = query_data(question_data['question'], model_1_id)
            model_b_result, model_b_query = query_data(question_data['question'], model_2_id)

            # Compare results and store evaluation
            if model_a_result is not None:
                model_a_passed = compare_results(model_a_result, question_data['parsed_response'])
                st.session_state.evaluations.append({
                    "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "model": "Model A",
                    "model_id": model_1_id,
                    "prompt": question_data['question'],
                    "expected_response": question_data['expected_response'],
                    "actual_response": model_a_result.to_csv(index=False) if isinstance(question_data['parsed_response'], pd.DataFrame) else str(model_a_result.iloc[0, 0]),
                    "result": "✅ PASS" if model_a_passed else "❌ FAIL"
                })

            if model_b_result is not None:
                model_b_passed = compare_results(model_b_result, question_data['parsed_response'])
                st.session_state.evaluations.append({
                    "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "model": "Model B",
                    "model_id": model_2_id,
                    "prompt": question_data['question'],
                    "expected_response": question_data['expected_response'],
                    "actual_response": model_b_result.to_csv(index=False) if isinstance(question_data['parsed_response'], pd.DataFrame) else str(model_b_result.iloc[0, 0]),
                    "result": "✅ PASS" if model_b_passed else "❌ FAIL"
                })

        # Complete the evaluation
        progress_bar.progress(1.0)
        st.session_state.evaluation_suite["running"] = False
        st.success("🎉 Test Suite Complete! Check the results below.")

# Show evaluation history
if st.session_state.evaluations:
    # Convert evaluations to DataFrame
    df_evals = pd.DataFrame(st.session_state.evaluations)
    
    # Create summary based on evaluation type
    if 'result' in df_evals.columns:  # Automatic comparison results
        summary = df_evals.groupby('model').agg({
            'result': [
                ('Total Tests', 'count'),
                ('Passed', lambda x: (x == '✅ PASS').sum()),
                ('Failed', lambda x: (x == '❌ FAIL').sum()),
                ('Pass Rate %', lambda x: (x == '✅ PASS').mean() * 100)
            ]
        })
        summary.columns = summary.columns.get_level_values(1)
        summary['Pass Rate %'] = summary['Pass Rate %'].apply(lambda x: f"{x:.1f}%")
    else:  # Manual feedback
        summary = df_evals.groupby('model').agg({
            'feedback': [
                ('Total Evaluations', 'count'),
                ('👍 Count', lambda x: (x == '👍').sum()),
                ('👎 Count', lambda x: (x == '👎').sum()),
                ('Net Positive %', lambda x: (x == '👍').mean() * 100)
            ]
        })
        summary.columns = summary.columns.get_level_values(1)
        summary['Net Positive %'] = summary['Net Positive %'].apply(lambda x: f"{x:.1f}%")
    

    # Display detailed history
    st.markdown("### Detailed History")
    if 'result' in df_evals.columns:
        # Convert DataFrame to string format to avoid Arrow serialization issues
        history_df = df_evals.sort_values('timestamp', ascending=False).copy()
        for col in history_df.columns:
            if col == 'actual_response' and isinstance(history_df[col].iloc[0], dict):
                # Convert dictionary to CSV string for actual_response
                history_df[col] = history_df[col].apply(lambda x: pd.DataFrame(x).to_csv(index=False) if isinstance(x, dict) else str(x))
            else:
                history_df[col] = history_df[col].astype(str)
        
        st.dataframe(history_df[['timestamp', 'model', 'prompt', 'expected_response', 'actual_response', 'result']])
    else:
        history_df = df_evals.sort_values('timestamp', ascending=False)[
            ['timestamp', 'model', 'prompt', 'feedback', 'note']
        ]
        st.dataframe(history_df.astype(str))

    # Display summary
    st.markdown("### Evaluation Results")
    st.dataframe(summary.astype(str))
    

st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.8rem; font-style: italic;">
        Built on <a href="https://omni.co/" style="color: #666; text-decoration: none;">Omni</a> and vibes ✨
    </div>
""", unsafe_allow_html=True)
