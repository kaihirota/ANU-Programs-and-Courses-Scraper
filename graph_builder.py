from typing import Dict, List
from collections import defaultdict
import json
from pprint import pprint

from py2neo import Graph, Node, Relationship, Subgraph

# G = Graph("bolt://localhost:7687")
# username = "neo4j"
# password = "KrRsKLC26qhHSdj4PG_qRso98GdyDbZOTQrdvvZPr8Q"
# G = Graph(f"neo4j+s://{username}:{password}@f2c1d80b.databases.neo4j.io")

# G.delete_all()

# with open("data/scraped/classes.json") as f:
#     classes = json.load(f)

# with open("data/scraped/programs.json") as f:
#     programs = json.load(f)

# with open("data/scraped/specialisations.json") as f:
#     special = json.load(f)

CLASSES = defaultdict(lambda: Node("class"))
PROGRAMS = defaultdict(lambda: Node("program"))
SPECIAL = defaultdict(lambda: Node("specialisation"))
REQ = defaultdict(lambda: Node("requirement"))


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
    if 'id' in doc:
        node.identity = node['id'] = doc['id']
    node = update_node(node, doc)
    G.merge(node, label, key)
    return node


def create_node_if_not_exists(cache: defaultdict, doc: Dict, G: Graph, label: str, key: str) -> Node:
    dest_node = cache[key]
    dest_node = upsert_node(dest_node, doc, G, label, key)
    return dest_node


def create_edge(edge: Relationship, doc: Dict, G: Graph, label: str = None, key: str = 'id') -> Relationship:
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
        labels = str(edge.end_node.labels).split(':')
        labels = [item for item in labels if item]
        label = labels[0]

    if not label:
        labels = str(edge.start_node.labels).split(':')
        labels = [item for item in labels if item]
        label = labels[0]

    G.merge(edge, label, key')
    return edge


def create_nodes_and_edges_if_class_requisite(doc: Dict, parent_node: Node, G: Graph, op: str) -> List[Relationship]:
    items = []

    if doc:
        if 'operator' in doc and type(doc['operator']) == dict:
            for operator in doc['operator'].keys():
                for requirement in doc['operator'][operator]:
                    items.extend(create_nodes_and_edges_if_class_requisite(
                        requirement, parent_node, G, operator))
        elif 'condition' in doc and doc['condition'] in CONDITION_MAPPER:
            EDGE_FACTORY = CONDITION_MAPPER[doc['condition']]
            if 'programs' in doc:
                for program_name in doc['programs']:
                    dest_node = create_node_if_not_exists(
                        PROGRAMS, program_name, doc, G)
                    items += create_edge(EDGE_FACTORY(parent_node,
                                         dest_node), doc, G),
            if 'classes' in doc:
                for class_name in doc['classes']:
                    dest_node = create_node_if_not_exists(
                        CLASSES, class_name, doc, G)
                    items += create_edge(EDGE_FACTORY(parent_node,
                                         dest_node), doc, G),
            if not doc['programs'] and not doc['classes'] and doc['description']:
                items += create_requirement_node(doc, parent_node, G),
    return items


def create_requirement_node(doc: Dict, parent_node: Node, G: Graph) -> Relationship:
    req_node = Node("requirement")
    req_node = update_node(req_node, doc)
    return create_edge(Requirement(parent_node, req_node), doc, G)


def create_nodes_and_edges_if_program(doc: Dict, parent_node: Node, G: Graph, op: str) -> List[Relationship]:
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
                items.extend(create_nodes_and_edges_if_program(
                    child, edge.end_node, G, op))
    elif 'id' in doc and doc['id']:
        if doc['id'] in PROGRAMS:
            dest_node = create_node_if_not_exists(PROGRAMS, doc['id'], doc, G)
        elif doc['id'] in SPECIAL:
            dest_node = create_node_if_not_exists(SPECIAL, doc['id'], doc, G)
        else:
            dest_node = create_node_if_not_exists(CLASSES, doc['id'], doc, G)
        items += create_edge(Requirement(parent_node, dest_node), doc, G),
    elif 'type' in doc and doc['type']:
        items += create_nodes_and_edges_if_specialisation(doc, parent_node, G, op),
    return items


def create_nodes_and_edges_if_specialisation(doc: Dict, parent_node: Node, G: Graph, op: str) -> Relationship:
    # TODO get id if it does not exist
    dest_node = create_node_if_not_exists(SPECIAL, doc['name'], doc, G)
    return create_edge(Requirement(parent_node, dest_node), doc, G)
