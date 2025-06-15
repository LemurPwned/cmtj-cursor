import os
import traceback
from datetime import datetime

import streamlit as st
from loguru import logger

from codegen_flow import main_flow

WORKING_DIR = os.environ.get("WORKING_DIR", "./_cmtj")


def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    # Add web search setting to session state
    if "enable_web_search" not in st.session_state:
        st.session_state.enable_web_search = False  # disable for now
    # Add model selection to session state
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "o4-mini"  # default model


def add_message(role: str, content: str):
    """Add a message to the chat history"""
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    st.session_state.messages.append(message)


def process_user_query(user_query: str, enable_web_search: bool = True, model: str = "o4-mini") -> str:
    """Process user query using the codegen flow"""
    try:
        # Create shared state for the flow
        shared = {
            "user_query": user_query,
            "working_dir": WORKING_DIR,
            "history": [],
            "response": None,
            "enable_web_search": enable_web_search,  # Add web search setting
            "model": model,  # Add model selection
        }

        # Get the main flow with web search setting
        flow = main_flow(enable_web_search=enable_web_search)

        # Run the flow
        flow.run(shared=shared)

        # Return the response
        return shared.get("response", "I apologize, but I couldn't generate a response to your query.")

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"I encountered an error while processing your query: {str(e)}"


def display_chat_messages():
    """Display all chat messages"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            st.caption(f"*{message['timestamp']}*")


def main():
    """Main Streamlit app"""
    st.set_page_config(page_title="CMTJ Chat Assistant", page_icon="assets/icon.svg", layout="wide")

    col1, col2 = st.columns([1, 8])
    with col1:
        st.image("assets/icon.svg", width=60)
    with col2:
        st.title("CMTJ Chat Assistant")
    st.markdown("Ask questions about CMTJ library or request code generation!")

    # Initialize session state
    initialize_session_state()

    # Sidebar with chat controls
    with st.sidebar:
        st.header("Chat Controls")

        if st.button("Clear Chat History", type="secondary"):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.rerun()

        st.markdown("---")
        st.markdown("### Settings")

        # Model selection
        model_options = {
            "o4-mini": "o4-mini (Fast, Cost-effective)",
            "o4": "o4 (Balanced Performance)",
            "gpt-4o": "GPT-4o (High Performance)",
            "gpt-4o-mini": "GPT-4o Mini (Fast, Efficient)",
            "gpt-4-turbo": "GPT-4 Turbo (Advanced)",
        }

        st.session_state.selected_model = st.selectbox(
            "Select Model",
            options=list(model_options.keys()),
            index=list(model_options.keys()).index(st.session_state.selected_model),
            format_func=lambda x: model_options[x],
            help="Choose the AI model for processing your requests. "
            "Different models offer different trade-offs between speed, cost, and performance.",
        )

        # Web search toggle
        st.session_state.enable_web_search = st.toggle(
            "Enable Web Search",
            value=st.session_state.enable_web_search,
            help="When enabled, the assistant will search the web for "
            "additional information to answer your questions. This may make responses slower but more comprehensive.",
        )

        # Show current status
        web_status = "🌐 Enabled" if st.session_state.enable_web_search else "📚 Document-only"
        model_status = model_options[st.session_state.selected_model]
        st.caption(f"Model: {model_status}")
        st.caption(f"Web Search: {web_status}")

        st.markdown("---")
        st.markdown("### About")
        st.markdown(
            """
        This chat assistant can help you with:
        - **Code Generation**: Create CMTJ simulation code
        - **Questions**: Answer questions about spintronics and CMTJ
        - **Documentation**: Search through CMTJ library documentation
        """
        )

        st.markdown("---")
        st.markdown(f"**Messages in chat:** {len(st.session_state.messages)}")

    # Display existing chat messages
    display_chat_messages()

    # Chat input
    if prompt := st.chat_input("Ask me anything about CMTJ or request code generation..."):
        # Add user message to chat
        add_message("user", prompt)

        # Display user message immediately
        with st.chat_message("user", avatar="👨‍🚀"):
            st.markdown(prompt)
            st.caption(f"*{datetime.now().strftime('%H:%M:%S')}*")

        # Process the query with loading spinner
        with st.chat_message("assistant", avatar="assets/icon.svg"):
            search_status = "🌐 with web search" if st.session_state.enable_web_search else "📚 document search only"
            model_name = st.session_state.selected_model
            with st.spinner(f"🤔 Thinking and processing your request using {model_name} {search_status}..."):
                response = process_user_query(
                    prompt,
                    st.session_state.enable_web_search,
                    st.session_state.selected_model,
                )

            # Display the response
            st.markdown(response)
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.caption(f"*{timestamp}*")

            # Add assistant response to chat history
            add_message("assistant", response)


if __name__ == "__main__":
    main()
