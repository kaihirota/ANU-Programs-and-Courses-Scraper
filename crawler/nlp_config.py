from collections import defaultdict
import json
import os

PATTERNS = [
    {
        "label": "CLASS",
        "pattern": [{"TEXT": {"REGEX": "[A-Z]{4}[0-9]{4}"}}],
        "id": "class"
    },
    {
        "label": "PROGRAM",
        "pattern": [
            {"OP": "?", "LOWER": "executive"},
            {"LOWER": {"IN": ["master", "masters", "doctor", "bachelor"]}},
            {"LOWER": "of"},
            {"OP": "?", "TEXT": {"REGEX": "[A-Z][a-z]+|and|of|in"}},
            {"IS_TITLE": True}
        ],
        "id": "program"
    },
    {
        "label": "PROGRAM",
        "pattern": [
            {"OP": "?", "LOWER": "executive"},
            {"LOWER": {"IN": ["master", "masters", "doctor", "bachelor"]}},
            {"LOWER": "of"},
            {"OP": "+", "TEXT": {"REGEX": "[A-Z][a-z]+|and|of|in"}},
            {"TEXT": "("},
            {"OP": "?", "TEXT": {"REGEX": "[A-Z][a-z]+|and|of|in"}},
            {"IS_TITLE": True},
            {"TEXT": ")"}
        ],
        "id": "program"
    },
    {
        "label": "PROGRAM",
        "pattern": [
            {"LOWER": "graduate"},
            {"LOWER": {"IN": ["certificate", "diploma"]}},
            {"LOWER": "of"},
            {"OP": "?", "TEXT": {"REGEX": "[A-Z][a-z]+|and|of|in"}},
            {"IS_TITLE": True}
        ],
        "id": "program"
    },
    {
        "label": "PROGRAM",
        "pattern": [
            {"LOWER": "graduate"},
            {"LOWER": {"IN": ["certificate", "diploma"]}},
            {"LOWER": "of"},
            {"OP": "+", "TEXT": {"REGEX": "[A-Z][a-z]+|and|of|in"}},
            {"TEXT": "("},
            {"OP": "?", "TEXT": {"REGEX": "[A-Z][a-z]+|and|of|in"}},
            {"IS_TITLE": True},
            {"TEXT": ")"}
        ],
        "id": "program"
    }
]

TARGET = {"CLASS", "PROGRAM"}

CONDITION_MAPPING = defaultdict(lambda: "Unknown")
CONDITION_MAPPING["incompatible"] = "incompatible"
CONDITION_MAPPING["completed"] = "completed"
CONDITION_MAPPING["studying"] = "studying"
CONDITION_MAPPING["enrolled"] = "enrolled"
CONDITION_MAPPING["request"] = "permission"
CONDITION_MAPPING["permission"] = "permission"

SPEC_MAPPER = {
    'major': 'MAJ',
    'minor': 'MIN',
    'specialisation': 'SPC',
    'specialization': 'SPC',
    'maj': 'MAJ',
    'min': 'MIN',
    'spc': 'SPC'
}

ALL_SPECIALISATIONS = {}
specialisations_dir = 'data/from_api/specialisations'
if os.path.exists(specialisations_dir):
    for file in os.listdir(specialisations_dir):
        _, fn = os.path.split(file)
        filename, _ = os.path.splitext(fn)

        with open(os.path.join(specialisations_dir, file)) as f:
            data = json.load(f)
            for item in data['Items']:
                ALL_SPECIALISATIONS[item['SubPlanCode']] = item


ALL_PROGRAMS = {}
for file in ['data/from_api/programs_undergrad.json', 'data/from_api/programs_postgrad.json']:
    if os.path.exists(file):
        with open(file) as f:
            data = json.load(f)
            for item in data['Items']:
                ALL_PROGRAMS[item['ProgramName']] = item['AcademicPlanCode']
