import os
import re
import sys
from typing import Any, Optional

from loguru import logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from index.api_builder import build_api_docs

API_DOC_STRINGS = None


def get_api_docstrings(query: str, working_dir: str, free_text: bool = False) -> list[dict[str, Any]] | None:
    """Get the api docstrings for the given query."""
    global API_DOC_STRINGS
    if API_DOC_STRINGS is None:
        API_DOC_STRINGS = build_api_docs(working_dir)

    if free_text:
        return search_api_docstrings_regex(query, working_dir)

    return API_DOC_STRINGS.get(query, None)


def search_api_docstrings_regex(
    query: str, working_dir: str, case_sensitive: bool = False, max_results: int = 50
) -> list[dict[str, Any]]:
    """Search API docstrings using regex pattern matching over signatures and docstrings.

    Args:
        query: Regex pattern to search for
        working_dir: Directory to build API docs from
        case_sensitive: Whether the search should be case sensitive
        max_results: Maximum number of results to return

    Returns:
        List of matching API entries with metadata about where the match was found
    """
    global API_DOC_STRINGS
    if API_DOC_STRINGS is None:
        API_DOC_STRINGS = build_api_docs(working_dir)

    results = []

    try:
        # Compile the regex pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query, flags)
    except re.error as e:
        logger.error(f"Invalid regex pattern: {str(e)}")
        return []

    for name, info in API_DOC_STRINGS.items():
        if len(results) >= max_results:
            break

        matches = []

        # Search in the name/signature
        if pattern.search(name):
            matches.append({"location": "name", "text": name})

        # Build signature string for functions/methods
        if isinstance(info, dict):
            if "args" in info and "returns" in info:
                # This is a function or method
                args_str = ", ".join(
                    [f"{arg}: {typ}" if typ else arg for arg, typ in (info.get("args", {}) or {}).items()]
                )
                returns_str = info.get("returns", "")
                signature = f"{name}({args_str})"
                if returns_str:
                    signature += f" -> {returns_str}"

                if pattern.search(signature):
                    matches.append({"location": "signature", "text": signature})

            # Search in docstring
            docstring = info.get("docstring")
            if docstring and pattern.search(docstring):
                matches.append({"location": "docstring", "text": docstring})

            # For classes, search in methods and attributes
            if "methods" in info:
                for method_name, method_info in info["methods"].items():
                    full_method_name = f"{name}.{method_name}"
                    if pattern.search(full_method_name):
                        matches.append({"location": "method_name", "text": full_method_name})

                    # Search method docstring
                    method_docstring = method_info.get("docstring")
                    if method_docstring and pattern.search(method_docstring):
                        matches.append(
                            {
                                "location": "method_docstring",
                                "text": method_docstring,
                                "method": method_name,
                            }
                        )

                    # Search method signature
                    method_args = method_info.get("args", {}) or {}
                    method_args_str = ", ".join([f"{arg}: {typ}" if typ else arg for arg, typ in method_args.items()])
                    method_returns = method_info.get("returns", "")
                    method_signature = f"{full_method_name}({method_args_str})"
                    if method_returns:
                        method_signature += f" -> {method_returns}"

                    if pattern.search(method_signature):
                        matches.append(
                            {
                                "location": "method_signature",
                                "text": method_signature,
                                "method": method_name,
                            }
                        )

            # Search in class attributes
            if "attributes" in info:
                for attr_name, attr_info in info["attributes"].items():
                    full_attr_name = f"{name}.{attr_name}"
                    if pattern.search(full_attr_name):
                        matches.append({"location": "attribute_name", "text": full_attr_name})

                    attr_type = attr_info.get("type")
                    if attr_type and pattern.search(attr_type):
                        matches.append(
                            {
                                "location": "attribute_type",
                                "text": f"{full_attr_name}: {attr_type}",
                                "attribute": attr_name,
                            }
                        )

        # If we found matches, add this API entry to results
        if matches:
            results.append({"name": name, "info": info, "matches": matches})

    return results


def fetch_gitignore(working_dir: str) -> str:
    """Fetch the gitignore file for the given working directory."""
    gitignore_path = os.path.join(working_dir, ".gitignore")
    if not os.path.exists(gitignore_path):
        return ""
    with open(gitignore_path) as f:
        return f.read()


