import ast
import glob
import pathlib
import warnings
from typing import Any


def parse_with_docstrings(file_path: str, ignore_underscore_functions: bool = True) -> dict[str, Any]:
    content = pathlib.Path(file_path).read_text()
    # Suppress syntax warnings when parsing .pyi files with LaTeX notation
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=SyntaxWarning)
        tree = ast.parse(content, filename=file_path)

    type_defs = {}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_name = node.name
            args = {}
            for arg in node.args.args:
                if arg.annotation:
                    args[arg.arg] = ast.unparse(arg.annotation)
            returns = ast.unparse(node.returns) if node.returns else None
            docstring = ast.get_docstring(node)
            type_defs[func_name] = {
                "args": args,
                "returns": returns,
                "docstring": docstring,
            }

        elif isinstance(node, ast.AnnAssign):
            var_name = node.target.id
            var_type = ast.unparse(node.annotation)
            type_defs[var_name] = {"type": var_type, "docstring": None}

        elif isinstance(node, ast.ClassDef):
            class_name = node.name
            class_defs = {
                "methods": {},
                "attributes": {},
                "docstring": ast.get_docstring(node),
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_name = item.name
                    if ignore_underscore_functions and method_name.startswith("_") and method_name != "__init__":
                        continue
                    method_args = {}
                    for arg in item.args.args:
                        if arg.annotation:
                            method_args[arg.arg] = ast.unparse(arg.annotation)
                    returns = ast.unparse(item.returns) if item.returns else None
                    method_docstring = ast.get_docstring(item)
                    class_defs["methods"][method_name] = {
                        "args": method_args,
                        "returns": returns,
                        "docstring": method_docstring,
                    }
                elif isinstance(item, ast.AnnAssign):
                    attr_name = item.target.id
                    attr_type = ast.unparse(item.annotation)
                    class_defs["attributes"][attr_name] = {
                        "type": attr_type,
                        "docstring": None,
                    }
            type_defs[class_name] = class_defs
    new_type_info = {}
    for k, f in type_defs.items():
        if methods := f.get("methods"):
            for m, d in methods.items():
                new_type_info[f"{k}.{m}"] = d

    return type_defs | new_type_info


def build_api_docs(folder: str) -> dict[str, Any]:
    """
    Build API docs for a given folder.
    """
    type_defs = {}
    for file in glob.glob(f"{folder}/**/*.py", recursive=True):
        file_defs = parse_with_docstrings(file)
        type_defs = type_defs | file_defs
    for file in glob.glob(f"{folder}/**/*.pyi", recursive=True):
        file_defs = parse_with_docstrings(file)
        type_defs = type_defs | file_defs
    return type_defs
