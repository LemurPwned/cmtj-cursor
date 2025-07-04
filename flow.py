import os
from datetime import datetime
from typing import Any

import yaml  # Add YAML support
from loguru import logger
from pocketflow import BatchNode, Flow, Node

# Import utility functions
from utils.call_llm import call_llm
from utils.compile_ops import validate_code, validate_file
from utils.dir_ops import list_dir
from utils.get_rules import get_rules
from utils.insert_file import insert_file
from utils.read_file import read_file
from utils.replace_file import replace_file
from utils.search_ops import (
    get_api_docstrings,
    grep_search,
    search_api_docstrings_regex,
)

DEFAULT_RETRIES: int = 2


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
        params = action.get("params", {})
        if params:
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
                elif action["tool"] == "edit_file" and success:
                    operations = result.get("operations", 0)
                    history_str += f"- Operations: {operations}\n"

                    # Include the reasoning if available
                    reasoning = result.get("reasoning", "")
                    if reasoning:
                        history_str += f"- Reasoning: {reasoning}\n"
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

Available tools:
1. read_file: Read content from a file
   - Parameters: target_file (path)
   - Example:
     tool: read_file
     reason: I need to read the main.py file to understand its structure
     params:
       target_file: main.py

2. edit_file: Make changes to a file
   - Parameters: target_file (path), instructions, code_edit
   - Code_edit_instructions:
       - The code changes with context, following these rules:
       - Use "// ... existing code ..." to represent unchanged code between edits
       - Include sufficient context around the changes to resolve ambiguity
       - Minimize repeating unchanged code
       - Never omit code without using the "// ... existing code ..." marker
       - No need to specify line numbers - the context helps locate the changes
   - Example:
     tool: edit_file
     reason: I need to add error handling to the file reading function
     params:
       target_file: utils/read_file.py
       instructions: Add try-except block around the file reading operation
       code_edit: |
            // ... existing file reading code ...
            function newEdit() {{
                // new code here
            }}
            // ... existing file reading code ...

3. create_new_file: Create a new file
   - Parameters: target_file (path), content
   - Example:
     tool: create_new_file
     reason: I need to create a new file called utils/read_file.py
     params:
       target_file: utils/read_file.py
       content: |
        # new code here
        import logging
        logger = logging.getLogger(__name__)
        logger.info("New file created")

4. grep_search: Search for patterns in files
   - Parameters: query, case_sensitive (optional), include_pattern (optional), exclude_pattern (optional)
   - Example:
     tool: grep_search
     reason: I need to find all occurrences of 'logger' in Python files
     params:
       query: logger
       include_pattern: "*.py"
       case_sensitive: false

5. list_dir: List contents of a directory
   - Parameters: relative_workspace_path
   - Example:
     tool: list_dir
     reason: I need to see all files in the utils directory
     params:
       relative_workspace_path: utils
   - Result: Returns a tree visualization of the directory structure

6. search_api_docstrings_regex: Search the signature or docstring of a class or function of cmtj library. Can also do free text search.
   - Parameters: query
   - Example:
     tool: search_api_docstrings_regex
     reason: I need to check the signature or docstring of the class called "Junction"
     params:
       query: Junction
   - Result: Returns the signature and the docstring of the class or function

7. finish: End the process and provide final code output
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


#############################################
# Read File Action Node
#############################################
class ReadFileAction(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        file_path = last_action["params"].get("target_file")

        if not file_path:
            raise ValueError("Missing target_file parameter")

        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, file_path) if working_dir else file_path

        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"ReadFileAction: {reason}")

        return full_path

    def exec(self, file_path: str) -> tuple[str, bool]:
        logger.warning(f"Reading file: {file_path}")
        # Call read_file utility which returns a tuple of (content, success)
        return read_file(file_path)

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[str, bool]) -> str:
        # Unpack the tuple returned by read_file()
        content, success = exec_res

        # Update the result in the last history entry
        if history := shared.get("history", []):
            history[-1]["result"] = {"success": success, "content": content}