def grep_search(
    query: str,
    case_sensitive: bool = True,
    include_pattern: Optional[str] = None,
    exclude_pattern: Optional[str] = None,
    working_dir: str = "",
) -> tuple[list[dict[str, Any]], bool]:
    """
    Search through files for specific patterns using regex.
    Allowed extensions: *.py, *.js, *.ts, *.tsx, *.css, *.html, *.json, *.md, *.txt, *.yaml, *.yml, *.toml, *.ini, *.env, *.lock, *.log, *.csv, *.jsonl, *.jsonl.gz, *.jsonl.bz2, *.jsonl.zip, *.jsonl.tar, *.jsonl.tar.gz, *.jsonl.tar.bz2, *.jsonl.tar.zip, *.jsonl.tar.tar.gz, *.jsonl.tar.tar.bz2, *.jsonl.tar.tar.zip

    Args:
        query: Regex pattern to find
        case_sensitive: Whether the search is case sensitive
        include_pattern: Glob pattern for files to include (e.g., "*.py")
        exclude_pattern: Glob pattern for files to exclude
        working_dir: Directory to search in (defaults to current directory if empty)

    Returns:
        Tuple of (list of matches, success status)
        Each match contains:
        {
            "file": file path,
            "line_number": line number (1-indexed),
            "content": matched line content
        }
    """  # noqa: E501
    results = []
    search_dir = working_dir if working_dir else "."
    forbidden_extensions = fetch_gitignore(working_dir)
    forbidden_extensions = forbidden_extensions.split("\n")
    forbidden_extensions = [extension.strip() for extension in forbidden_extensions if extension.strip()]

    # Convert gitignore patterns to regex for matching
    gitignore_regexes = _glob_to_regex(",".join(forbidden_extensions)) if forbidden_extensions else []

    try:
        # Compile the regex pattern
        try:
            pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {str(e)}")
            return [], False

        # Convert glob patterns to regex for file matching
        include_regexes = _glob_to_regex(include_pattern) if include_pattern else None
        exclude_regexes = _glob_to_regex(exclude_pattern) if exclude_pattern else None

        # Walk through the directory and search files
        for root, _, files in os.walk(search_dir):
            for filename in files:
                # Skip files that don't match inclusion pattern
                if include_regexes and not any(r.match(filename) for r in include_regexes):
                    continue

                # Skip files that match exclusion pattern
                if exclude_regexes and any(r.match(filename) for r in exclude_regexes):
                    continue

                file_path = os.path.join(root, filename)

                relative_path = os.path.relpath(file_path, search_dir)

                # Skip files that match gitignore patterns
                if any(r.match(relative_path) or r.match(filename) for r in gitignore_regexes):
                    continue

                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append(
                                    {
                                        "file": file_path,
                                        "line_number": i,
                                        "content": line.rstrip(),
                                    }
                                )

                                # Limit to 50 results
                                if len(results) >= 50:
                                    break
                except Exception:
                    # Skip files that can't be read
                    continue

                if len(results) >= 50:
                    break

            if len(results) >= 50:
                break

        return results, True

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return [], False


def _glob_to_regex(pattern_str: str) -> list[re.Pattern]:
    """Convert comma-separated glob patterns to regex patterns."""
    patterns = []

    for glob in pattern_str.split(","):
        glob = glob.strip()
        if not glob:
            continue

        # Convert glob syntax to regex
        regex = (
            glob.replace(".", r"\.")  # Escape dots
            .replace("*", r".*")  # * becomes .*
            .replace("?", r".")
        )  # ? becomes .

        try:
            patterns.append(re.compile(f"^{regex}$"))
        except re.error:
            # Skip invalid patterns
            continue

    return patterns


if __name__ == "__main__":
    # Test the grep search function
    # print("Testing basic search for 'def' in Python files:")
    # results, success = grep_search("def", include_pattern="*.py")
    # print(f"Search success: {success}")
    # print(f"Found {len(results)} matches")
    # for result in results[:5]:  # Print first 5 results
    #     print(f"{result['file']}:{result['line_number']}: {result['content'][:50]}...")

    # # Test case for searching CSS color patterns with regex
    # print("\nTesting CSS color search with regex:")
    # css_query = r"background-color|background:|backgroundColor|light blue|#add8e6|rgb\(173, 216, 230\)"
    # css_results, css_success = grep_search(
    #     query=css_query,
    #     case_sensitive=False,
    #     include_pattern="*.css,*.html,*.js,*.jsx,*.ts,*.tsx",
    # )
    # print(f"Search success: {css_success}")
    # print(f"Found {len(css_results)} matches")
    # for result in css_results[:5]:
    #     print(f"{result['file']}:{result['line_number']}: {result['content'][:50]}...")

    # Test the new API docstring regex search
    print("\nTesting API docstring regex search:")
    api_results = search_api_docstrings_regex(
        query=r"vector|embedding", working_dir="./cmtj/cmtj", case_sensitive=False
    )
    print(f"Found {len(api_results)} API matches")
    for result in api_results[:3]:
        print(f"API: {result['name']}")
        for match in result["matches"]:
            print(f"  - {match['location']}: {match['text']}")
