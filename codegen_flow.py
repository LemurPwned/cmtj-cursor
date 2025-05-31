from datetime import datetime
from typing import Any

import yaml
from loguru import logger
from pocketflow import Flow, Node

from flow import (
    FormatResponseNode,
    GrepSearchAction,
    ListDirAction,
    ReadFileAction,
)
from utils.call_llm import call_llm
from utils.compile_ops import validate_code
from utils.get_rules import get_rules
from utils.search_ops import (
    get_api_docstrings,
    search_api_docstrings_regex,
)


def format_history_summary(history: list[dict[str, Any]]) -> str:
    if not history:
        return "No previous actions."

    history_str = "\n"

    for i, action in enumerate(history):
        # Header for all entries - removed timestamp
        history_str += f"Action {i+1}:\n"
        history_str += f"- Tool: {action['tool']}\n"
        history_str += f"- Reason: {action['reason']}\n"

        # Add parameters
        if params := action.get("params", {}):
            history_str += "- Parameters:\n"
            for k, v in params.items():
                history_str += f"  - {k}: {v}\n"

        # Add detailed result information
        if result := action.get("result"):
            if isinstance(result, dict):
                success = result.get("success", False)
                history_str += f"- Result: {'Success' if success else 'Failed'}\n"

                # Add tool-specific details
                if action["tool"] == "read_file" and success:
                    content = result.get("content", "")
                    # Show full content without truncating
                    history_str += f"- Content: {content}\n"
                elif action["tool"] == "grep_search" and success:
                    matches = result.get("matches", [])
                    history_str += f"- Matches: {len(matches)}\n"
                    # Show all matches without limiting to first 3
                    for j, match in enumerate(matches):
                        history_str += f"  {j+1}. {match.get('file')}:{match.get('line')}: {match.get('content')}\n"
                elif action["tool"] == "list_dir" and success:
                    # Get the tree visualization string
                    tree_visualization = result.get("tree_visualization", "")
                    history_str += "- Directory structure:\n"

                    # Properly handle and format the tree visualization
                    if tree_visualization and isinstance(tree_visualization, str):
                        # First, ensure we handle any special line ending characters properly
                        clean_tree = tree_visualization.replace("\r\n", "\n").strip()

                        if clean_tree:
                            # Add each line with proper indentation
                            for line in clean_tree.split("\n"):
                                # Ensure the line is properly indented
                                if line.strip():  # Only include non-empty lines
                                    history_str += f"  {line}\n"
                        else:
                            history_str += "  (No tree structure data)\n"
                    else:
                        history_str += "  (Empty or inaccessible directory)\n"
                        logger.debug(f"Tree visualization missing or invalid: {tree_visualization}")
                elif action["tool"] == "search_api_docstrings_regex" and success:
                    matches = result.get("matches", [])
                    history_str += f"- API Matches: {len(matches)}\n"
                    # Show all matches with their details
                    for j, match in enumerate(matches):
                        history_str += f"  {j+1}. {match.get('name')} (score: {match.get('match_score', 0)})\n"

                        # Show match reasons
                        reasons = match.get("match_reasons", [])
                        if reasons:
                            history_str += f"     Reasons: {', '.join(reasons)}\n"

                        # Show search details (fuzzy score, semantic similarity)
                        details = match.get("search_details", {})
                        if details:
                            detail_parts = []
                            if "fuzzy_score" in details:
                                detail_parts.append(f"Fuzzy: {details['fuzzy_score']}%")
                            if "semantic_score" in details:
                                detail_parts.append(f"Semantic: {details['semantic_score']:.3f}")
                            if detail_parts:
                                history_str += f"     Details: {', '.join(detail_parts)}\n"

                        if match.get("docstring"):
                            # Truncate long docstrings for readability
                            docstring = match.get("docstring", "")
                            if len(docstring) > 150:
                                docstring = docstring[:150] + "..."
                            history_str += f"     Docstring: {docstring}\n"
                        if match.get("args"):
                            args_str = ", ".join(f"{k}: {v}" for k, v in match.get("args", {}).items())
                            if len(args_str) > 100:
                                args_str = args_str[:100] + "..."
                            history_str += f"     Args: {args_str}\n"
                        if match.get("returns"):
                            history_str += f"     Returns: {match.get('returns')}\n"
                        if match.get("methods"):
                            methods = match.get("methods", [])
                            if len(methods) > 5:
                                methods_str = ", ".join(methods[:5]) + f" (and {len(methods)-5} more)"
                            else:
                                methods_str = ", ".join(methods)
                            history_str += f"     Methods: {methods_str}\n"
                elif action["tool"] == "search_api_docstrings_regex" and not success:
                    message = result.get("message", "No matches found")
                    history_str += f"- API Search Result: {message}\n"
            else:
                history_str += f"- Result: {result}\n"

        # Add separator between actions
        history_str += "\n" if i < len(history) - 1 else ""

    return history_str