#############################################
# Grep Search Action Node
#############################################
class GrepSearchAction(Node):
    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        params = last_action["params"]

        if "query" not in params:
            raise ValueError("Missing query parameter")

        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"GrepSearchAction: {reason}")

        # Ensure paths are relative to working directory
        working_dir = shared.get("working_dir", "")

        return {
            "query": params["query"],
            "case_sensitive": params.get("case_sensitive", False),
            "include_pattern": params.get("include_pattern"),
            "exclude_pattern": params.get("exclude_pattern"),
            "working_dir": working_dir,
        }

    def exec(self, params: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
        # Use current directory if not specified
        logger.warning(f"GrepSearchAction: {params}")
        working_dir = params.pop("working_dir", "")

        # Call grep_search utility which returns (success, matches)
        return grep_search(
            query=params["query"],
            case_sensitive=params.get("case_sensitive", False),
            include_pattern=params.get("include_pattern"),
            exclude_pattern=params.get("exclude_pattern"),
            working_dir=working_dir,
        )

    def post(
        self,
        shared: dict[str, Any],
        prep_res: dict[str, Any],
        exec_res: tuple[bool, list[dict[str, Any]]],
    ) -> str:
        matches, success = exec_res

        # Update the result in the last history entry
        if history := shared.get("history", []):
            history[-1]["result"] = {"success": success, "matches": matches}


#############################################
# List Directory Action Node
#############################################
class ListDirAction(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        path = last_action["params"].get("relative_workspace_path", ".")

        # Use the reason for logging instead of explanation
        reason = last_action.get("reason", "No reason provided")
        logger.info(f"ListDirAction: {reason}")

        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        return os.path.join(working_dir, path) if working_dir else path

    def exec(self, path: str) -> tuple[bool, str]:
        # Call list_dir utility which now returns (success, tree_str)
        logger.warning(f"ListDirAction: {path}")
        success, tree_str = list_dir(path)

        return success, tree_str

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[bool, str]) -> str:
        success, tree_str = exec_res

        # Update the result in the last history entry with the new structure
        if history := shared.get("history", []):
            history[-1]["result"] = {"success": success, "tree_visualization": tree_str}


#############################################
# Read Target File Node (Edit Agent)
#############################################
class ReadTargetFileNode(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        file_path = last_action["params"].get("target_file")

        if not file_path:
            raise ValueError("Missing target_file parameter")

        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        return os.path.join(working_dir, file_path) if working_dir else file_path

    def exec(self, file_path: str) -> tuple[str, bool]:
        # Call read_file utility which returns (content, success)
        logger.warning(f"ReadTargetFileNode: {file_path}")
        return read_file(file_path)

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[str, bool]) -> str:
        content, success = exec_res
        logger.info("ReadTargetFileNode: File read completed for editing")

        # Store file content in the history entry
        if history := shared.get("history", []):
            history[-1]["file_content"] = content


#############################################
# Analyze and Plan Changes Node
#############################################
class AnalyzeAndPlanNode(Node):
    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        # Get history
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        file_content = last_action.get("file_content")
        instructions = last_action["params"].get("instructions")
        code_edit = last_action["params"].get("code_edit")

        if not file_content:
            raise ValueError("File content not found")
        if not instructions:
            raise ValueError("Missing instructions parameter")
        if not code_edit:
            raise ValueError("Missing code_edit parameter")

        return {
            "file_content": file_content,
            "instructions": instructions,
            "code_edit": code_edit,
        }

    def exec(self, params: dict[str, Any], retries: int = DEFAULT_RETRIES) -> list[dict[str, Any]]:
        logger.warning(f"AnalyzeAndPlanNode: {params}")
        file_content = params["file_content"]
        instructions = params["instructions"]
        code_edit = params["code_edit"]

        # File content as lines
        file_lines = file_content.split("\n")
        total_lines = len(file_lines)

        # Generate a prompt for the LLM to analyze the edit using YAML instead of JSON
        prompt = f"""
As a code editing assistant, I need to convert the following code edit instruction
and code edit pattern into specific edit operations (start_line, end_line, replacement).

FILE CONTENT:
{file_content}

EDIT INSTRUCTIONS:
{instructions}

CODE EDIT PATTERN (markers like "// ... existing code ..." indicate unchanged code):
{code_edit}

Analyze the file content and the edit pattern to determine exactly where changes should be made.
Be very careful with start and end lines. They are 1-indexed and inclusive. These will be REPLACED, not APPENDED!
If you want APPEND, just copy that line as the first line of the replacement.
Return a YAML object with your reasoning and an array of edit operations:

```yaml
reasoning: |
  First explain your thinking process about how you're interpreting the edit pattern.
  Explain how you identified where the edits should be made in the original file.
  Describe any assumptions or decisions you made when determining the edit locations.
  You need to be very precise with the start and end lines! Reason why not 1 line before or after the start and end lines.

operations:
  - start_line: 10
    end_line: 15
    replacement: |
      def process_file(filename):
          # New implementation with better error handling
          try:
              with open(filename, 'r') as f:
                  return f.read()
          except FileNotFoundError:
              return None

  - start_line: 25
    end_line: 25
    replacement: |
      logger.info("File processing completed")
```

For lines that include "// ... existing code ...", do not include them in the replacement.
Instead, identify the exact lines they represent in the original file and set the line
numbers accordingly. Start_line and end_line are 1-indexed.

If the instruction indicates content should be appended to the file, set both start_line and end_line
to the maximum line number + 1, which will add the content at the end of the file.
"""  # noqa: E501

        # Call LLM to analyze
        response = call_llm(prompt, use_cache=retries == DEFAULT_RETRIES)

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

        if yaml_content:
            decision = yaml.safe_load(yaml_content)

            # Validate the required fields
            assert "reasoning" in decision, "Reasoning is missing"
            assert "operations" in decision, "Operations are missing"

            # Ensure operations is a list
            if not isinstance(decision["operations"], list):
                raise ValueError("Operations are not a list")

            # Validate operations
            for op in decision["operations"]:
                assert "start_line" in op, "start_line is missing"
                assert "end_line" in op, "end_line is missing"
                assert "replacement" in op, "replacement is missing"
                assert 1 <= op["start_line"] <= total_lines, f"start_line out of range: {op['start_line']}"
                assert 1 <= op["end_line"] <= total_lines, f"end_line out of range: {op['end_line']}"
                assert (
                    op["start_line"] <= op["end_line"]
                ), f"start_line > end_line: {op['start_line']} > {op['end_line']}"

            return decision
        if retries > 0:
            logger.warning(f"AnalyzeAndPlanNode: Retrying (attempt {2 - retries})")
            return self.exec(params, retries - 1)
        raise ValueError("No YAML object found in response")

    def post(self, shared: dict[str, Any], prep_res: dict[str, Any], exec_res: dict[str, Any]) -> str:
        # Store reasoning and edit operations in shared
        shared["edit_reasoning"] = exec_res.get("reasoning", "")
        shared["edit_operations"] = exec_res.get("operations", [])


#############################################
# Apply Changes Batch Node
#############################################
class ApplyChangesNode(BatchNode):
    def prep(self, shared: dict[str, Any]) -> list[dict[str, Any]]:
        # Get edit operations
        edit_operations = shared.get("edit_operations", [])
        if not edit_operations:
            logger.warning("No edit operations found")
            return []

        # Sort edit operations in descending order by start_line
        # This ensures that line numbers remain valid as we edit from bottom to top
        sorted_ops = sorted(edit_operations, key=lambda op: op["start_line"], reverse=True)

        # Get target file from history
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        target_file = last_action["params"].get("target_file")

        if not target_file:
            raise ValueError("Missing target_file parameter")

        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        full_path = os.path.join(working_dir, target_file) if working_dir else target_file

        # Attach file path to each operation
        for op in sorted_ops:
            op["target_file"] = full_path

        return sorted_ops

    def exec(self, op: dict[str, Any]) -> tuple[bool, str]:
        logger.warning(f"ApplyChangesNode: {op}")
        # Call replace_file utility which returns (success, message)
        return replace_file(
            target_file=op["target_file"],
            start_line=op["start_line"],
            end_line=op["end_line"],
            content=op["replacement"],
        )

    def post(
        self,
        shared: dict[str, Any],
        prep_res: list[dict[str, Any]],
        exec_res_list: list[tuple[bool, str]],
    ) -> str:
        # Check if all operations were successful
        all_successful = all(success for success, _ in exec_res_list)
        # validate the file
        errors = []
        for op in prep_res:
            if error := validate_file(op["target_file"]):
                errors.append(error)
                logger.warning(f"ApplyChangesNode: {error}")
                all_successful = False

        # Format results for history
        result_details = [{"success": success, "message": message} for success, message in exec_res_list]
        if errors:
            result_details.append({"success": False, "message": errors})

        # Update edit result in history
        if history := shared.get("history", []):
            history[-1]["result"] = {
                "success": all_successful,
                "operations": len(exec_res_list),
                "details": result_details,
                "reasoning": shared.get("edit_reasoning", ""),
            }

        # Clear edit operations and reasoning after processing
        shared.pop("edit_operations", None)
        shared.pop("edit_reasoning", None)


#############################################
# Format Response Node
#############################################
class FormatResponseNode(Node):
    def prep(self, shared: dict[str, Any]) -> list[dict[str, Any]]:
        # Get history
        if history := shared.get("history", []):
            return history
        raise ValueError("No history found")

    def exec(self, history: list[dict[str, Any]]) -> str:
        # If no history, return a generic message
        logger.warning(f"FormatResponseNode: {history}")

        # Generate a summary of actions for the LLM using the utility function
        actions_summary = format_history_summary(history)
        final_version = history[-1].get("params", {}).get("final_version", "")
        # Prompt for the LLM to generate the final response
        prompt = f"""
You are a coding assistant. You have just performed a series of actions based on the
user's request. Summarize what you did in a clear, helpful response.

Here are the actions you performed:
{actions_summary}

Generate a comprehensive yet concise response that explains:
1. What actions were taken
2. What was found or modified
3. Any next steps the user might want to take

IMPORTANT:
- Focus on the outcomes and results, not the specific tools used
- Write as if you are directly speaking to the user
- When providing code examples or structured information, use YAML format enclosed in triple backticks
"""

        # Call LLM to generate response
        return {
            "response": call_llm(prompt),
            "final_version": final_version,
        }

    def post(
        self,
        shared: dict[str, Any],
        prep_res: list[dict[str, Any]],
        exec_res: dict[str, Any],
    ) -> str:
        # Store response in shared
        shared["response"] = exec_res["response"]
        if final_version := exec_res.get("final_version", ""):
            if "```python" not in final_version:
                final_version = f"```python\n{final_version}\n```"
            shared["response"] += f"\n\n{final_version}"
        resp = exec_res["response"]
        logger.info(f"###### Final Response Generated ######\n{resp}\n###### End of Response ######")

        return "done"


class CreateNewFileNode(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        file_path = last_action["params"].get("target_file")
        content = last_action["params"].get("content")
        if not file_path:
            raise ValueError("Missing target_file parameter")
        if not content:
            raise ValueError("Missing content parameter")

        # Ensure path is relative to working directory
        working_dir = shared.get("working_dir", "")
        return {
            "file_path": (os.path.join(working_dir, file_path) if working_dir else file_path),
            "content": content,
        }

    def exec(self, params: dict[str, Any]) -> tuple[str, bool]:
        # Call create_new_file utility which returns (success, message)
        logger.warning(f"CreateNewFileNode: {params}")
        return insert_file(params["file_path"], params["content"])

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[str, bool]) -> str:
        # Update the result in the last history entry
        error, success = exec_res
        error = "" if success else error
        if success:
            error = validate_file(prep_res["file_path"])
        if history := shared.get("history", []):
            history[-1]["result"] = {"success": success, "error": error}


class SalientFileAgent(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]
        if not (file_path := last_action["params"].get("target_file")):
            raise ValueError("Missing target_file parameter")

        return file_path

    def exec(self, file_path: str) -> tuple[str, bool]:
        # Call read_file utility which returns (con tent, success)
        content, success = read_file(file_path)
        if not success:
            return "not relevant", False

        prompt = f"""
        You are a coding assistant. You have just a grep search for a string in a file.
        Determine if the file content is relevant to the user's request.

        If file is not relevant, return "not relevant".
        If file is relevant, return the most salient parts of the file contents.

        File content:
        {content}
        """
        response = call_llm(prompt)
        logger.warning(f"SalientFileNode: {file_path}")
        return response

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: tuple[str, bool]) -> str:
        return exec_res[0]


