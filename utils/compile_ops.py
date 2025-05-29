import pathlib
import traceback

from loguru import logger


def validate_code(code: str) -> str:
    """Validate if the code looks correct (syntax check only)"""
    try:
        # Just compile to check for syntax errors
        compile(code, "<string>", "exec")
        exec(code, {})
        return "Code syntax looks valid.", True
    except SyntaxError as e:
        # Get precise syntax error details
        tb = f"Line {e.lineno}, Column {e.offset}: {e.msg}"
        logger.error(f"Code has syntax errors: {tb}")
        return f"Code has syntax errors: {tb}", False
    except Exception as e:
        # Get full traceback for runtime errors
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
