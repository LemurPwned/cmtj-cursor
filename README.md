# Cursor-CMTJ

Simple simulation codebase agent basing off the Pocket Cursor Tutorial

## Overview

This project provides both a **Streamlit chat interface** and a **command-line interface** for interacting with the CMTJ (Computational Micromagnetics Toolkit for Julia) library. It can generate code, answer questions about spintronics, and help with CMTJ simulations.

## Quick Start with Docker

The easiest way to run the application is using Docker:

### Prerequisites

- Docker and Docker Compose installed on your system

### Running the Chat App (Recommended)

```bash
# Build and run the chat app
./run_docker.sh chat

# Or manually with docker-compose
docker-compose up -d cmtj-chat
```

The chat app will be available at: **http://localhost:8501**

### Running the CLI Interface

```bash
# Run the interactive CLI
./run_docker.sh cli

# Or manually with docker-compose
docker-compose --profile cli run --rm cmtj-cli
```

### Docker Commands

```bash
./run_docker.sh build    # Build the Docker image
./run_docker.sh chat     # Run chat app (default)
./run_docker.sh cli      # Run interactive CLI
./run_docker.sh stop     # Stop all containers
./run_docker.sh clean    # Clean up containers and images
./run_docker.sh logs     # Show chat app logs
./run_docker.sh help     # Show help
```

## Local Development

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the chat app locally
streamlit run chat_app.py

# Or run the CLI
python main.py --interactive --working-dir ./cmtj
```

## Features

### Chat Interface

- **Code Generation**: Generate CMTJ simulation code
- **Q&A**: Ask questions about spintronics and CMTJ
- **Web Search**: Optional web search for comprehensive answers
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
