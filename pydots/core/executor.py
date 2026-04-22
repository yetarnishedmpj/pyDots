"""Execute a pyDOT node graph.

This module provides runtime execution of node graphs.
"""

from __future__ import annotations
from typing import Any, Callable
from .graph import Graph, Node, Edge, PortType


class ExecutionContext:
    """Runtime context for executing a node graph."""

    def __init__(self, graph: Graph):
        self.graph = graph
        self.variables: dict[str, Any] = {}
        self.functions: dict[str, Callable] = {}
        self.output: list[str] = []
        self._break_requested = False
        self._continue_requested = False

    def get_input_value(self, node: Node, port_name: str) -> Any:
        """Get the value for an input port."""
        edges = self.graph.find_edges_to(node.id, port_name)
        if edges:
            edge = edges[0]
            source_node = self.graph.get_node(edge.source_node)
            if source_node:
                return self.execute_node(source_node)
        return None

    def execute_node(self, node: Node) -> Any:
        """Execute a single node and return its value."""
        node_type = node.node_type

        # Literals
        if node_type in ("literal_int", "literal_float", "literal_str", "literal_bool", "literal_none"):
            return node.data.get("value")

        # Variable operations
        elif node_type == "variable_get":
            name = node.data.get("name", "?")
            return self.variables.get(name)

        elif node_type == "variable_set":
            value = self.get_input_value(node, "value")
            name = node.data.get("name", "?")
            self.variables[name] = value
            return value

        # Math operations
        elif node_type == "math_add":
            a = self.get_input_value(node, "a") or 0
            b = self.get_input_value(node, "b") or 0
            return a + b
        elif node_type == "math_subtract":
            a = self.get_input_value(node, "a") or 0
            b = self.get_input_value(node, "b") or 0
            return a - b
        elif node_type == "math_multiply":
            a = self.get_input_value(node, "a") or 0
            b = self.get_input_value(node, "b") or 0
            return a * b
        elif node_type == "math_divide":
            a = self.get_input_value(node, "a") or 0
            b = self.get_input_value(node, "b") or 1
            return a / b

        # Comparison
        elif node_type == "compare_eq":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a == b
        elif node_type == "compare_ne":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a != b
        elif node_type == "compare_lt":
            a = self.get_input_value(node, "a") or 0
            b = self.get_input_value(node, "b") or 0
            return a < b

        # Boolean
        elif node_type == "bool_and":
            a = self.get_input_value(node, "a") or False
            b = self.get_input_value(node, "b") or False
            return a and b
        elif node_type == "bool_or":
            a = self.get_input_value(node, "a") or False
            b = self.get_input_value(node, "b") or False
            return a or b
        elif node_type == "bool_not":
            val = self.get_input_value(node, "value") or False
            return not val

        # IO
        elif node_type == "print":
            val = self.get_input_value(node, "value")
            text = str(val) if val is not None else ""
            self.output.append(text)
            print(text)
            return None

        elif node_type == "input":
            prompt = self.get_input_value(node, "prompt") or ""
            return input(str(prompt))

        # Function call
        elif node_type == "function_call":
            name = node.data.get("name", "?")
            args = []
            for i in range(20):
                if node.get_input(f"arg{i}"):
                    args.append(self.get_input_value(node, f"arg{i}"))

            # Built-in functions
            if name == "range":
                return range(*args)
            elif name == "len":
                return len(args[0]) if args else 0
            elif name == "str":
                return str(args[0]) if args else ""
            elif name == "int":
                return int(args[0]) if args else 0
            elif name == "float":
                return float(args[0]) if args else 0.0
            elif name == "list":
                return list(args[0]) if args else []
            elif name == "print":
                print(*args)
                return None

            # User-defined functions
            if name in self.functions:
                return self.functions[name](*args)
            return None

        # List and dict
        elif node_type == "literal_list":
            result = []
            for i in range(100):
                if not node.get_input(f"element{i}"):
                    break
                result.append(self.get_input_value(node, f"element{i}"))
            return result

        elif node_type == "literal_dict":
            result = {}
            for i in range(100):
                if not node.get_input(f"key{i}"):
                    break
                key = self.get_input_value(node, f"key{i}")
                val = self.get_input_value(node, f"value{i}")
                if key is not None:
                    result[key] = val
            return result

        # Subscript
        elif node_type == "subscript":
            obj = self.get_input_value(node, "obj")
            index = self.get_input_value(node, "index")
            if obj is not None and index is not None:
                return obj[index]
            return None

        # Attribute
        elif node_type == "attribute":
            obj = self.get_input_value(node, "obj")
            attr = node.data.get("attr", "")
            if obj is not None:
                return getattr(obj, attr, None)
            return None

        # Control flow
        elif node_type == "if":
            condition = self.get_input_value(node, "condition")
            return condition  # Caller should handle branching

        elif node_type == "for":
            iterable = self.get_input_value(node, "iterable")
            return iterable  # Caller should handle iteration

        elif node_type == "while":
            condition = self.get_input_value(node, "condition")
            return condition  # Caller should handle looping

        return None

    def execute_statement_node(self, node: Node) -> bool:
        """Execute a statement-type node. Returns True to continue, False to stop."""
        node_type = node.node_type

        # Control flow statements
        if node_type == "break":
            self._break_requested = True
            return False

        elif node_type == "continue":
            self._continue_requested = True
            return False

        elif node_type == "return":
            return False

        # For statement nodes, execute normally
        self.execute_node(node)
        return True


def execute(graph: Graph) -> list[str]:
    """Execute a graph and return printed output."""
    ctx = ExecutionContext(graph)

    # Find entry statement nodes
    entry_nodes = find_entry_statements(graph)

    for node_id in entry_nodes:
        node = graph.get_node(node_id)
        if node:
            ctx.execute_statement_node(node)

    return ctx.output


def find_entry_statements(graph: Graph) -> list[str]:
    """Find nodes that should be executed as statements."""
    statement_types = {
        "variable_set", "print", "if", "elif", "else", "for", "while",
        "break", "continue", "return", "function_define", "class_define",
        "import", "import_from", "try", "except", "raise", "with", "pass",
        "function_call"
    }

    has_incoming = set()
    for edge in graph.edges:
        has_incoming.add(edge.target_node)

    entry_nodes = []
    for node_id in graph.nodes:
        node = graph.nodes[node_id]
        if node_id not in has_incoming or node.node_type in statement_types:
            entry_nodes.append(node_id)

    return entry_nodes