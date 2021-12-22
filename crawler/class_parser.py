from collections import Counter
import json
from typing import Any, Dict, List

from nlp_config import CONDITION_MAPPING, ALL_PROGRAMS

Expression = Dict[str, Any]

def split_expression(sent, token, start: int, end: int) -> Expression:
    if end != token.i:
        return {
            'description': str(sent[start:end]),
            'operator': {
                token.text.upper(): [
                    parse_requisite_from_sent(sent, start, token.i),
                    parse_requisite_from_sent(sent, token.i + 1, end)
                ]
            }
        }


def parse_requisite_from_sent(sent, start: int = 0, end=None) -> Dict:
    counter = Counter()

    raw_txt = sent[start:end].text
    lemma_txt = " ".join([token.lemma_ for token in sent[start:end]])
    negation = "not" in raw_txt
    verb = None
    classes = []
    programs = []
    semicolon = False

    # prioritize semicolons first
    # find and/or following a semicolon where there are named entity and verb on left and right sides
    for idx in range(start, end):
        token = sent[idx]

        if token.ent_type_ == "CLASS":
            classes += token.text,
        if token.is_alpha and token.ent_type_ == "PROGRAM":
            programs += token.text,
        if token.pos_ == 'VERB':
            verb = token
        if token.text == ';':
            semicolon = True

        if token.lower_ in {"and", "or"} and semicolon and verb:
            # different pair of named entity and verb on left and right of the sentence
            right_ent = sent[token.i + 1:].ents
            right_verb = [t for t in sent[token.i + 1:] if t.pos_ == 'VERB']
            if len(programs) + len(classes) > 0 and right_ent and right_verb:
                return split_expression(sent, token, start, end)

    verb = None
    classes = []
    programs = []

    for idx in range(start, end):
        token = sent[idx]

        if token.ent_type_ == "CLASS":
            classes += token.text,
        elif token.ent_type_ == "PROGRAM":
            programs += token.text,
        elif token.pos_ == 'VERB':
            verb = token
        # translate into boolean expressions
        elif token.lower_ in {"and", "or"}:
            counter[token.lower_] += 1

            try:
                # preceded or followed by a punctuation, unless that punctuation is part of a named entity
                left_token = sent[token.i - 1]
                right_token = sent[token.i + 1]
                if (left_token.is_punct and not left_token.ent_type_) or (
                        right_token.is_punct and not right_token.ent_type_):
                    return split_expression(sent, token, start, end)

                # different pair of named entity and verb on left and right of the sentence
                right_ent = sent[token.i + 1:].ents
                right_verb = [t for t in sent[token.i + 1:] if t.pos_ == 'VERB']
                if verb and (len(programs) + len(classes) > 0) and right_ent and right_verb:
                    return split_expression(sent, token, start, end)

                # if no named entity to the left, mirror the verb
                # i.e. "you must have completed or be currently enrolled in COMP6710"
                # will be OR of two expressions on COMP6710, completed OR enrolled
                if verb and (len(programs) + len(classes) == 0):
                    right_counter = Counter()
                    for t in sent[token.i + 1:]:
                        if t.lower_ in {"and", "or"}:
                            right_counter[t.lower_] += 1
                    try:
                        right_operator, _ = right_counter.most_common(1)[0]
                    except IndexError:
                        right_operator = ""
                    return {
                        'description': str(sent[start:end]),
                        'operator': {
                            token.text.upper(): [
                                {
                                    "condition": verb.text,
                                    "operator": right_operator,
                                    # "negation": negation,
                                    "programs": [ent.text for ent in sent[token.i + 1:].ents if
                                                 ent.label_ == 'PROGRAM'],
                                    "classes": [ent.text for ent in sent[token.i + 1:].ents if ent.label_ == 'CLASS'],
                                    "description": raw_txt
                                },
                                parse_requisite_from_sent(sent, token.i + 1, end)
                            ]
                        }
                    }
            except IndexError:
                pass

    try:
        operator, _ = counter.most_common(1)[0]
    except IndexError:
        operator = ""

    if 'incompatible' in lemma_txt:
        return {
            "condition": "incompatible",
            # "negation": negation,
            "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
            "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
            "description": raw_txt
        }
    elif verb:
        return {
            "condition": CONDITION_MAPPING[verb.text],
            "operator": operator,
            "negation": negation,
            "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
            "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
            "description": raw_txt
        }
    else:
        for i in range(start, -1, -1):
            if sent[i].pos_ == 'VERB':
                return {
                    "condition": CONDITION_MAPPING[sent[i].text],
                    "operator": operator,
                    "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
                    "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
                    "description": raw_txt
                }
    return {
        "condition": "Unknown",
        "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
        "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
        "description": raw_txt
    }


def clean_class_doc(doc: Dict) -> Dict:
    # convert program names to program id
    if not doc:
        return None

    if 'operator' in doc and type(doc['operator']) == dict:
        for op in doc['operator'].keys():
            for i in range(len(doc['operator'][op])):
                doc['operator'][op][i] = clean_class_doc(doc['operator'][op][i])
    elif 'programs' in doc and doc['programs']:
        for i in range(len(doc['programs'])):
            name_str = doc['programs'][i]
            name_str = name_str.rstrip('(').strip()

            if name_str in ALL_PROGRAMS:
                name_str = ALL_PROGRAMS[name_str]

            doc['programs'][i] = name_str
    return doc


def parse_requisites(doc) -> List[Dict]:
    reqs = []
    for sent in doc.sents:
        reqs += parse_requisite_from_sent(sent, 0, len(sent)),

    for i in range(len(reqs)):
        reqs[i] = clean_class_doc(reqs[i])
    return reqs
