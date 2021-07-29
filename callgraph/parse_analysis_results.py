import re
import json
from sys import argv
from pathlib import Path


def parse_analysis_line(line):
    match = re.search(r'CheckedT{\.node = (\d+), \.rtype = (\d+)}', line)
    if match:
        node_id, rtype_id = match.groups()
        return (node_id, rtype_id)
    else:
        raise Exception(f'Failed to parse line: {line}')


def decode_analysis_out(graph, ids):
    checked = {}
    for node_id, rtype_id in ids:
        node_name = None
        if node_id in graph['nodes']:
            node_name = graph['nodes'][node_id]['name']
        else:
            raise Exception(f'Invalid node ID: {node_id}')
        rtype = None
        if rtype_id in graph['rtypes']:
            rtype = graph['rtypes'][rtype_id]
        else:
            raise Exception(f'Invalid rtype ID: {node_id}')
        if node_name not in checked:
            checked[node_name] = set([rtype])
        else:
            checked[node_name].add(rtype)
    return {k: list(v) for k, v in checked.items()}


def main(args):
    graph_data = Path(args[0])
    analysis_out = Path(args[1])
    graph = {}
    with open(graph_data, 'r') as graph_f:
        graph = json.load(graph_f)
    ids = []
    with open(analysis_out, 'r') as analysis_f:
        lines = analysis_f.readlines()
        for line in lines:
            ids.append(parse_analysis_line(line))
    checked = decode_analysis_out(graph, ids)
    with open('decoded.json', 'w+') as decoded_f:
        json.dump(checked, decoded_f)


if __name__ == '__main__':
    main(argv[1:])
