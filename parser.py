from collections import Counter

import spacy

from nlp_params import patterns

nlp = spacy.load("en_core_web_sm")
ruler = nlp.add_pipe("entity_ruler", config={"validate": True}, before="ner")
ruler.add_patterns(patterns)

def parse_requisite_from_sent(sent, start: int = 0, end=None):
    classes = []
    programs = []
    counter = Counter()

    txt_substr = sent[start:end].text
    txt_lemma = " ".join([token.lemma_ for token in sent[start:end]])
    negation = "not" in txt_substr
    has_verb = False
    verb = None

    for idx in range(start, end):
        token = sent[idx]

        if token.ent_type_ == "CLASS":
            classes += token.text,
        elif token.ent_type_ == "PROGRAM":
            programs += token.text,
        elif token.pos_ == 'VERB':
            has_verb = True
            verb = token

        # look for and / or compound boolean logic (i.e. not interested in "COMPxxxx or COMPyyyy")
        # intersted in "completed COMPxxxx; and be enrolled in XXXX"
        elif token.lower_ in {"and", "or"}:
            counter[token.lower_] += 1

            try:
                left_token = sent[token.i-1]
                right_token = sent[token.i+1]

                if left_token.is_punct or right_token.is_punct:
                    return {
                        'description': str(token.sent[start:end]),
                        'operator': {
                            token.text.upper(): [
                                parse_requisite_from_sent(sent, start, token.i),
                                parse_requisite_from_sent(sent, token.i + 1, end)
                            ]
                        }
                    }
            except IndexError:
                pass

    most_common = counter.most_common(1)
    if len(most_common) > 0:
        operator, _ = most_common[0]
    else:
        operator = ""

    # detect co-requisite
    simple_words = [token.lemma_ for token in sent[start:end] if token.pos_ != 'ADV']
    if len(simple_words) >= 3:
        for i in range(len(simple_words)-3):
            s = set(simple_words[i:i+3])
            if 'completed' in s and ('enrolled' in s or 'studying' in s):
                return {
                    "condition": "co-requisite",
                    # "negation": negation,
                    "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
                    "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
                    "description": txt_substr
                }

    if 'incompatible' in txt_lemma:
        return {
            "condition": "incompatible",
            # "negation": negation,
            "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
            "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
            "description": txt_substr
        }
    elif has_verb:
        return {
            "condition": verb.text,
            "operator": operator,
            "negation": negation,
            "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
            "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
            "description": txt_substr
        }
    else:
        for i in range(start, -1, -1):
            if sent[i].pos_ == 'VERB':
                return {
                    "condition": sent[i].text,
                    "operator": operator,
                    "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
                    "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
                    "description": txt_substr
                }
        return {
            "condition": "Unknown",
            "programs": [ent.text for ent in sent[start:end].ents if ent.label_ == 'PROGRAM'],
            "classes": [ent.text for ent in sent[start:end].ents if ent.label_ == 'CLASS'],
            "description": txt_substr
        }


def parse_requisites(doc):
    reqs = []
    for sent in doc.sents:
        reqs += parse_requisite_from_sent(sent, 0, len(sent)),
    return reqs
