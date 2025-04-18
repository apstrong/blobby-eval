# Blobby's Evaluation MVP

A Streamlit application for comparing and evaluating two AI models' responses to natural language queries about eCommerce data.

## Features

- Side-by-side comparison of two AI models
- Real-time query execution
- Feedback collection with thumbs up/down ratings
- Query details inspection
- Evaluation history tracking

## Setup

1. Clone the repository:
```bash
git clone git@github.com:apstrong/blobby-eval.git
cd blobby-eval
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your API credentials:
```
OMNI_API_KEY=your_api_key_here
OMNI_BASE_URL=your_api_base_url_here
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. Open your browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

3. Configure your model URLs in the sidebar

4. Enter your query in the text input field

5. Compare the responses from both models

6. Provide feedback using the thumbs up/down buttons and optional notes

7. View your evaluation history at the bottom of the page
