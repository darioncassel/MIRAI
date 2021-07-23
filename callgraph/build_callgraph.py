import json
from sys import argv


def parse_defid(defid):
    parts = defid.split('DefId(')[1].split(' ~ ')
    parts = [x.strip() for x in parts]
    return (parts[0], parts[1].strip(')'))


def collect_edges(lines):
    graph = {
        'nodes': {},
        'edges': set(),
        'node_info': {},
    }
    excluded_crates = ['core', 'std', 'alloc', 'mirai_annotations']
    ctr = 0
    for line in lines:
        if '<callgraph>' in line:
            if 'root::' in line:
                node_type = 'root'
                if 'croot::' in line:
                    node_type = 'croot'
                elif '{closure#' in line:
                    node_type = 'closure'
                defid = parse_defid(line.split('root::')[1].strip())
                cont = True
                for crate in excluded_crates:
                    if crate in defid[1]:
                        cont = False
                already_croot = defid[0] in graph['node_info'] and graph['node_info'][defid[0]] == 'croot'
                if cont and not already_croot:
                    graph['nodes'][defid[0]] = defid[1]
                    graph['node_info'][defid[0]] = node_type
                    ctr += 1
            if 'edge::' in line:
                edge_type = None
                if 'cedge::' in line:
                    edge_type = 'black'
                elif 'redge::' in line:
                    edge_type = 'red'
                else:
                    raise Exception('Unreachable')
                parts = line.split('edge::')[1].strip().split('-')
                caller_defid = parse_defid(parts[0])
                callee_defid = parse_defid(parts[1])
                cont = True
                for crate in excluded_crates:
                    if crate in caller_defid[1] or crate in callee_defid[1]:
                        cont = False
                if cont:
                    if caller_defid[0] not in graph['nodes']:
                        graph['nodes'][caller_defid[0]] = caller_defid[1]
                        graph['node_info'][caller_defid[0]] = 'child'
                        ctr += 1
                    if callee_defid[0] not in graph['nodes']:
                        graph['nodes'][callee_defid[0]] = callee_defid[1]
                        graph['node_info'][callee_defid[0]] = 'child'
                        ctr += 1
                    if graph['node_info'][caller_defid[0]] == 'closure':
                        closure_parent_defid = get_closure_parent_defid(graph, caller_defid)
                        if closure_parent_defid:
                            caller_defid = closure_parent_defid
                    if graph['node_info'][callee_defid[0]] == 'closure':
                        closure_parent_defid = get_closure_parent_defid(graph, callee_defid)
                        if closure_parent_defid:
                            callee_defid = closure_parent_defid
                    graph['edges'].add((caller_defid[0], callee_defid[0], edge_type, ctr))
                    ctr += 1
    return {
        'nodes': graph['nodes'],
        'node_info': graph['node_info'],
        'edges': graph['edges'],
    }


def get_closure_parent_defid(graph, closure_defid):
    idx, name = closure_defid[0], closure_defid[1]
    parent_name = '::'.join(name.split('::')[:-1])
    parent_defid = None
    for idx2, name2 in graph['nodes'].items():
        if parent_name == name2:
            parent_defid = (idx2, name2)
            break
    return parent_defid


def add_closure_edges_inner(graph, closure_defid, ctr):
    closure_edges = []
    caller_idx = get_closure_parent_defid(graph, closure_defid)
    if caller_idx:
        closure_edges.append((caller_idx, idx, 'black', ctr))
        ctr += 1
        closure_edges.append((idx, caller_idx, 'red', ctr))
        ctr += 1
    return closure_edges, ctr


def add_closure_edges(graph):
    closure_edges = set()
    for idx, name in graph['nodes'].items():
        if '{closure' in name:
            caller_name = '::'.join(name.split('::')[:-1])
            caller_idx = None
            for idx2, name2 in graph['nodes'].items():
                if caller_name == name2:
                    caller_idx = idx2
                    break
            if caller_idx:
                closure_edges.add((caller_idx, idx, 'black', 0))
                closure_edges.add((idx, caller_idx, 'red', 0))
    return {
        'nodes': graph['nodes'],
        'node_info': graph['node_info'],
        'edges': graph['edges'].union(closure_edges),
    }


