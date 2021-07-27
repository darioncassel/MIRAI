import json
from sys import argv
from enum import Enum


class NodeType(Enum):
    # Regular root
    ROOT = 1
    # Crate root: Starting point for analysis (pub fn)
    CROOT = 2
    # Closure
    CLOSURE = 3


class Node(object):

    def __init__(self, defid: str, name: str, ntype: NodeType):
        """
        A Node has a DefId, name, and type.
        
        Nodes are uniquely identified by their DefId.
        """
        self.defid = defid
        self.name = name
        self.ntype = ntype
    
    def __repr__(self):
        return f'Node({self.defid}, {self.name}, {self.ntype})'


class EdgeDir(Enum):
    # Caller
    CALL = 1
    # Return
    RET = 2


class Edge(object):

    def __init__(self, caller_id: str, callee_id: str, direction: EdgeDir, rtype: str, id=None):
        """
        An Edge connects two nodes.

        Edges are uniquely identified by their endpoints, direction, and Rust type.
        """
        self.caller_id = caller_id
        self.callee_id = callee_id
        self.direction = direction
        self.rtype = rtype
        self.id = id

    def hash(self):
        """
        Return the edge's info in a way that can be hashed, e.g., for a set.
        """
        return (self.caller_id, self.callee_id, self.direction, self.rtype, self.id)

    def min_hash(self):
        """
        Return the edge's minimal info in a way that can be hashed, e.g., for a set.
        """
        return (self.caller_id, self.callee_id, self.direction)

    def __repr__(self):
        return f'Edge({self.id}, {self.caller_id}, {self.callee_id}, {self.direction}, {self.rtype})'


class CallGraph(object):

    def __init__(self, nodes={}, edges={}, rtypes={}):
        # A map from defid to Node
        self.nodes = nodes
        # A map of Edge hashes to Edges
        self.edges = edges
        # An index of types
        self.rtypes = rtypes
        # Crates to exclude from call graph
        self.excluded_crates = ['core', 'std', 'alloc', 'mirai_annotations']

    def maybe_add_node(self, node):
        """
        Add a node to the graph if conditions are satisifed
        """
        cont = True
        # Node should not belong to an excluded crate
        for crate in self.excluded_crates:
            if crate in node.name:
                cont = False
        # If the node is already present in the graph
        # as a CROOT, don't overwrite it
        if node.defid in self.nodes \
            and self.nodes[node.defid].ntype == NodeType.CROOT:
                cont = False
        if cont:
            self.nodes[node.defid] = node
    
    def get_node(self, defid):
        """
        Get a node by defid
        """
        if defid in self.nodes:
            return self.nodes[defid]
        else:
            raise Exception(f'No node found for DefId: {defid}')

    def get_node_by_name(self, name):
        """
        Get the first node associated (substring) with
        the given name.
        """
        for node in self.nodes.values():
            if name in node.name:
                return node
        raise Exception(f'No node found with name: {name}')

    def _get_closure_parent_defid(self, closure_node):
        """
        Heuristic for finding the parent of a closure based
        on node names.
        """
        parent_name = '::'.join(closure_node.name.split('::')[:-1])
        parent_defid = None
        for defid, node in self.nodes.items():
            if parent_name == node.name:
                parent_defid = defid
                break
        return parent_defid

    def _resolve_closures(self, edge):
        """
        Heuristic for resolving closure edges to their parent nodes.
        """
        caller_node = self.get_node(edge.caller_id)
        callee_node = self.get_node(edge.callee_id)
        if caller_node.ntype == NodeType.CLOSURE:
            closure_parent_defid = self._get_closure_parent_defid(caller_node)
            if closure_parent_defid:
                edge.caller_id = closure_parent_defid
        if callee_node.ntype == NodeType.CLOSURE:
            closure_parent_defid = self._get_closure_parent_defid(callee_node)
            if closure_parent_defid:
                edge.callee_id = closure_parent_defid
        return edge

    def maybe_add_edge(self, edge):
        """
        Add an edge to the graph if its endpoints both exist.
        """
        if edge.caller_id in self.nodes and edge.callee_id in self.nodes:
            # Resolve edge closures
            edge = self._resolve_closures(edge)
            # Assign an ID to the edge
            edge.id = len(self.edges)
            # Add the Rust type associated with the edge
            rtype_id = None
            if edge.rtype in self.rtypes.values():
                for k, v in self.rtypes.items():
                    if edge.rtype == v:
                        rtype_id = k
                        break
            else:
                rtype_id = len(self.rtypes)
                self.rtypes[rtype_id] = edge.rtype
            # Set the Rust type to its index
            edge.rtype = rtype_id
            self.edges[edge.hash()] = edge


def parse_defid(line):
    """
    Parse a DefId from a line.
    """
    try:
        parts = line.split('DefId(')[1].split(' ~ ')
        parts = [x.strip() for x in parts]
        return (parts[0], parts[1].strip(')'))
    except Exception as exn:
        print(line)
        raise exn


