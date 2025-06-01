RULES_FILE = "./knowledge_base/rules.txt"


def get_rules() -> str:
    """
    Get the rules from the rules file.
    """
    with open(RULES_FILE) as file:
        return file.read()
