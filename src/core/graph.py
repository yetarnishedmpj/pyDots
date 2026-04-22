"""Node graph data structure for pyDOT.

The graph consists of:
- Nodes: individual operations with input/output ports
- Ports: connection points on nodes (type annotated)
- Edges: connections between ports
- Values: runtime data stored in the graph
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import uuid


class PortType(Enum):
    """Types that ports can carry."""
    ANY = auto()
    INT = auto()
    FLOAT = auto()
    STR = auto()
    BOOL = auto()
    LIST = auto()
    DICT = auto()
    NONE = auto()
    OBJECT = auto()
    FLOW = auto()  # Execution flow port (no data)

    @classmethod
    def from_python(cls, obj: Any) -> PortType:
        """Infer PortType from a Python object."""
        if obj is None:
            return cls.NONE
        t = type(obj)
        if t == bool:
            return cls.BOOL
        elif t == int:
            return cls.INT
        elif t == float:
            return cls.FLOAT
        elif t == str:
            return cls.STR
        elif t == list:
            return cls.LIST
        elif t == dict:
            return cls.DICT
        else:
            return cls.OBJECT

    def to_python_type(self) -> type | None:
        """Get the Python type for this port type."""
        mapping = {
            self.INT: int,
            self.FLOAT: float,
            self.STR: str,
            self.BOOL: bool,
            self.LIST: list,
            self.DICT: dict,
            self.NONE: type(None),
        }
        return mapping.get(self)


class Port:
    """A connection point on a node."""

    def __init__(self, name: str, port_type: PortType, is_input: bool, default_value: Any = None):
        self.name = name
        self.port_type = port_type
        self.is_input = is_input
        self.default_value = default_value
        self.id = uuid.uuid4().hex

    def matches(self, other: Port) -> bool:
        """Check if this port can connect to another."""
        if self.is_input == other.is_input:
            return False  # Can't connect same direction

        # FLOW ports only connect to other FLOW ports
        if self.port_type == PortType.FLOW or other.port_type == PortType.FLOW:
            return self.port_type == other.port_type

        # If either is ANY, allow connection
        if self.port_type == PortType.ANY or other.port_type == PortType.ANY:
            return True

        # Numeric types are compatible in Python
        numeric = {PortType.INT, PortType.FLOAT}
        if self.port_type in numeric and other.port_type in numeric:
            return True

        # Default: types must match exactly
        return self.port_type == other.port_type


class Node:
    """A node in the graph representing an operation."""

    def __init__(self, node_type: str, label: str, x: float = 0, y: float = 0):
        self.id = uuid.uuid4().hex
        self.node_type = node_type
        self.label = label
        self.x = x
        self.y = y
        self.width = 150
        self.height = 60
        self.inputs: list[Port] = []
        self.outputs: list[Port] = []
        self.data: dict[str, Any] = {}

    def add_input(self, name: str, port_type: PortType = PortType.ANY, default: Any = None) -> Port:
        port = Port(name, port_type, is_input=True, default_value=default)
        self.inputs.append(port)
        self._update_height()
        return port

    def add_output(self, name: str, port_type: PortType = PortType.ANY) -> Port:
        port = Port(name, port_type, is_input=False, default_value=None)
        self.outputs.append(port)
        self._update_height()
        return port

    def _update_height(self):
        """Update node height based on port count."""
        port_count = max(len(self.inputs), len(self.outputs))
        self.height = max(60, 20 + port_count * 20)

    def get_input(self, name: str) -> Port | None:
        for p in self.inputs:
            if p.name == name:
                return p
        return None

    def get_output(self, name: str) -> Port | None:
        for p in self.outputs:
            if p.name == name:
                return p
        return None

    def input_rect(self, port_index: int) -> tuple[float, float]:
        """Return (x, y) for input port at index."""
        spacing = self.height / (len(self.inputs) + 1)
        y = spacing * (port_index + 1)
        return (self.x, self.y + y)

    def output_rect(self, port_index: int) -> tuple[float, float]:
        """Return (x, y) for output port at index."""
        spacing = self.height / (len(self.outputs) + 1)
        y = spacing * (port_index + 1)
        return (self.x + self.width, self.y + y)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside the node."""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