def parse_node(line):
    """
    Parse a node from a line.
    """
    try:
        node_type = NodeType.ROOT
        if 'croot::' in line:
            node_type = NodeType.CROOT
        elif '{closure#' in line:
            node_type = NodeType.CLOSURE
        defid, node_name = parse_defid(line)
        return Node(defid, node_name, node_type)
    except Exception as exn:
        print(line)
        raise exn


def parse_edges(line):
    """
    Parse edge(s) from a raw line
    """
    edge_type = None
    edge_args = []
    # Currently, only caller's args are recorded
    if 'cedge::' in line:
        edge_type = EdgeDir.CALL
        arg_part = line.split('|=')[1].strip()
        edge_args = [x.strip() for x in arg_part[1:-1].split(',')]
    elif 'redge::' in line:
        edge_type = EdgeDir.RET
    else:
        raise Exception('Unreachable')
    parts = line.split('edge::')[1].strip().split('-')
    caller_id = parse_defid(parts[0])[0]
    callee_id = parse_defid(parts[1])[0]
    edges = []
    if len(edge_args) == 0:
        edge = Edge(caller_id, callee_id, edge_type, '')
        edges.append(edge)
    else:
        for arg in edge_args:
            edge = Edge(caller_id, callee_id, edge_type, arg)
            edges.append(edge)
    return edges


def parse_graph(lines):
    """
    Parse the call graph from MIRAI's debug output.
    """
    graph = CallGraph()
    for line in lines:
        # print('glen: ', len(graph.nodes))
        if '<callgraph>' in line:
            line = line.split('<callgraph> ')[1]
            if 'root::' in line:
                node = parse_node(line)
                graph.maybe_add_node(node)
            if 'edge::' in line:
                edges = parse_edges(line)
                for edge in edges:
                    # Add endpoint nodes if they don't already exist
                    graph.maybe_add_node(parse_node(line.split('-')[0], ))
                    graph.maybe_add_node(parse_node(line.split('-')[1]))
                    graph.maybe_add_edge(edge)
    return graph


def slice_graph(graph, name):
    """
    Slice the graph to only include nodes that reachable
    from the node corresponding to the given name.
    """
    node = graph.get_node_by_name(name)
    reachable_nodes = {node.defid: node}
    reachable_edges = {}
    reachable_rtypes = {}
    node_queue = [node]
    while len(node_queue) != 0:
        caller_node = node_queue.pop(0)
        for edge in graph.edges.values():
            if caller_node.defid == edge.caller_id:
                callee_node = graph.get_node(edge.callee_id)
                # Stop at the CROOT boundary unless the CROOT is directly called
                if edge.direction == EdgeDir.CALL or callee_node.ntype != NodeType.CROOT:
                    reachable_edges[edge.hash()] = edge
                    reachable_rtypes[edge.rtype] = graph.rtypes[edge.rtype]
                    # Only add this endpoint if we haven't already seen it
                    if callee_node.defid not in reachable_nodes:
                        reachable_nodes[callee_node.defid] = callee_node
                        node_queue.append(callee_node)
    return CallGraph(reachable_nodes, reachable_edges, reachable_rtypes)


def filter_graph(graph, string):
    """
    Filter graph to only include nodes with certain substrings.
    """
    reduced_nodes = {}
    reduced_edges = {}
    reduced_rtypes = {}
    for defid, node in graph.nodes.items():
        if string in node.name:
            reduced_nodes[defid] = node
    for edge_hash, edge in graph.edges.items():
        if edge.caller_id in reduced_nodes and edge.callee_id in reduced_nodes:
            reduced_edges[edge_hash] = edge
            reduced_rtypes[edge.rtype] = graph.rtypes[edge.rtype]
    return CallGraph(reduced_nodes, reduced_edges, reduced_rtypes)


def reindex(graph):
    """
    Map DefIds to integers.
    """
    translation = {}
    new_nodes = {}
    new_edges = {}
    for defid, node in graph.nodes.items():
        ctr = len(translation)
        translation[defid] = ctr
        new_nodes[ctr] = node
    edge_ids = sorted([edge.id for edge in graph.edges.values()])
    for edge in graph.edges.values():
        new_edge = Edge(
            translation[edge.caller_id], 
            translation[edge.callee_id], 
            edge.direction,
            edge.rtype,
            edge_ids.index(edge.id) + 1
        )
        new_edges[new_edge.hash()] = new_edge
    return CallGraph(new_nodes, new_edges, graph.rtypes)


def to_json(graph):
    """
    Change graph representation for JSON serialization.
    """
    nodes = {}
    for idx, node in graph.nodes.items():
        nodes[idx] = {
            'defid': node.defid,
            'name': node.name,
            'ntype': str(node.ntype),
        }
    edges = []
    for edge in graph.edges.values():
        edges.append({
            'id': edge.id,
            'caller_id': edge.caller_id,
            'callee_id': edge.callee_id,
            'direction': str(edge.direction),
            'rtype': edge.rtype,
        })
    return {
        'nodes': nodes,
        'edges': edges,
        'rtypes': graph.rtypes,
    }