#############################################
# Main Decision Agent Node
#############################################
class MainDecisionAgent(Node):
    def prep(self, shared: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        # Get user query and history
        user_query = shared.get("user_query", "")
        history = shared.get("history", [])

        return user_query, history

    def exec(self, inputs: tuple[str, list[dict[str, Any]]]) -> dict[str, Any]:
        user_query, history = inputs
        logger.info(f"MainDecisionAgent: Analyzing user query: {user_query}")

        # Format history using the utility function with 'basic' detail level
        history_str = format_history_summary(history)

        # Create prompt for the LLM using YAML instead of JSON
        prompt = f"""You are a coding assistant that helps modify and navigate code. Given the following request,
decide which tool to use from the available options.
Do not finish until you provide a sample code. You can ask the user for more details, but always provide a sample code.
If the task ask you to write code, before you write any code, always do a thorough search first and then write the code.
When generating content for new files or editing existing files, follow these rules: {get_rules()}

User request: {user_query}

Here are the actions you performed:
{history_str}


If you have encountered an error from cmtj library, remember that you have access to the source code of the library.
You can use the source code to search and fix the error.
You can also use the search_api_docstrings_regex tool to search the signature or docstring of a class or function of cmtj library.

Available tools:
1. read_file: Read content from a file
   - Parameters: target_file (path)
   - Example:
     tool: read_file
     reason: I need to read the main.py file to understand its structure
     params:
       target_file: main.py

2. grep_search: Search for patterns in files
   - Parameters: query, case_sensitive (optional), include_pattern (optional), exclude_pattern (optional)
   - Example:
     tool: grep_search
     reason: I need to find all occurrences of 'logger' in Python files
     params:
       query: logger
       include_pattern: "*.py"
       case_sensitive: false

3. list_dir: List contents of a directory
   - Parameters: relative_workspace_path
   - Example:
     tool: list_dir
     reason: I need to see all files in the utils directory
     params:
       relative_workspace_path: utils
   - Result: Returns a tree visualization of the directory structure

4. search_api_docstrings_regex: Search the signature or docstring of a class or function of cmtj library. Can also do free text search.
   - Parameters: query
   - Example:
     tool: search_api_docstrings_regex
     reason: I need to check the signature or docstring of the class called "Junction"
     params:
       query: Junction
   - Result: Returns the signature and the docstring of the class or function

5. finish: End the process and provide final code output
   - No parameters required
   - Example:
     tool: finish
     reason: I have completed the requested task of finding all logger instances
     params: {{}}

Respond with a YAML object containing:
```yaml
tool: one of: read_file, edit_file, delete_file, grep_search, list_dir, finish
reason: |
  detailed explanation of why you chose this tool and what you intend to do
  if you chose finish, explain why no more actions are needed
params:
  # parameters specific to the chosen tool
```

If you believe no more actions are needed, use "finish" as the tool and explain why in the reason.
"""  # noqa: E501

        # Call LLM to decide action
        response = call_llm(prompt)
        if "```python" in response:
            # we actually got python code, so we need to validate it and correct it if needed
            python_blocks = response.split("```python")
            if len(python_blocks) > 1:
                python_content = python_blocks[1].split("```")[0].strip()
                python_code = python_content.replace("```python", "")
                return {
                    "tool": "validate_code",
                    "reason": "validate_code",
                    "params": {"code_content": python_code},
                }
        # Look for YAML structure in the response
        yaml_content = ""
        if "```yaml" in response:
            yaml_blocks = response.split("```yaml")
            if len(yaml_blocks) > 1:
                yaml_content = yaml_blocks[1].split("```")[0].strip()
        elif "```yml" in response:
            yaml_blocks = response.split("```yml")
            if len(yaml_blocks) > 1:
                yaml_content = yaml_blocks[1].split("```")[0].strip()
        elif "```" in response:
            # Try to extract from generic code block
            yaml_blocks = response.split("```")
            if len(yaml_blocks) > 1:
                yaml_content = yaml_blocks[1].strip()

        else:
            # If no code blocks, try to use the entire response
            yaml_content = response.strip()

        if yaml_content:
            try:
                decision = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                logger.error(f"YAML parsing error: {str(e)}")
                logger.error(f"LLM Response: {response}")
                logger.error(f"Extracted YAML content: {yaml_content}")
                raise ValueError(f"Invalid YAML format in LLM response: {str(e)}") from e

            # Validate the required fields
            assert "tool" in decision, "Tool name is missing"
            assert "reason" in decision, "Reason is missing"

            # For tools other than "finish", params must be present
            if decision["tool"] != "finish":
                assert "params" in decision, "Parameters are missing"
            else:
                decision["params"] = {}

            return decision
        else:
            logger.error(f"No YAML content found in LLM response: {response}")
            raise ValueError("No YAML object found in response")

    def post(self, shared: dict[str, Any], prep_res: Any, exec_res: dict[str, Any]) -> str:
        logger.info(f"MainDecisionAgent: Selected tool: {exec_res['tool']}")

        # Initialize history if not present
        if "history" not in shared:
            shared["history"] = []

        # Add this action to history
        shared["history"].append(
            {
                "tool": exec_res["tool"],
                "reason": exec_res["reason"],
                "params": exec_res.get("params", {}),
                "result": None,  # Will be filled in by action nodes
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Return the action to take
        return exec_res["tool"]


class SearchDocstring(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        if query := last_action["params"].get("query"):
            return {
                "query": query,
                "working_dir": shared.get("working_dir", ""),
            }
        raise ValueError("Missing query parameter")

    def exec(self, params: dict[str, Any]) -> Any:
        # Call get_api_docstrings utility which now returns a list of matches or a string message
        logger.warning(f"SearchDocstring: {params}")
        naive_search = get_api_docstrings(params["query"], params["working_dir"])
        if naive_search:
            return naive_search
        return search_api_docstrings_regex(params["query"], params["working_dir"])

    def post(self, shared: dict[str, Any], prep_res: dict[str, Any], exec_res: Any) -> str:
        # Update the result in the last history entry
        if history := shared.get("history", []):
            # Determine if the search was successful
            success = isinstance(exec_res, list) and len(exec_res) > 0
            history[-1]["result"] = {
                "success": success,
                "matches": exec_res if isinstance(exec_res, list) else [],
                "message": exec_res if isinstance(exec_res, str) else "",
            }


class CompileFileNode(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        if code_content := last_action["params"].get("code_content"):
            return code_content
        raise ValueError("Missing code_content parameter")

    def exec(self, code_content: str) -> tuple[str, bool]:
        # Call compile_file utility which returns (content, success)
        errors, success = validate_code(code_content)
        if success:
            return "compilation_success", errors
        return "compilation_error", errors

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[str, bool]) -> str:
        if history := shared.get("history", []):
            history[-1]["result"] = {
                "code_content": prep_res,
                "success": exec_res[0] == "compilation_success",
                "compilation_errors": exec_res[1],
            }
        return exec_res[0]


class FixCodeNode(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        if (code_content := last_action["params"].get("code_content")) and (
            compilation_errors := last_action["result"].get("compilation_errors")
        ):
            return {
                "code_content": code_content,
                "compilation_errors": compilation_errors,
            }
        raise ValueError("Missing code_content or compilation_errors parameter")

    def exec(self, params: dict[str, Any]) -> tuple[str, bool]:
        logger.info(f"FixCodeNode: {params}")
        # Call fix_code utility which returns (content, success)
        PROMPT = f"""
        You are a coding assistant. You have just a python code.
        Fix the code to remove all the errors.
        Return only the fixed code, no other text.
        Code editing rules: {get_rules()}

        Reported errors:
        {params.get("compilation_errors", [])}
        Code:
        {params.get("code_content", "")}
        """
        return call_llm(PROMPT)

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[str, bool]) -> str:
        if history := shared.get("history", []):
            history[-1]["result"] = {
                "code_content": exec_res[0],
            }
        # return exec_res[0]


class QueryClassificationNode(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        if user_query := last_action["params"].get("user_query"):
            return user_query
        raise ValueError("Missing user_query parameter")

    def exec(self, user_query: str) -> str:
        PROMPT = f"""
        You are an expert in decoding user intent. The user gives a prompt or a question.
        Determine whether the user is asking for code generation, or whether they are simply
        asking a question about the code or methodology in the field of spintronics.

        If the user is asking for code generation, return "code_generation".
        If the user is asking a question about the code or methodology in the field of spintronics, return "question".
        Return only the query classification, no other text.

        Example:
        User query: "Create a PIMM simulation with 3 layer stack with params Ms = 1T, 2T, 3T,
                    in plane Ku = 10kJ/m^3, 20kJ/m^3, 30kJ/m^3"
        Classification: "code_generation"

        User query: "What is the meaning of the variable 'Ms' in the code?"
        Classification: "question"

        User query: "What is PIMM simulation?"
        Classification: "question"

        User query: {user_query}
        """
        return call_llm(PROMPT)

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: str) -> str:
        if history := shared.get("history", []):
            history[-1]["result"] = {
                "query_classification": exec_res,
            }
        return exec_res


def main_flow():
    main_agent = MainDecisionAgent()
    read_action = ReadFileAction()
    grep_action = GrepSearchAction()
    list_dir_action = ListDirAction()
    format_response = FormatResponseNode()
    docstring_node = SearchDocstring()
    # query_classification_node = QueryClassificationNode()

    # query_classification_node - "code_generation" >> main_agent
    # query_classification_node - "question" >> qa_agent

    compile_file_node = CompileFileNode()
    fix_code_node = FixCodeNode()
    main_agent - "validate_code" >> compile_file_node
    compile_file_node - "compilation_error" >> fix_code_node
    compile_file_node - "compilation_success" >> main_agent
    fix_code_node >> main_agent

    main_agent - "read_file" >> read_action
    main_agent - "grep_search" >> grep_action
    main_agent - "list_dir" >> list_dir_action
    main_agent - "search_api_docstrings_regex" >> docstring_node
    main_agent - "finish" >> format_response

    # Connect action nodes back to main agent using default action
    read_action >> main_agent
    grep_action >> main_agent
    list_dir_action >> main_agent
    docstring_node >> main_agent

    return Flow(start=main_agent)


if __name__ == "__main__":
    shared = {
        "user_query": "Create sample code using cmtj library in Python for CIMS simulation with 2 "
        "layers where first has Ms=1.2T, Ku = 3.2kJ/m^3 PMA and the second has Ms = 1.6T, Ku = 6.4kJ/m^3",
        "working_dir": "/Users/jm/repos/cmtj-cursor/_cmtj",
        "history": [],
        "response": None,
    }

    flow = main_flow()
    flow.run(shared=shared)
