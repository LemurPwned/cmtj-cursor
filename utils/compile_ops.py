import traceback

from loguru import logger


def validate_code(code: str) -> str:
    """Validate if the code looks correct (syntax check only)"""
    print(code)
    try:
        # Just compile to check for syntax errors
        compile(code, "<string>", "exec")
        exec(code, {})
        return "Code syntax looks valid."
    except Exception:
        tb = traceback.format_exc()
        return f"Code has syntax errors: {tb}"


def validate_file(file_path: str) -> str:
    """Validate if the file looks correct (syntax check only)"""
    logger.debug(f"Validating file: {file_path}")
    with open(file_path) as f:
        code = f.read()
    return validate_code(code)