def from_json(graph_json):
    """
    Deserialize graph from JSON.
    """
    nodes = {}
    for idx, node in graph_json['nodes'].items():
        ntype_str = node['ntype']
        ntype = None
        if ntype_str == 'NodeType.ROOT':
            ntype = NodeType.ROOT
        elif ntype_str == 'NodeType.CROOT':
            ntype = NodeType.CROOT
        elif ntype_str == 'NodeType.CLOSURE':
            ntype = NodeType.CLOSURE
        else:
            raise Exception(f'Unexpected NodeType: {ntype_str}')
        nodes[idx] = Node(node['defid'], node['name'], ntype)
    edges = {}
    for edge in graph_json['edges']:
        dir_str = edge['direction']
        edge_dir = None
        if dir_str == 'EdgeDir.CALL':
            edge_dir = EdgeDir.CALL
        elif dir_str == 'EdgeDir.RET':
            edge_dir = EdgeDir.RET
        else:
            raise Exception(f'Unexpected EdgeDir: {dir_str}')
        edge = Edge(edge['caller_id'], edge['callee_id'], edge_dir, edge['rtype'], edge['id'])
        edges[edge.hash()] = edge
    return CallGraph(nodes, edges, graph_json['rtypes'])


def dedup_edges(graph):
    """
    Deduplicate edges to the minimum edge sequence number.
    """
    new_edges_id = {}
    new_edges = {}
    for edge in graph.edges.values():
        if edge.min_hash() in new_edges_id:
            curr_min_id = new_edges_id[edge.min_hash()]
            if edge.id < curr_min_id:
                new_edges_id[edge.min_hash()] = edge.id
                new_edges[edge.hash()] = edge
        else:
            new_edges_id[edge.min_hash()] = edge.id
            new_edges[edge.hash()] = edge
    return CallGraph(graph.nodes, new_edges, graph.rtypes)


def shorten_name(node):
    """
    Shorten a node's name for cleaner presentation.
    """
    parts = node.name.split('::')
    if 'closure' in node.name:
        shortened_name = f'{node.defid}.{parts[0]}-{parts[-2]}.{parts[-1]}'
    else:
        shortened_name = f'{node.defid}.{parts[0]}-{parts[-1]}'
    return shortened_name


def to_graphviz(graph):
    """
    Convert the graph to dot representation for viewing.
    """
    graph = dedup_edges(graph)
    graph = reindex(graph)
    out_str = 'digraph callgraph {\n\tnode [shape=box];\n'
    effective_nodes = set()
    for edge in graph.edges.values():
        effective_nodes.add(edge.caller_id)
        effective_nodes.add(edge.callee_id)
    for node in graph.nodes.values():
        if node.defid in effective_nodes:
            out_str += f'\t"{shorten_name(node)}"\n'
    for edge in graph.edges.values():
        n1 = shorten_name(graph.nodes[edge.caller_id])
        n2 = shorten_name(graph.nodes[edge.callee_id])
        color = 'black' if edge.direction == EdgeDir.CALL else 'red'
        out_str += f'\t"{n1}" -> "{n2}"\n [label="{edge.id}" color="{color}"]\n'
    return out_str + '}'


def to_ddlog(graph):
    """
    Convert the graph to datalog representation for analysis.
    """
    arg_nums = {}
    dat_out_str = 'start;\n'
    for edge in graph.edges.values():
        edge_dir = 0 if edge.direction == EdgeDir.CALL else 1
        dat_out_str += f'insert Edge({edge.id},{edge.caller_id},{edge.callee_id});\n'
        dat_out_str += f'insert EdgeSeq({edge.id},{edge.id});\n'
        dat_out_str += f'insert EdgeDir({edge.id},{edge_dir});\n'
        dat_out_str += f'insert EdgeType({edge.id},{edge.rtype});\n'
    dat_out_str += 'commit;\ndump Checked;\ndump NotChecked;\n'
    return dat_out_str


def main(log_path):
    # Parse the graph from MIRAI debug output
    with open(log_path, 'r') as log_f:
        lines = log_f.readlines()
    graph = parse_graph(lines)
    # Ensure that the JSON representation is sufficient
    graph_json = to_json(graph)
    graph = from_json(graph_json)
    # Reduce the graph to nodes relevant for this analysis
    graph = slice_graph(graph, 'verify_script')
    graph = filter_graph(graph, '::check_bounds::')
    graph = reindex(graph)
    with open('./graph.json', 'w+') as graph_f:
        json.dump(to_json(graph), graph_f)
    with open('./graph.dot', 'w+') as dotgraph_f:
        dotgraph = to_graphviz(graph)
        dotgraph_f.write(dotgraph)
    with open('./base.dat', 'w+') as base_dat_f:
        dat_out = to_ddlog(graph)
        base_dat_f.write(dat_out)


if __name__ == '__main__':
    main(argv[1])