class SummaryNode(Node):
    def prep(self, shared: dict[str, Any]) -> str:
        # Get parameters from the last history entry
        history = shared.get("history", [])
        if not history:
            raise ValueError("No history found")

        last_action = history[-1]

        if file_path := last_action["params"].get("target_file"):
            return file_path
        raise ValueError("Missing target_file parameter")

    def exec(self, file_path: str) -> str:
        # Call read_file utility which returns (content, success)
        content, success = read_file(file_path)
        return content if success else "not relevant"


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
                "code_content": prep_res,
                "success": exec_res[0] == "compilation_success",
                "compilation_errors": exec_res[1],
            }
        return exec_res[0]


#############################################
# Edit Agent Flow
#############################################
def create_edit_agent() -> Flow:
    # Create nodes
    read_target = ReadTargetFileNode()
    analyze_plan = AnalyzeAndPlanNode()
    apply_changes = ApplyChangesNode()

    # Connect nodes using default action (no named actions)
    read_target >> analyze_plan
    analyze_plan >> apply_changes

    # Create flow
    return Flow(start=read_target)


def create_search_agent() -> Flow:
    # Create nodes
    # do a search for string
    grep_action = GrepSearchAction()
    read_action = ReadFileAction()
    saliency_agent = SalientFileAgent()
    summary_agent = SummaryNode()
    grep_action - "read_file" >> read_action
    read_action - "is_file_relevant" >> saliency_agent
    saliency_agent - "summary" >> summary_agent

    return Flow(start=grep_action)


