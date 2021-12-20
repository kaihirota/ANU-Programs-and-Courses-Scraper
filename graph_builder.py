import hashlib
import json
import os
from collections import defaultdict
from pprint import pprint
from py2neo import Graph, Node, Relationship, Subgraph
from typing import Dict, List

ALL_SPECIALISATIONS = {}
specialisations_dir = 'data/from_api/specialisations'

for file in os.listdir(specialisations_dir):
    _, fn = os.path.split(file)
    filename, _ = os.path.splitext(fn)

    with open(os.path.join(specialisations_dir, file)) as f:
        data = json.load(f)
        for item in data['Items']:
            ALL_SPECIALISATIONS[item['SubPlanCode']] = item

CLASSES = defaultdict(lambda: Node("class"))
PROGRAMS = defaultdict(lambda: Node("program"))
SPECIAL = defaultdict(lambda: Node("specialisation"))

SPEC_MAPPER = {
    'major': 'MAJ',
    'minor': 'MIN',
    'specialisation': 'SPC',
    'specialization': 'SPC',
    'maj': 'MAJ',
    'min': 'MIN',
    'spc': 'SPC'
}


class Prerequisite(Relationship):
    name = 'Prerequisite'


class Incompatible(Relationship):
    name = 'Incompatible'


class Enrolled(Relationship):
    name = 'Enrolled'


class Unknown(Relationship):
    name = 'Unknown'


class Requirement(Relationship):
    name = 'Requirement'


CONDITION_MAPPER = {
    'completed': Prerequisite,
    'incompatible': Incompatible,
    'studying': Enrolled,
    'enrolled': Enrolled,
    'Unknown': Unknown,
    'permission': Unknown,
    'obtained': Unknown
}


def update_node(node: Node, doc: Dict) -> Node:
    for key in doc.keys():
        if doc[key]:
            if type(doc[key]) != list and type(doc[key]) != dict:
                node[key] = doc[key]
    return node


def upsert_node(node: Node, doc: Dict, G: Graph, label: str, key: str) -> Node:
    node = update_node(node, doc)
    try:
        G.merge(node, label, key)
    except:
        if 'id' in doc:
            ret = G.nodes.match(label, id=doc['id'])
            if len(ret) == 0:
                G.create(ret)
        else:
            G.create(node)
    return node


def create_node_if_not_exists(cache: defaultdict, doc: Dict, G: Graph, key: str, label: str) -> Node:
    dest_node = cache[key]
    dest_node = upsert_node(dest_node, doc, G, label, 'id')
    return dest_node


def create_edge(edge: Relationship, doc: Dict, G: Graph, label: str = None) -> Relationship:
    """
    program -- Req -> req
    req -- Req -> req
    req -- Req -> spec
    spec -- Req -> req
    req -- Req -> class
    class -> class
    """
    if 'condition' in doc:
        edge['condition'] = doc['condition']
    if 'description' in doc:
        edge['description'] = doc['description']
    if 'negation' in doc:
        edge['negation'] = doc['negation']

    if label == 'requirement':
        labels = list(edge.end_node.labels)
        label = labels[0]

    if not label:
        labels = list(edge.start_node.labels)
        label = labels[0]

    G.merge(edge, label, 'id')
    return edge


def create_nodes_and_edges_if_class_requisite(
        doc: Dict, parent_node: Node, G: Graph, op: str = 'and'
) -> List[Relationship]:
    items = []

    if doc:
        if 'operator' in doc and type(doc['operator']) == dict:
            for operator in doc['operator'].keys():
                for requirement in doc['operator'][operator]:
                    items.extend(create_nodes_and_edges_if_class_requisite(requirement, parent_node, G, operator))
        elif 'condition' in doc and doc['condition'] in CONDITION_MAPPER:
            EDGE_FACTORY = CONDITION_MAPPER[doc['condition']]
            if 'programs' in doc:
                for program_name in doc['programs']:
                    dest_node = create_node_if_not_exists(PROGRAMS, doc, G, program_name, 'program')
                    items += create_edge(EDGE_FACTORY(parent_node, dest_node), doc, G, 'program'),
            if 'classes' in doc:
                for class_name in doc['classes']:
                    dest_node = create_node_if_not_exists(CLASSES, doc, G, class_name, 'class')
                    items += create_edge(EDGE_FACTORY(parent_node, dest_node), doc, G, 'class'),
            # DISREGARD class requisites that are not referring to classes
            # if not doc['programs'] and not doc['classes'] and doc['description']:
            #     items += create_requirement_node(doc, parent_node, G),
    return items


def create_requirement_node(doc: Dict, parent_node: Node, G: Graph) -> Relationship:
    req_node = Node("requirement")
    doc['id'] = get_id_from_string(doc['description'].encode('utf-8'))
    req_node = update_node(req_node, doc)
    G.create(req_node)

    labels = list(parent_node.labels)
    if 'program' in labels:
        label = 'program'
    elif 'specialisation' in labels:
        label = 'specialisation'
    else:
        label = 'class'
    # print(label, parent_node, req_node, doc)
    return create_edge(Requirement(parent_node, req_node), doc, G, label)


def create_nodes_and_edges_if_program(doc: Dict, parent_node: Node, G: Graph, op: str = 'and') -> List[Relationship]:
    """create edges if document is a program or specialisation / major / minor"""
    # create new requirement node and connect to parent
    items = []

    if not doc:
        return items

    if 'description' in doc and doc['description']:
        edge = create_requirement_node(doc, parent_node, G)
        items += edge,

        if 'items' in doc:
            # create each child node and edges
            for child in doc['items']:
                items.extend(create_nodes_and_edges_if_program(child, edge.end_node, G, op))
    elif 'id' in doc and doc['id']:
        if doc['id'] in PROGRAMS:
            label = 'program'
            dest_node = create_node_if_not_exists(PROGRAMS, doc, G, doc['id'], label)
        elif doc['id'] in SPECIAL:
            label = 'specialisation'
            dest_node = create_node_if_not_exists(SPECIAL, doc, G, doc['id'], label)
        else:
            label = 'class'
            dest_node = create_node_if_not_exists(CLASSES, doc, G, doc['id'], label)
        items += create_edge(Requirement(parent_node, dest_node), doc, G, label),
    elif 'type' in doc and doc['type'] and doc['name']:
        items += create_nodes_and_edges_if_specialisation(doc, parent_node, G, op),
    return items


def get_id_from_string(s: str) -> str:
    m = hashlib.md5()
    m.update(s)
    return str(int(m.hexdigest(), 16))[0:12]


def create_nodes_and_edges_if_specialisation(doc: Dict, parent_node: Node, G: Graph, op: str = 'and') -> Relationship:
    assert 'type' in doc and 'name' in doc
    # get id if it does not exist
    if 'id' not in doc:
        doc['type'] = SPEC_MAPPER[doc['type'].lower()]

        name = doc['name']
        if name.endswith('Major'):
            name = name.replace('Major', '').strip()
        elif name.endswith('Minor'):
            name = name.replace('Minor', '').strip()

        for key, val in ALL_SPECIALISATIONS.items():
            if name == val['Name'] and doc['type'] == val['SubplanType']:
                doc['id'] = key

    if 'id' in doc:
        dest_node = create_node_if_not_exists(SPECIAL, doc, G, doc['id'], 'specialisation')
        return create_edge(Requirement(parent_node, dest_node), doc, G, 'specialisation')
