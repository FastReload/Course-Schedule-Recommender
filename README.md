
# Course Schedule Recommender (Google ADK + Streamlit)

Multi-agent course scheduling assistant built on Google’s Agent Development Kit (ADK). The Streamlit app provides a guided onboarding flow (verify Student ID, confirm major, choose term, enter desired courses) and then opens a free-form chat that routes to the right specialist agent.

## Screenshot

![Streamlit sidebar onboarding](Screenshot%202026-01-03%20202429.png)

## What This Does

- Verifies a student by Student ID (via the Student sub-agent + BigQuery tool)
- Routes the conversation to the right major-specific scheduling agent (CS or ME)
- Uses Online agent for professor/program/resource lookups
- Lets the student continue chatting freely after the initial context is collected

## Architecture

The root ADK agent delegates to sub-agents:

- Student agent: uses a BigQuery-backed tool to fetch student info (major + courses taken)
- CS agent: CS course planning and RAG retrieval
- ME agent: ME course planning and RAG retrieval
- Online agent: external lookups

The Streamlit UI runs the root agent using ADK’s `InMemoryRunner` and keeps a persistent `(user_id, session_id)`.

## Project Layout

```
Course Schedule Recommender/
├── streamlit_app.py               # Streamlit UI (guided onboarding + chat)
├── frontend/
│   ├── __init__.py
│   └── adk_runtime.py             # ADK runner/session bridge
├── main_agent/
│   ├── agent.py                   # Root agent (routes to sub-agents)
│   ├── prompt.py                  # Root prompt
│   ├── requirements.txt           # Pip install option
│   └── sub_agents/
│       ├── CS/                    # CS scheduling agent + prompt
│       ├── ME/                    # ME scheduling agent + prompt
│       ├── ONLINE/                # Web/resource agent + prompt
│       └── Student/               # BigQuery student agent + prompt
├── .env.example                   # Template for environment variables
├── pyproject.toml                 # Poetry project definition
└── poetry.lock
```

## Setup (Windows / macOS / Linux)

### Requirements

- Python 3.11 (recommended for this repo)
- Google credentials for whichever Gemini mode you use (AI Studio key or Vertex AI)

### 1) Create environment variables

This repo intentionally does NOT commit a `.env`. Use `.env.example` as a template:

1. Copy `.env.example` to `.env`
2. Fill in values

Important: `.env` is ignored by git via `.gitignore`.

### 2) Install dependencies

Option A — Poetry:

```bash
poetry install
```

Option B — pip + venv:

```bash
python -m venv .venv

# Windows:
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r main_agent/requirements.txt

# macOS/Linux:
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r main_agent/requirements.txt
```

### 3) Run the Streamlit app

Poetry:

```bash
poetry run streamlit run streamlit_app.py
```

pip + venv:

```bash
streamlit run streamlit_app.py
```

Open: `http://localhost:8501`

## Streamlit Flow (How To Use)

1. Enter Student ID and click “Verify Student ID”
2. Confirm major (this triggers routing to the correct sub-agent)
3. Enter quarter + year
4. Enter desired courses
5. Chat freely

## Environment Variables

The full list lives in `.env.example`, but the important ones are:

### Gemini / ADK auth (choose one)

- AI Studio:
	- `GOOGLE_API_KEY`

- Vertex AI:
	- `GOOGLE_GENAI_USE_VERTEXAI=TRUE`
	- `GOOGLE_CLOUD_PROJECT`
	- `GOOGLE_CLOUD_LOCATION`

### Sub-agent requirements

- `CS_CORPUS` and `ME_CORPUS` (Vertex AI RAG corpora IDs)
- `BIGQUERY_STUDENT_INFO_TABLE` (BigQuery table with curated student + course history)

## Notes / Common Issues

- Student verification depends on BigQuery access and `BIGQUERY_STUDENT_INFO_TABLE`.
- The Student BigQuery query currently uses `FROM_BASE64(student_id)`. If your IDs are not base64-encoded, update the query in `main_agent/sub_agents/Student/agent.py`.
- If Streamlit fails with Arrow / `pyarrow` errors on Windows, a working combo is:
	- `numpy<2` and `pyarrow==14.0.2`

## GitHub Safety

- `.env` is ignored (only `.env.example` should be committed)
- `.venv/`, `__pycache__/`, and other local artifacts are ignored

## License

MIT. See [LICENSE](LICENSE).