class Edge:
    """A connection between two ports."""

    def __init__(self, source_node: str, source_port: str, target_node: str, target_port: str):
        self.id = uuid.uuid4().hex
        self.source_node = source_node
        self.source_port = source_port
        self.target_node = target_node
        self.target_port = target_port

    def __repr__(self):
        return f"Edge({self.source_node}.{self.source_port} -> {self.target_node}.{self.target_port})"


class Graph:
    """The node graph containing all nodes and edges."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.values: dict[str, Any] = {}  # Variable storage

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        if node_id in self.nodes:
            del self.nodes[node_id]
        self.edges = [e for e in self.edges if e.source_node != node_id and e.target_node != node_id]

    def add_edge(self, edge: Edge) -> bool:
        source_node = self.get_node(edge.source_node)
        target_node = self.get_node(edge.target_node)
        if not source_node or not target_node:
            return False

        source_port = source_node.get_output(edge.source_port)
        target_port = target_node.get_input(edge.target_port)
        if not source_port or not target_port:
            return False

        if not source_port.matches(target_port):
            return False

        # Remove existing edge to this input
        self.edges = [e for e in self.edges if not (e.target_node == edge.target_node and e.target_port == edge.target_port)]

        self.edges.append(edge)
        return True

    def remove_edge(self, edge_id: str) -> None:
        self.edges = [e for e in self.edges if e.id != edge_id]

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def find_edges_from(self, node_id: str, port_name: str) -> list[Edge]:
        return [e for e in self.edges if e.source_node == node_id and e.source_port == port_name]

    def find_edges_to(self, node_id: str, port_name: str) -> list[Edge]:
        return [e for e in self.edges if e.target_node == node_id and e.target_port == port_name]

    def find_edges_to_node(self, node_id: str) -> list[Edge]:
        """Find all edges targeting a node."""
        return [e for e in self.edges if e.target_node == node_id]

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self.values.clear()

    def to_dict(self) -> dict:
        """Serialize graph to a dictionary."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "label": n.label,
                    "x": n.x,
                    "y": n.y,
                    "data": n.data
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "id": e.id,
                    "source_node": e.source_node,
                    "source_port": e.source_port,
                    "target_node": e.target_node,
                    "target_port": e.target_port
                }
                for e in self.edges
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Graph':
        """Create a graph from a dictionary."""
        graph = cls()
        for n_data in data.get("nodes", []):
            node = create_node(n_data["node_type"], n_data["x"], n_data["y"])
            if not node:
                node = Node(n_data["node_type"], n_data["label"], n_data["x"], n_data["y"])
            node.id = n_data["id"]
            node.data = n_data.get("data", {})
            graph.add_node(node)
        
        for e_data in data.get("edges", []):
            edge = Edge(
                e_data["source_node"], e_data["source_port"],
                e_data["target_node"], e_data["target_port"]
            )
            edge.id = e_data["id"]
            graph.edges.append(edge)
            
        return graph

    def duplicate_node(self, node_id: str, dx: float = 0, dy: float = 0) -> Node | None:
        """Create a copy of a node with offset position."""
        original = self.nodes.get(node_id)
        if not original:
            return None

        new_node = Node(original.node_type, original.label, original.x + dx, original.y + dy)
        new_node.data = dict(original.data)
        new_node.width = original.width

        for inp in original.inputs:
            new_node.add_input(inp.name, inp.port_type, inp.default_value)
        for out in original.outputs:
            new_node.add_output(out.name, out.port_type)

        self.add_node(new_node)
        return new_node