def is_parent(graph, idx1, idx2):
    """
    There is a backwards path from idx1 to idx2
    """
    reachable = set(idx1)
    while len(reachable) > 0:
        curr = list(reachable)[0]
        reachable -= set(curr)
        for edge in graph['edges']:
            if edge[0] == idx1:
                if edge[1] == idx2:
                    return True
                else:
                    reachable.add(edge[1])
    return False


def callers(graph):
    return set([x[0] for x in graph['edges']])


def get_parents(graph, idx):
    parents = set()
    for edge in graph['edges']:
        if edge[1] == idx:
            parents.add(edge[0])
    return parents


def get_all_parents(graph, idxs):
    parents = set()
    for idx in idxs:
        parents = parents.union(get_parents(graph, idx))
    return parents


def lca(graph, idx1, idx2):
    """
    Find the least common ancestor of idx1 and node idx2
    """
    parents1 = get_parents(graph, idx1)
    parents2 = get_parents(graph, idx2)
    ctr = 0
    while len(parents1.intersection(parents2)) < 1 and ctr < 100:
        parents1 = get_all_parents(graph, parents1)
        parents2 = get_all_parents(graph, parents2)
        ctr += 1
    common = parents1.intersection(parents2)
    if len(common) == 1:
        return list(common)[0]
    elif len(common) > 1:
        raise Exception('TODO')
    elif len(common) < 1:
        # raise Exception(f'No LCA found: {idx1}, {idx2}')
        return None


def add_sequence_edges(graph):
    """
    If node n1 has sequence number s1 and n1 has number s2
    where n2 is not a parent of n1 and s1 < s2, add an edge
    """
    new_edges = set()
    for idx1, n1 in graph['nodes'].items():
        s1 = int(n1.split('::')[0])
        if idx1 not in callers(graph):
            min_2 = None
            for idx2, n2 in graph['nodes'].items():
                s2 = int(n2.split('::')[0])
                if s1 < s2 and not is_parent(graph, n2, n1):
                    if min_2 is None or s2 < min_2[1]:
                        min_2 = (idx2, s2)
            if min_2 is not None:
                idx_n = lca(graph, idx1, min_2[0])
                if idx_n:
                    new_edges.add((idx1, idx_n, 'blue'))
    return {
        'nodes': graph['nodes'],
        'edges': graph['edges'].union(new_edges),
    }


def add_return_edges(graph):
    return_edges = set()
    for edge in graph['edges']:
        return_edges.add((edge[1], edge[0], 'red'))
    return {
        'nodes': graph['nodes'],
        'node_info': graph['node_info'],
        'edges': graph['edges'].union(return_edges),
    }


def slice_graph(graph, endpoint_name):
    culled_edges = set()
    reachable_node_names = set()
    reachable_node_names.add(endpoint_name)
    changes = True
    while changes:
        changes = False
        for edge in graph['edges']:
            new_reachable_node_names = set()
            for node_name in reachable_node_names:
                if node_name in graph['nodes'][edge[0]]:
                    is_croot = edge[1] in graph['node_info'] and graph['node_info'][edge[1]] == 'croot'
                    if not is_croot or edge[2] == 'black':
                        culled_edges.add(edge)
                        new_reachable_node_names.add(graph['nodes'][edge[1]])
            old_len = len(reachable_node_names)
            reachable_node_names = reachable_node_names.union(new_reachable_node_names)
            if len(reachable_node_names) > old_len:
                changes = True
    reachable_nodes = {}
    reachable_info = {}
    for idx, name in graph['nodes'].items():
        if name in reachable_node_names or endpoint_name in name:
            reachable_nodes[idx] = name
            if idx in graph['node_info']:
                reachable_info[idx] = graph['node_info'][idx]
    return {
        'nodes': reachable_nodes,
        'node_info': reachable_info,
        'edges': culled_edges,
    }


def filter_graph(graph, string):
    reduced_nodes = {}
    reduced_info = {}
    reduced_idxs = set()
    for idx, name in graph['nodes'].items():
        if string in name:
            reduced_nodes[idx] = name
            if idx in graph['node_info']:
                reduced_info[idx] = graph['node_info'][idx]
            reduced_idxs.add(idx)
    reduced_edges = set()
    for edge in graph['edges']:
        if edge[0] in reduced_idxs and edge[1] in reduced_idxs:
            reduced_edges.add(edge)
    return {
        'nodes': reduced_nodes,
        'node_info': reduced_info,
        'edges': reduced_edges,
    }


