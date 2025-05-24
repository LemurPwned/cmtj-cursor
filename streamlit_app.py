import os

import streamlit as st

from flow import coding_agent_flow, format_history_summary

st.set_page_config(page_title="CMTJ Code Chat")

STARTER_QUESTIONS = [
    "How do I set up a basic LLG simulation?",
    "Show an example using FieldScan.",
    "How can I chain multiple Junction objects?",
]


def init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "history" not in st.session_state:
        st.session_state.history = []


def run_flow(query: str, callback=None) -> tuple[str, str]:
    """Run the coding agent flow with optional streaming callback."""
    shared = {
        "user_query": query,
        "working_dir": os.getcwd(),
        "history": st.session_state.history,
        "response": None,
    }
    if callback:
        shared["stream_callback"] = callback
    coding_agent_flow.run(shared)
    st.session_state.history = shared["history"]
    summary = format_history_summary(shared["history"])
    return shared.get("response", ""), summary


init_state()
st.title("CMTJ Code Chat")

with st.expander("Starter Questions"):
    cols = st.columns(1)
    for q in STARTER_QUESTIONS:
        if st.button(q):
            st.session_state.user_input = q

user_prompt = st.chat_input("Ask a question about cmtj...")
if user_prompt:
    st.session_state.user_input = user_prompt

if "user_input" in st.session_state:
    query = st.session_state.pop("user_input")
    st.session_state.messages.append({"role": "user", "content": query})
    placeholder = st.chat_message("assistant")

    def stream_cb(chunk: str):
        placeholder.write_stream(chunk)

    response, summary = run_flow(query, callback=stream_cb)
    st.session_state.messages.append({"role": "assistant", "content": response, "summary": summary})

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])
    if msg.get("summary"):
        with st.expander("Intermediate Steps"):
            st.markdown(msg["summary"])
