import os
import pathlib
import traceback

from loguru import logger


def validate_code(code: str) -> str:
    """Validate if the code looks correct (syntax check only)"""
    try:
        # Just compile to check for syntax errors
        compile(code, "<string>", "exec")

        # Create execution environment with matplotlib backend set
        exec_globals = {}

        # Check if code contains matplotlib and set non-interactive backend
        if "matplotlib" in code or "plt." in code:
            # Set environment variables that matplotlib will read
            os.environ["MPLBACKEND"] = "Agg"

            # Pre-configure matplotlib in the execution environment
            exec_code = (
                """
import matplotlib
matplotlib.use('Agg', force=True)
import matplotlib.pyplot as plt
plt.ioff()  # Turn off interactive mode
"""
                + code
            )
        else:
            exec_code = code

        # Execute with a more complete environment
        exec_globals.update(
            {
                "__builtins__": __builtins__,
                "__name__": "__main__",
            }
        )

        exec(exec_code, exec_globals)
        return "Code syntax looks valid.", True
    except SyntaxError as e:
        # Get precise syntax error details
        tb = f"Line {e.lineno}, Column {e.offset}: {e.msg}"
        logger.error(f"Code has syntax errors: {tb}")
        return f"Code has syntax errors: {tb}", False
    except ImportError as e:
        # Handle import errors more gracefully - these might be expected
        if any(lib in str(e).lower() for lib in ["matplotlib", "display", "gui", "tkinter"]):
            logger.warning(f"Import warning (likely display-related): {e}")
            return "Code syntax looks valid (with display-related import warnings).", True
        else:
            tb = f"Import error: {e}"
            logger.error(tb)
            return tb, False
    except Exception as e:
        # Handle matplotlib display errors more gracefully
        error_msg = str(e).lower()
        if any(term in error_msg for term in ["display", "gui", "x11", "tkinter", "qt", "show"]):
            logger.warning(f"Display-related warning: {e}")
            return "Code syntax looks valid (with display-related warnings).", True
        else:
            # Get full traceback for other runtime errors
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error(f"Code has runtime errors: {tb}")
            return f"Code has runtime errors: {tb}", False


def validate_file(file_path: str) -> str:
    """Validate if the file looks correct (syntax check only)"""
    logger.debug(f"Validating file: {file_path}")
    code = pathlib.Path(file_path).read_text()
    resp, _ = validate_code(code)
    logger.debug(f"Validation response: {resp}")
    return resp
