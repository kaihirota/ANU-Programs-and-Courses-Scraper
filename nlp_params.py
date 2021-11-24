TARGET = {"CLASS", "PROGRAM"}

patterns = [
    {
        "label": "CLASS",
        "pattern": [{"TEXT": {"REGEX": "[A-Z]{4}[0-9]{4}"}}],
        "id": "class"
    },
    {
        "label": "PROGRAM",
        "pattern": [
            {"LOWER": {"IN": ["master", "masters"]}},
            {"LOWER": "of"},
            {"IS_TITLE": True},  # Computing, Engineering,
            {"OP": "*", "IS_TITLE": True},
            {"OP": "*", "TEXT": {"IN": ["in", "and", "of"]}},
            {"OP": "*", "IS_TITLE": True},
            {"OP": "?", "TEXT": "("},
            {"OP": "?", "LOWER": {"IN": ["research", "advanced"]}},
            {"OP": "?", "TEXT": ")"}
        ],
        "id": "program"
    },
    {
        "label": "PROGRAM",
        "pattern": [
            {"LOWER": {"IN": ["master", "masters"]}},
            {"LOWER": "of"},
            {"IS_TITLE": True},  # Computing, Engineering,
            {"OP": "*", "TEXT": {"IN": ["in", "and", "of"]}},
            {"OP": "*", "IS_TITLE": True},
            {"OP": "?", "TEXT": "("},
            {"OP": "?", "LOWER": {"IN": ["research", "advanced"]}},
            {"OP": "?", "TEXT": ")"}
        ],
        "id": "program"
    }
]