#############################################
# Main Flow
#############################################
def create_main_flow() -> Flow:
    # Create nodes
    create_new_file = CreateNewFileNode()
    main_agent = MainDecisionAgent()
    read_action = ReadFileAction()
    grep_action = GrepSearchAction()
    list_dir_action = ListDirAction()
    edit_agent = create_edit_agent()
    format_response = FormatResponseNode()
    docstring_node = SearchDocstring()

    compile_file_node = CompileFileNode()
    fix_code_node = FixCodeNode()
    main_agent - "validate_code" >> compile_file_node
    compile_file_node - "compilation_error" >> fix_code_node
    compile_file_node - "compilation_success" >> main_agent
    fix_code_node >> compile_file_node

    main_agent - "create_new_file" >> create_new_file
    main_agent - "read_file" >> read_action
    main_agent - "grep_search" >> grep_action
    main_agent - "list_dir" >> list_dir_action
    main_agent - "edit_file" >> edit_agent
    main_agent - "search_api_docstrings_regex" >> docstring_node
    main_agent - "finish" >> format_response

    # Connect action nodes back to main agent using default action
    read_action >> main_agent
    grep_action >> main_agent
    list_dir_action >> main_agent
    edit_agent >> main_agent
    create_new_file >> main_agent
    docstring_node >> main_agent
    # Create flow
    return Flow(start=main_agent)