def reindex(graph):
    translation = {}
    ctr = 0
    new_nodes = {}
    new_info = {}
    for defid, name in graph['nodes'].items():
        translation[defid] = ctr
        new_nodes[ctr] = name
        if defid in graph['node_info']:
            new_info[ctr] = graph['node_info'][defid]
        ctr += 1
    new_edges = set()
    edge_idx = sorted([edge[3] for edge in graph['edges']])
    for edge in graph['edges']:
        new_edge = (translation[edge[0]], translation[edge[1]], edge[2], edge_idx.index(edge[3]) + 1)
        new_edges.add(new_edge)
    return {
        'nodes': new_nodes,
        'node_info': new_info,
        'edges': new_edges,
    }


def shorten_names(graph):
    new_names = {}
    for idx, name in graph['nodes'].items():
        parts = name.split('::')
        if 'closure' in name:
            shortened_name = f'{idx}.{parts[0]}-{parts[-2]}.{parts[-1]}'
        else:
            shortened_name = f'{idx}.{parts[0]}-{parts[-1]}'
        new_names[idx] = shortened_name
    return {
        'nodes': new_names,
        'node_info': graph['node_info'],
        'edges': graph['edges'],
    }


def dedup_edges(graph):
    # Deduplicate to the minimum edge sequence number
    new_edges = {}
    for edge in graph['edges']:
        if (edge[0], edge[1], edge[2]) in new_edges:
            entry = new_edges[(edge[0], edge[1], edge[2])]
            new_edges[(edge[0], edge[1], edge[2])] = (edge[0], edge[1], edge[2], min(entry[3], edge[3]))
        else:
            new_edges[(edge[0], edge[1], edge[2])] = edge
    return {
        'nodes': graph['nodes'],
        'node_info': graph['node_info'],
        'edges': new_edges.values(),
    }


def to_graphviz(graph):
    graph = dedup_edges(graph)
    out_str = 'digraph callgraph {\n\tnode [shape=box];\n'
    effective_nodes = set()
    for edge in graph['edges']:
        n1 = graph['nodes'][edge[0]]
        effective_nodes.add(n1)
    for node in list(effective_nodes):
        out_str += f'\t"{node}"\n'
    for edge in graph['edges']:
        n1 = graph['nodes'][edge[0]]
        n2 = graph['nodes'][edge[1]]
        out_str += f'\t"{n1}" -> "{n2}"\n [label="{edge[3]}" color="{edge[2]}"]\n'
    return out_str + '}'


def to_ddlog(graph):
    dat_out_str = 'start;\n'
    for i, edge in enumerate(graph['edges']):
        etype = 0 if edge[2] == 'black' else 1
        dat_out_str += f'insert Edge({edge[0]},{edge[1]},{edge[3]},{etype})'
        if i == len(graph['edges']) - 1:
            dat_out_str += ';\n'
        else:
            dat_out_str += ',\n'
    dat_out_str += 'commit;\ndump Checked;\ndump NotChecked;\n'
    return dat_out_str


def main(log_path):
    with open(log_path, 'r') as log_f:
        lines = log_f.readlines()
    graph = collect_edges(lines)
    graph = slice_graph(graph, 'verify_script')
    graph = filter_graph(graph, 'check_bounds')
    graph = reindex(graph)
    graph = shorten_names(graph)
    with open('./graph.json', 'w+') as graph_f:
        graph = {'nodes': graph['nodes'], 'node_info': graph['node_info'], 'edges': list(graph['edges'])}
        json.dump(graph, graph_f)
    with open('./graph.dot', 'w+') as dotgraph_f:
        dotgraph = to_graphviz(graph)
        dotgraph_f.write(dotgraph)
    with open('./base.dat', 'w+') as base_dat_f:
        dat_out = to_ddlog(graph)
        base_dat_f.write(dat_out)


if __name__ == '__main__':
    main(argv[1])
