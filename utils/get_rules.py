RULES_FILE = "rules.txt"


def get_rules() -> str:
    """
    Get the rules from the rules file.
    """
    with open(RULES_FILE, "r") as file:
        return file.read()