def build_mermaid(start):
    ids, visited, lines = {}, set(), ["graph LR"]
    ctr = 1

    def get_id(n):
        nonlocal ctr
        return ids[n] if n in ids else (ids.setdefault(n, f"N{ctr}"), (ctr := ctr + 1))[0]

    def link(a, b):
        lines.append(f"    {a} --> {b}")

    def walk(node, parent=None):
        if node in visited:
            return parent and link(parent, get_id(node))
        visited.add(node)
        if isinstance(node, Flow):
            node.start_node and parent and link(parent, get_id(node.start_node))
            lines.append(f"\n    subgraph sub_flow_{get_id(node)}[{type(node).__name__}]")
            node.start_node and walk(node.start_node)
            for nxt in node.successors.values():
                node.start_node and walk(nxt, get_id(node.start_node)) or (
                    parent and link(parent, get_id(nxt))
                ) or walk(nxt)
            lines.append("    end\n")
        else:
            lines.append(f"    {(nid := get_id(node))}['{type(node).__name__}']")
            parent and link(parent, nid)
            [walk(nxt, nid) for nxt in node.successors.values()]

    walk(start)
    return "\n".join(lines)


# Create the main flow
coding_agent_flow = create_main_flow()

flow = build_mermaid(coding_agent_flow)
with open("flow.md", "w") as f:
    f.write(f"```mermaid\n{flow}\n```")
