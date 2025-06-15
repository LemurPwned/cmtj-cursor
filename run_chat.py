#!/usr/bin/env python3
"""
Simple runner script for the CMTJ Chat Assistant Streamlit app.
"""

import os
import subprocess
import sys
from pathlib import Path


def setup_environment():
    """Setup environment variables and paths"""
    # Set up logging directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Set environment variables
    os.environ["LOG_DIR"] = str(log_dir)

    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY environment variable is not set.")
        print("   Please set it before running the chat app:")
        print("   export OPENAI_API_KEY='your-api-key-here'")
        print()


def run_streamlit_app():
    """Run the Streamlit chat application"""
    try:
        print("🚀 Starting CMTJ Chat Assistant...")
        print("📱 The app will open in your default web browser")
        print("🛑 Press Ctrl+C to stop the application")
        print()

        # Run streamlit with the chat app
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "chat_app.py",
                "--server.port",
                "8501",
                "--server.address",
                "localhost",
                "--browser.gatherUsageStats",
                "false",
            ],
            check=True,
        )

    except KeyboardInterrupt:
        print("\n👋 Chat application stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running Streamlit: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def main():
    """Main function"""
    print("=" * 50)
    print("🤖 CMTJ Chat Assistant Runner")
    print("=" * 50)

    # Setup environment
    setup_environment()

    # Run the app
    run_streamlit_app()


if __name__ == "__main__":
    main()
