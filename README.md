# Cursor-CMTJ

Simple simulation codebase agent based on the Pocket Cursor Tutorial.

## Sources

- Forked from [`The-Pocket/PocketFlow-Tutorial-Cursor`](https://github.com/The-Pocket/PocketFlow-Tutorial-Cursor)
- Generates code and Q&A for the [`cmtj` codebase](https://github.com/LemurPwned/cmtj)

## Streamlit Application

A minimal Streamlit web app (`streamlit_app.py`) exposes a chat interface powered by the coding agent.
Responses are streamed to the page and each includes an "Intermediate Steps" section
in a collapsed expander to review the underlying actions.

To run locally with Docker:

```bash
docker build -f Dockerfile.streamlit -t cmtj-chat .
docker run -p 8501:8501 -e OPENAI_API_KEY=your-key cmtj-chat
```

Open `http://localhost:8501` to access the chat UI.
