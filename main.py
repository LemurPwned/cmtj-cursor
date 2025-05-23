import os
import argparse
from flow import coding_agent_flow
from loguru import logger


def main():
    """
    Run the coding agent to help with code operations
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Coding Agent - AI-powered coding assistant"
    )
    parser.add_argument(
        "--query", "-q", type=str, help="User query to process", required=False
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
        required=False,
    )
    parser.add_argument(
        "--working-dir",
        "-d",
        type=str,
        default=os.path.join(os.getcwd(), "project"),
        help="Working directory for file operations (default: current directory)",
    )

    args = parser.parse_args()
    if args.interactive:
        interactive(args.working_dir)
    elif args.query:
        run_flow(args.working_dir, args.query)
    else:
        logger.error("No query provided via command line or interactive mode")
        exit(1)


def run_flow(working_dir: str, user_query: str):
    # If no query provided via command line, ask for it
    if not user_query:
        user_query = input("What would you like me to help you with? ")

    # Initialize shared memory
    shared = {
        "user_query": user_query,
        "working_dir": working_dir,
        "history": [],
        "response": None,
    }

    logger.info(f"Working directory: {working_dir}")

    # Run the flow
    coding_agent_flow.run(shared)


def interactive(working_dir: str):
    """
    Run the coding agent in interactive mode, continually asking for user input
    """

    # Main interaction loop
    shared = {
        "working_dir": working_dir,
        "history": [],
        "response": None,
    }
    while True:
        # Get user input
        user_query = input("\n>> What would you like me to help you with?\n>>")

        # Check for exit command
        if user_query.lower() in ["exit", "quit"]:
            print("Exiting interactive mode. Goodbye!")
            break

        # Update shared context with new query
        shared["user_query"] = user_query

        # Run the flow
        coding_agent_flow.run(shared)


if __name__ == "__main__":
    main()
