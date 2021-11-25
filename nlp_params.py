from collections import defaultdict

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
            {"OP": "+", "IS_TITLE": True},
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
            {"OP": "+", "IS_TITLE": True},
            {"OP": "?", "TEXT": {"IN": ["in", "and", "of"]}},
            {"OP": "+", "IS_TITLE": True}
        ],
        "id": "program"
    }
]

CONDITION_MAPPING = defaultdict(lambda : "Unknown")
CONDITION_MAPPING["incompatible"] = "incompatible"
CONDITION_MAPPING["completed"] = "completed"
CONDITION_MAPPING["studying"] = "studying"
CONDITION_MAPPING["enrolled"] = "enrolled"
CONDITION_MAPPING["enrol"] = "permission"
CONDITION_MAPPING["request"] = "permission"