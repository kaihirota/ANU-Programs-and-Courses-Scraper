import hashlib
import json
import os
from collections import defaultdict
from pprint import pprint
from py2neo import Graph, Node, Relationship, Subgraph
from typing import Dict, List

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

CLASSES = defaultdict(lambda: Node('Course'))
PROGRAMS = defaultdict(lambda: Node('Program'))
SPECIAL = defaultdict(lambda: Node('Specialisation'))

NOT_FOUND = []
UNMERGED_EDGES = []
MERGED_EDGES = []


class PREREQUISITE(Relationship):
    name = 'Prerequisite'

class INCOMPATIBLE(Relationship):
    name = 'Incompatible'

class ENROLLED(Relationship):
    name = 'Enrolled'

class UNKNOWN(Relationship):
    name = 'Unknown'

class COTAUGHT(Relationship):
    name = 'Co-taught'

class REQUIREMENT(Relationship):
    name = 'Requirement'


CONDITION_MAPPER = {
    'completed': PREREQUISITE,
    'incompatible': INCOMPATIBLE,
    'studying': ENROLLED,
    'enrolled': ENROLLED,
    'Unknown': UNKNOWN,
    'permission': UNKNOWN,
    'obtained': UNKNOWN
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
    if doc:
        if 'condition' in doc:
            edge['condition'] = doc['condition']
        if 'description' in doc:
            edge['description'] = doc['description']
        if 'negation' in doc:
            edge['negation'] = doc['negation']

    if label == 'Requirement':
        labels = list(edge.end_node.labels)
        label = labels[0]

    if not label:
        labels = list(edge.start_node.labels)
        label = labels[0]

    global UNMERGED_EDGES
    global MERGED_EDGES
    try:
        G.merge(edge, label, 'id')
        MERGED_EDGES += (edge, label),
    except Exception as e:
        UNMERGED_EDGES += (edge, label),

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
                    dest_node = create_node_if_not_exists(PROGRAMS, doc, G, program_name, 'Program')
                    items += create_edge(EDGE_FACTORY(parent_node, dest_node), doc, G, 'Program'),
            if 'classes' in doc:
                for class_name in doc['classes']:
                    dest_node = create_node_if_not_exists(CLASSES, doc, G, class_name, 'Course')
                    items += create_edge(EDGE_FACTORY(parent_node, dest_node), doc, G, 'Course'),
            # DISREGARD class requisites that are not referring to classes
            # if not doc['programs'] and not doc['classes'] and doc['description']:
            #     items += create_requirement_node(doc, parent_node, G),
    return items


def create_requirement_node(doc: Dict, parent_node: Node, G: Graph) -> Relationship:
    req_node = Node("Requirement")
    doc['id'] = get_id_from_string(doc['description'].encode('utf-8'))
    req_node = update_node(req_node, doc)
    G.create(req_node)

    labels = list(parent_node.labels)
    if 'Program' in labels:
        label = 'Program'
    elif 'Specialisation' in labels:
        label = 'Specialisation'
    else:
        label = 'Course'
    return create_edge(REQUIREMENT(parent_node, req_node), doc, G, label)


def create_nodes_and_edges_if_program(doc: Dict, parent_node: Node, G: Graph, op: str = 'and') -> List[Relationship]:
    """create edges if document is a program or specialisation / major / minor"""
    # create new requirement node and connect to parent
    global NOT_FOUND
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
            label = 'Program'
            dest_node = create_node_if_not_exists(PROGRAMS, doc, G, doc['id'], label)
        elif doc['id'] in SPECIAL:
            label = 'Specialisation'
            dest_node = create_node_if_not_exists(SPECIAL, doc, G, doc['id'], label)
        else:
            label = 'Course'
            dest_node = create_node_if_not_exists(CLASSES, doc, G, doc['id'], label)
        items += create_edge(REQUIREMENT(parent_node, dest_node), doc, G, label),
    elif type(doc) == list:
        for child in doc:
            items.extend(create_nodes_and_edges_if_program(child, parent_node, G, op))
    else:
        NOT_FOUND += doc,
    return items


def get_id_from_string(s: str) -> str:
    m = hashlib.md5()
    m.update(s)
    return str(int(m.hexdigest(), 16))[0:12]


def main():
    G = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    G.delete_all()

    with open("data/scraped/classes.json") as f:
        classes = json.load(f)

    with open("data/scraped/programs.json") as f:
        programs = json.load(f)

    with open("data/scraped/specialisations.json") as f:
        special = json.load(f)

    print(f"classes: {len(classes)}, programs: {len(programs)}, special: {len(special)}")

    try:
        G.schema.create_uniqueness_constraint('Course', 'id')
        G.schema.create_uniqueness_constraint('Program', 'id')
        G.schema.create_uniqueness_constraint('Specialisation', 'id')
    except Exception as e:
        pass

    ####### create nodes #######
    for doc in classes:
        create_node_if_not_exists(CLASSES, doc, G, doc['id'], 'Course')
    print('classes: ', len(CLASSES))

    for doc in programs:
        create_node_if_not_exists(PROGRAMS, doc, G, doc['id'], 'Program')
    print('programs:', len(PROGRAMS))

    for doc in special:
        create_node_if_not_exists(SPECIAL, doc, G, doc['id'], 'Specialisation')
    print('specialisations:', len(SPECIAL))

    print('Nodes:', G.run("""
        MATCH (n)
        RETURN count(n)
    """))

    ####### create edges #######
    for doc in classes:
        if 'prerequisites' in doc:
            create_nodes_and_edges_if_class_requisite(doc['prerequisites'], CLASSES[doc['id']], G)
        # if 'co_taught' in doc:
        #     if type(doc['co_taught']) == list:
        #         for item in doc['co_taught']:
        #             edge = Cotaught(CLASSES[doc['id']], CLASSES[item])
        #             edge['id'] = CLASSES[doc['id']] + CLASSES[item]
        #             create_edge(edge, None, G, 'class')
        #     else:
        #         edge = Cotaught(CLASSES[doc['id']], CLASSES[doc['co_taught']])
        #         edge['id'] = CLASSES[doc['id']] + CLASSES[doc['co_taught']]
        #         create_edge(edge, None, G, 'class')
    print('Completed merging edges for classes')

    for doc in programs:
        src_node = PROGRAMS[doc['id']]
        for requirement in doc['requirements']:
            create_nodes_and_edges_if_program(requirement, src_node, G)
    print('Completed merging edges for programs')

    for doc in special:
        src_node = SPECIAL[doc['id']]
        for requirement in doc['requirements']:
            create_nodes_and_edges_if_program(requirement, src_node, G)
    print('Completed merging edges for specialisations')

    print('Edges', G.run("""
        MATCH ()-[r]-()
        RETURN count(r)
    """))

    print('Failed to merge edges:', len(UNMERGED_EDGES))
    print('Merged edges:', len(MERGED_EDGES))
    print('Not found:', len(NOT_FOUND))


if __name__ == "__main__":
    main()
