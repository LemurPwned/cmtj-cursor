# Cursor-CMTJ

Simple simulation codebase agent basing off the Pocket Cursor Tutorial.
Designed for [CMTJ library](https://github.com/LemurPwned/cmtj).

## Overview

This project provides both a **Streamlit chat interface** and a **command-line interface** for interacting with the [CMTJ library](https://github.com/LemurPwned/cmtj). It can generate code, answer questions about spintronics, and help with CMTJ simulations.

## Quick Start with Docker

The easiest way to run the application is using Docker:

### Prerequisites

- Docker and Docker Compose installed on your system

### Running the Chat App (Recommended)

```bash
docker-compose up -d cmtj-chat
```

The chat app will be available at: **http://localhost:8501**


## Local Development

## Features

### Chat Interface

- **Code Generation**: Generate CMTJ simulation code
- **Q&A**: Ask questions about spintronics and CMTJ
- **Document Search**: Search through CMTJ documentation
- **Interactive UI**: Modern Streamlit interface

### CLI Interface

- **Interactive Mode**: Command-line interface for code generation
- **Working Directory**: Generates code in specified directory
- **Logging**: Comprehensive logging with Loguru

## Project Structure

```
├── chat_app.py           # Streamlit chat interface
├── main.py              # CLI interface
├── codegen_flow.py      # Main code generation flow
├── search_agent.py      # Document search functionality
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose setup
├── run_docker.sh        # Docker runner script
├── requirements.txt     # Python dependencies
├── assets/              # UI assets (icons, etc.)
├── _cmtj/              # Generated code output directory
└── knowledge_base/      # PDF documents for search
```

## Configuration

### Environment Variables

- `LOGURU_LEVEL`: Logging level (default: INFO)
- `STREAMLIT_SERVER_PORT`: Streamlit port (default: 8501)
- `STREAMLIT_SERVER_ADDRESS`: Streamlit address (default: 0.0.0.0)

### Chat App Settings

- **Web Search**: Toggle web search on/off in the sidebar
- **Clear History**: Clear chat history anytime
- **Working Directory**: Code is generated in `_cmtj/` directory

## Sources

- Forked from [`The-Pocket/PocketFlow-Tutorial-Cursor`](https://github.com/The-Pocket/PocketFlow-Tutorial-Cursor)
- Generates code and Q&A for the `cmtj` codebase: https://github.com/LemurPwned/cmtj
