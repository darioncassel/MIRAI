import re
import json
from sys import argv
from pathlib import Path


def parse_type_map(type_map_path):
    """
    Read in a mapping from type indexes to type strings
    """
    type_map = {}
    with open(type_map_path, 'r') as type_map_f:
        type_map = json.load(type_map_f)
    return {int(k): v for k, v in type_map.items()}


def parse_dot_graph(graph_path):
    """
    Generate a mapping from node indexes to node names
    """
    with open(graph_path, 'r') as graph_f:
        lines = graph_f.readlines()
    mapping = {}
    for line in lines:
        if 'label = ' in line:
            match = re.search(r'(\d+) \[.*\\"(.+)\\"', line)
            if match:
                node_id, node_name = match.groups()
                if node_id in mapping:
                    raise Exception(f'Duplicate node ID found: {node_id}')
                mapping[int(node_id)] = node_name
    return mapping


def parse_analysis_line(line):
    """
    Parse a Datalog output relation into this format:
    {
        "name": Relation name,
        "operands": [
            {
                "name": Operand name,
                "index": Node or type index
            }
        ]
    }
    """
    parts = line.split('{')
    relation_name = parts[0]
    if ',' in parts[1]:
        relation_operands_raw = parts[1].split(',')
    else:
        relation_operands_raw = [parts[1]]
    operands = []
    for operand_raw in relation_operands_raw:
        match = re.search(r'\.(\w+) = (\d+)', operand_raw)
        if match:
            operand_name, operand_id = match.groups()
            operands.append({
                "name": operand_name,
                "index": int(operand_id)
            })
    return {
        "name": relation_name,
        "operands": operands
    }


def parse_analysis(analysis_output_path):
    """
    Parse all of the analysis output relations
    """
    relations = []
    with open(analysis_output_path, 'r') as analysis_f:
        lines = analysis_f.readlines()
    for line in lines:
        try:
            relations.append(parse_analysis_line(line))
        except Exception as exn:
            print(f'Failed to parse analysis line: {line}')
            raise exn
    return relations


def decode_analysis_out(relations, mappings):
    """
    Use the mappings to decode indexes in relation 
    operands to strings
    """
    decoded = []
    for relation in relations:
        try:
            for operand in relation['operands']:
                if 'node' in operand['name'] or 'checker' in operand['name']:
                    operand['string'] = mappings["nodes"][operand["index"]]
                elif operand['name'] == 't':
                    operand['string'] = mappings["types"][operand["index"]]
                else:
                    raise Exception(f'Unhandled operand: {operand["name"]}')
            decoded.append(relation)
        except Exception as exn:
            print(f'Failed to decode relation: {relation}')
            raise exn
    return decoded


def main(args):
    graph_path = Path(args[0])
    type_map_path = Path(args[1])
    analysis_output_path = Path(args[2])
    mappings = {
        "nodes": parse_dot_graph(graph_path),
        "types": parse_type_map(type_map_path),
    }
    relations = parse_analysis(analysis_output_path)
    decoded = decode_analysis_out(relations, mappings)
    with open('decoded.json', 'w+') as decoded_f:
        json.dump(decoded, decoded_f)


if __name__ == '__main__':
    main(argv[1:])
