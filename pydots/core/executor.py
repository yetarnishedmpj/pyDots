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
        self._return_value = None
        self._return_requested = False

    def get_input_value(self, node: Node, port_name: str) -> Any:
        """Get the value for an input port."""
        edges = self.graph.find_edges_to(node.id, port_name)
        if edges:
            edge = edges[0]
            source_node = self.graph.get_node(edge.source_node)
            if source_node:
                return self.execute_node(source_node)
        
        # Check for default value in port
        port = node.get_input(port_name)
        if port and port.default_value is not None:
            return port.default_value
            
        return None

    def execute_node(self, node: Node) -> Any:
        """Execute a single node and return its value (for expression nodes)."""
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
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) + (b or 0)
        elif node_type == "math_subtract":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) - (b or 0)
        elif node_type == "math_multiply":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) * (b or 0)
        elif node_type == "math_divide":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) / (b or 1)
        elif node_type == "math_mod":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) % (b or 1)
        elif node_type == "math_power":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) ** (b or 1)

        elif node_type == "math_negate":
            val = self.get_input_value(node, "value")
            return -val if val is not None else 0

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
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) < (b or 0)
        elif node_type == "compare_lte":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) <= (b or 0)
        elif node_type == "compare_gt":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) > (b or 0)
        elif node_type == "compare_gte":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return (a or 0) >= (b or 0)
        elif node_type == "compare_is":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a is b
        elif node_type == "compare_is_not":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a is not b
        elif node_type == "compare_in":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a in b if b is not None else False
        elif node_type == "compare_not_in":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a not in b if b is not None else True

        # Boolean
        elif node_type == "bool_and":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a and b
        elif node_type == "bool_or":
            a = self.get_input_value(node, "a")
            b = self.get_input_value(node, "b")
            return a or b
        elif node_type == "bool_not":
            val = self.get_input_value(node, "value")
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

        elif node_type == "fstring":
            parts = node.data.get("parts", [])
            result = ""
            for part in parts:
                if part["type"] == "literal":
                    result += str(part["value"])
                elif part["type"] == "expr":
                    val = self.get_input_value(node, f"part{part['index']}")
                    result += str(val)
            return result

        elif node_type == "attribute_set":
            obj = self.get_input_value(node, "obj")
            attr = node.data.get("attr", "")
            val = self.get_input_value(node, "value")
            if obj is not None:
                setattr(obj, attr, val)
            return val

        elif node_type == "subscript_set":
            obj = self.get_input_value(node, "obj")
            idx = self.get_input_value(node, "index")
            val = self.get_input_value(node, "value")
            if obj is not None and idx is not None:
                obj[idx] = val
            return val

        return None

    def execute_flow(self, start_node_id: str | None) -> None:
        """Follow the execution flow starting from a node."""
        current_node_id = start_node_id
        while current_node_id:
            if self._break_requested or self._continue_requested or self._return_requested:
                break
                
            node = self.graph.get_node(current_node_id)
            if not node:
                break
                
            current_node_id = self.execute_statement_node(node)

    def execute_statement_node(self, node: Node) -> str | None:
        """Execute a statement node and return the ID of the next node to execute."""
        node_type = node.node_type

        if node_type == "if":
            condition = self.get_input_value(node, "condition")
            if condition:
                # Follow 'then' branch
                then_node = self._get_next_node(node, "then")
                if then_node:
                    self.execute_flow(then_node.id)
            else:
                # Follow 'else' branch
                else_node = self._get_next_node(node, "else")
                if else_node:
                    self.execute_flow(else_node.id)
            
            # After if/else, follow 'exec_out' if it exists (some if nodes might have it)
            return self._get_next_node_id(node, "exec_out")

        elif node_type == "while":
            while True:
                condition = self.get_input_value(node, "condition")
                if not condition or self._return_requested:
                    break
                
                body_node = self._get_next_node(node, "body")
                if body_node:
                    self.execute_flow(body_node.id)
                    
                if self._break_requested:
                    self._break_requested = False
                    break
                if self._continue_requested:
                    self._continue_requested = False
                    continue
            
            return self._get_next_node_id(node, "done") or self._get_next_node_id(node, "exec_out")

        elif node_type == "for":
            iterable = self.get_input_value(node, "iterable")
            loop_var = node.data.get("loop_var", "_")
            
            if iterable:
                for item in iterable:
                    if self._return_requested:
                        break
                    self.variables[loop_var] = item
                    
                    body_node = self._get_next_node(node, "body")
                    if body_node:
                        self.execute_flow(body_node.id)
                        
                    if self._break_requested:
                        self._break_requested = False
                        break
                    if self._continue_requested:
                        self._continue_requested = False
                        continue
            
            return self._get_next_node_id(node, "done") or self._get_next_node_id(node, "exec_out")

        elif node_type == "break":
            self._break_requested = True
            return None

        elif node_type == "continue":
            self._continue_requested = True
            return None

        elif node_type == "return":
            self._return_value = self.get_input_value(node, "value")
            self._return_requested = True
            return None

        # General statement
        self.execute_node(node)
        return self._get_next_node_id(node, "exec_out")

    def _get_next_node(self, node: Node, port_name: str) -> Node | None:
        edges = self.graph.find_edges_from(node.id, port_name)
        if edges:
            return self.graph.get_node(edges[0].target_node)
        return None

    def _get_next_node_id(self, node: Node, port_name: str) -> str | None:
        node = self._get_next_node(node, port_name)
        return node.id if node else None


def execute(graph: Graph) -> list[str]:
    """Execute a graph and return printed output."""
    ctx = ExecutionContext(graph)

    # Find entry statement nodes
    entry_nodes = find_entry_statements(graph)

    for node_id in entry_nodes:
        ctx.execute_flow(node_id)

    return ctx.output


def find_entry_statements(graph: Graph) -> list[str]:
    """Find nodes that should be executed as starting points of flow."""
    # Entry points are statement nodes that have no incoming FLOW edges.
    
    flow_targets = set()
    for edge in graph.edges:
        target_node = graph.get_node(edge.target_node)
        if target_node:
            port = target_node.get_input(edge.target_port)
            if port and port.port_type == PortType.FLOW:
                flow_targets.add(edge.target_node)

    statement_types = {
        "variable_set", "print", "if", "elif", "else", "for", "while",
        "break", "continue", "return", "function_define", "class_define",
        "import", "import_from", "try", "except", "raise", "with", "pass",
        "function_call", "delete", "attribute_set", "subscript_set"
    }

    entry_nodes = []
    for node_id, node in graph.nodes.items():
        if node.node_type in statement_types:
            if node_id not in flow_targets:
                entry_nodes.append(node_id)
        elif not any(edge.source_node == node_id for edge in graph.edges):
            # Also include expressions that are not connected to anything
            if node_id not in flow_targets: # Expressions shouldn't be flow targets anyway
                 entry_nodes.append(node_id)

    return entry_nodes