# Node type definitions - defines what each node type looks like
NODE_DEFINITIONS: dict[str, dict] = {
    # Literals
    "literal_int": {
        "label": "Integer",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [],
        "outputs": [{"name": "value", "type": PortType.INT}]
    },
    "literal_float": {
        "label": "Float",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [],
        "outputs": [{"name": "value", "type": PortType.FLOAT}]
    },
    "literal_str": {
        "label": "String",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [],
        "outputs": [{"name": "value", "type": PortType.STR}]
    },
    "literal_bool": {
        "label": "Boolean",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [],
        "outputs": [{"name": "value", "type": PortType.BOOL}]
    },
    "literal_list": {
        "label": "List",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [{"name": "element0", "type": PortType.ANY}],
        "outputs": [{"name": "value", "type": PortType.LIST}]
    },
    "literal_tuple": {
        "label": "Tuple",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [{"name": "element0", "type": PortType.ANY}],
        "outputs": [{"name": "value", "type": PortType.LIST}]
    },
    "literal_set": {
        "label": "Set",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [{"name": "element0", "type": PortType.ANY}],
        "outputs": [{"name": "value", "type": PortType.LIST}]
    },
    "literal_dict": {
        "label": "Dict",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [{"name": "key0", "type": PortType.ANY}, {"name": "value0", "type": PortType.ANY}],
        "outputs": [{"name": "value", "type": PortType.DICT}]
    },
    "literal_none": {
        "label": "None",
        "category": "Literals",
        "color": "#4a9",
        "inputs": [],
        "outputs": [{"name": "value", "type": PortType.NONE}]
    },

    # Variables
    "variable_get": {
        "label": "Get Variable",
        "category": "Variables",
        "color": "#a67",
        "inputs": [],
        "outputs": [{"name": "value", "type": PortType.ANY}]
    },
    "variable_set": {
        "label": "Set Variable",
        "category": "Variables",
        "color": "#a67",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "value", "type": PortType.ANY}
        ],
        "outputs": [
            {"name": "exec_out", "type": PortType.FLOW},
            {"name": "result", "type": PortType.ANY}
        ]
    },

    # Math operations
    "math_add": {
        "label": "a + b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.FLOAT}, {"name": "b", "type": PortType.FLOAT}],
        "outputs": [{"name": "result", "type": PortType.FLOAT}]
    },
    "math_subtract": {
        "label": "a - b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.FLOAT}, {"name": "b", "type": PortType.FLOAT}],
        "outputs": [{"name": "result", "type": PortType.FLOAT}]
    },
    "math_multiply": {
        "label": "a * b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.FLOAT}, {"name": "b", "type": PortType.FLOAT}],
        "outputs": [{"name": "result", "type": PortType.FLOAT}]
    },
    "math_divide": {
        "label": "a / b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.FLOAT}, {"name": "b", "type": PortType.FLOAT}],
        "outputs": [{"name": "result", "type": PortType.FLOAT}]
    },
    "math_mod": {
        "label": "a % b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_power": {
        "label": "a ** b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_floor_div": {
        "label": "a // b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_bit_and": {
        "label": "a & b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_bit_or": {
        "label": "a | b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_bit_xor": {
        "label": "a ^ b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_lshift": {
        "label": "a << b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_rshift": {
        "label": "a >> b",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },
    "math_negate": {
        "label": "-a",
        "category": "Math",
        "color": "#36d",
        "inputs": [{"name": "value", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.ANY}]
    },

    # Comparison
    "compare_eq": {
        "label": "a == b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_ne": {
        "label": "a != b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_lt": {
        "label": "a < b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_lte": {
        "label": "a <= b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_gt": {
        "label": "a > b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_gte": {
        "label": "a >= b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_is": {
        "label": "a is b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_is_not": {
        "label": "a is not b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_in": {
        "label": "a in b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "compare_not_in": {
        "label": "a not in b",
        "category": "Compare",
        "color": "#a63",
        "inputs": [{"name": "a", "type": PortType.ANY}, {"name": "b", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },

    # Boolean operations
    "bool_and": {
        "label": "a and b",
        "category": "Boolean",
        "color": "#3a5",
        "inputs": [{"name": "a", "type": PortType.BOOL}, {"name": "b", "type": PortType.BOOL}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "bool_or": {
        "label": "a or b",
        "category": "Boolean",
        "color": "#3a5",
        "inputs": [{"name": "a", "type": PortType.BOOL}, {"name": "b", "type": PortType.BOOL}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "bool_not": {
        "label": "not a",
        "category": "Boolean",
        "color": "#3a5",
        "inputs": [{"name": "value", "type": PortType.BOOL}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },

    # Control flow
    "if": {
        "label": "If",
        "category": "Control",
        "color": "#a3a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "condition", "type": PortType.BOOL}
        ],
        "outputs": [{"name": "then", "type": PortType.FLOW}, {"name": "else", "type": PortType.FLOW}]
    },
    "elif": {
        "label": "Elif",
        "category": "Control",
        "color": "#a3a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "condition", "type": PortType.BOOL}
        ],
        "outputs": [{"name": "next", "type": PortType.FLOW}]
    },
    "else": {
        "label": "Else",
        "category": "Control",
        "color": "#a3a",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": [{"name": "next", "type": PortType.FLOW}]
    },
    "for": {
        "label": "For Loop",
        "category": "Control",
        "color": "#a3a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "iterable", "type": PortType.LIST},
            {"name": "loop_var", "type": PortType.STR, "default": "_"}
        ],
        "outputs": [{"name": "body", "type": PortType.FLOW}, {"name": "done", "type": PortType.FLOW}]
    },
    "while": {
        "label": "While Loop",
        "category": "Control",
        "color": "#a3a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "condition", "type": PortType.BOOL}
        ],
        "outputs": [{"name": "body", "type": PortType.FLOW}, {"name": "done", "type": PortType.FLOW}]
    },
    "break": {
        "label": "Break",
        "category": "Control",
        "color": "#a3a",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": []
    },
    "continue": {
        "label": "Continue",
        "category": "Control",
        "color": "#a3a",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": []
    },
    "pass": {
        "label": "Pass",
        "category": "Control",
        "color": "#a3a",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": [{"name": "exec_out", "type": PortType.FLOW}]
    },
    "return": {
        "label": "Return",
        "category": "Control",
        "color": "#a3a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "value", "type": PortType.ANY}
        ],
        "outputs": []
    },

    # Functions
    "function_define": {
        "label": "Define Function",
        "category": "Functions",
        "color": "#5aa",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW}
        ],
        "outputs": [
            {"name": "exec_out", "type": PortType.FLOW},
            {"name": "body", "type": PortType.FLOW},
            {"name": "func", "type": PortType.OBJECT}
        ]
    },
    "function_call": {
        "label": "Call Function",
        "category": "Functions",
        "color": "#5aa",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "func", "type": PortType.OBJECT},
            {"name": "arg0", "type": PortType.ANY}
        ],
        "outputs": [
            {"name": "exec_out", "type": PortType.FLOW},
            {"name": "result", "type": PortType.ANY}
        ]
    },

    # Classes
    "class_define": {
        "label": "Define Class",
        "category": "Classes",
        "color": "#a5a",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": [
            {"name": "exec_out", "type": PortType.FLOW},
            {"name": "body", "type": PortType.FLOW},
            {"name": "cls", "type": PortType.OBJECT}
        ]
    },

    # IO
    "print": {
        "label": "Print",
        "category": "IO",
        "color": "#55a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "value", "type": PortType.ANY}
        ],
        "outputs": [{"name": "exec_out", "type": PortType.FLOW}]
    },
    "input": {
        "label": "Input",
        "category": "IO",
        "inputs": [{"name": "prompt", "type": PortType.STR}],
        "outputs": [{"name": "value", "type": PortType.STR}]
    },

    # Import
    "import": {
        "label": "Import",
        "category": "Modules",
        "color": "#777",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": [
            {"name": "exec_out", "type": PortType.FLOW},
            {"name": "module", "type": PortType.OBJECT}
        ]
    },
    "import_from": {
        "label": "From Import",
        "category": "Modules",
        "color": "#777",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": [
            {"name": "exec_out", "type": PortType.FLOW},
            {"name": "exports", "type": PortType.OBJECT}
        ]
    },

    # Exception handling
    "try": {
        "label": "Try",
        "category": "Exceptions",
        "color": "#a55",
        "inputs": [{"name": "exec_in", "type": PortType.FLOW}],
        "outputs": [
            {"name": "body", "type": PortType.FLOW},
            {"name": "except", "type": PortType.FLOW},
            {"name": "finally", "type": PortType.FLOW},
            {"name": "done", "type": PortType.FLOW}
        ]
    },
    "except": {
        "label": "Except",
        "category": "Exceptions",
        "color": "#a55",
        "inputs": [{"name": "type", "type": PortType.OBJECT}],
        "outputs": [{"name": "handler", "type": PortType.FLOW}, {"name": "next", "type": PortType.FLOW}]
    },
    "raise": {
        "label": "Raise",
        "category": "Exceptions",
        "color": "#a55",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "error", "type": PortType.OBJECT}
        ],
        "outputs": []
    },

    # Context managers
    "with": {
        "label": "With",
        "category": "Context",
        "color": "#5a5",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "context", "type": PortType.OBJECT}
        ],
        "outputs": [
            {"name": "body", "type": PortType.FLOW},
            {"name": "done", "type": PortType.FLOW}
        ]
    },

    # Lambda
    "lambda": {
        "label": "Lambda",
        "category": "Functions",
        "color": "#5aa",
        "inputs": [{"name": "arg0", "type": PortType.ANY}],
        "outputs": [{"name": "func", "type": PortType.OBJECT}]
    },

    # Comprehensions
    "list_comp": {
        "label": "List Comp",
        "category": "Comprehensions",
        "color": "#5a5",
        "inputs": [{"name": "element", "type": PortType.ANY}, {"name": "iterable", "type": PortType.LIST}],
        "outputs": [{"name": "result", "type": PortType.LIST}]
    },

    # Slices and subscripts
    "subscript": {
        "label": "Get Item",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "obj", "type": PortType.ANY}, {"name": "index", "type": PortType.ANY}],
        "outputs": [{"name": "value", "type": PortType.ANY}]
    },
    "slice": {
        "label": "Slice",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "obj", "type": PortType.ANY}, {"name": "start", "type": PortType.INT}, {"name": "stop", "type": PortType.INT}],
        "outputs": [{"name": "result", "type": PortType.LIST}]
    },

    # Attribute access
    "attribute": {
        "label": "Get Attribute",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "obj", "type": PortType.OBJECT}],
        "outputs": [{"name": "value", "type": PortType.ANY}]
    },
    "to_int": {
        "label": "int(value)",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "value", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.INT}]
    },
    "to_float": {
        "label": "float(value)",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "value", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.FLOAT}]
    },
    "to_str": {
        "label": "str(value)",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "value", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.STR}]
    },
    "to_bool": {
        "label": "bool(value)",
        "category": "Operations",
        "color": "#66a",
        "inputs": [{"name": "value", "type": PortType.ANY}],
        "outputs": [{"name": "result", "type": PortType.BOOL}]
    },
    "delete": {
        "label": "Delete",
        "category": "Operations",
        "color": "#66a",
        "inputs": [
            {"name": "exec_in", "type": PortType.FLOW},
            {"name": "target", "type": PortType.ANY}
        ],
        "outputs": [{"name": "exec_out", "type": PortType.FLOW}]
    },
}


def create_node(node_type: str, x: float = 0, y: float = 0) -> Node | None:
    """Factory function to create a node from definitions."""
    defn = NODE_DEFINITIONS.get(node_type)
    if not defn:
        return None

    node = Node(node_type, defn["label"], x, y)
    node.data["node_type"] = node_type

    for inp in defn.get("inputs", []):
        node.add_input(inp["name"], inp.get("type", PortType.ANY), inp.get("default"))

    for out in defn.get("outputs", []):
        node.add_output(out["name"], out.get("type", PortType.ANY))

    return node


# Port colors by type
PORT_COLORS = {
    PortType.ANY: "#aaa",
    PortType.INT: "#4a9",
    PortType.FLOAT: "#4a9",
    PortType.STR: "#a74",
    PortType.BOOL: "#a63",
    PortType.LIST: "#76a",
    PortType.DICT: "#6a7",
    PortType.NONE: "#666",
    PortType.OBJECT: "#888",
    PortType.FLOW: "#f80",
}