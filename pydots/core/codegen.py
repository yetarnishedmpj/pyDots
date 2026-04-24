"""Generate Python code from a pyDOT node graph.

Performs reverse transformation: node graph → executable Python source.
"""

from __future__ import annotations
from typing import Iterator
from .graph import Graph, Node, Edge, PortType, NODE_DEFINITIONS


class CodeGenerator:
    """Generate Python code from a node graph."""

    def __init__(self, graph: Graph):
        self.graph = graph
        self._output: list[str] = []
        self._temp_counter = 0
        self._temp_vars: set[str] = set()
        self._visited: set[str] = set()

    def generate(self) -> str:
        """Generate Python code from the graph."""
        self._output.clear()
        self._temp_counter = 0
        self._visited.clear()

        # Find entry point nodes
        entry_nodes = self._find_entry_nodes()

        for node_id in entry_nodes:
            self._generate_from_node(node_id)

        # Clean up result
        result = "\n".join(self._output)
        return result

    def _find_entry_nodes(self) -> list[str]:
        """Find nodes that should start code generation (top-level statements)."""
        entry_nodes = []
        for node_id, node in self.graph.nodes.items():
            if self._is_statement(node):
                # Check if it has any incoming FLOW edges
                has_incoming_flow = False
                for edge in self.graph.find_edges_to_node(node_id):
                    # Find which port it targets
                    target_node = self.graph.get_node(edge.target_node)
                    if target_node:
                        # Find the port
                        for p in target_node.inputs:
                            if p.name == edge.target_port and p.port_type == PortType.FLOW:
                                has_incoming_flow = True
                                break
                    if has_incoming_flow: break
                
                if not has_incoming_flow:
                    entry_nodes.append(node_id)
            else:
                # For expressions, only if they are not connected to anything
                has_outgoing = any(e.source_node == node_id for e in self.graph.edges)
                if not has_outgoing:
                    entry_nodes.append(node_id)
        
        return entry_nodes

    def _generate_from_node(self, node_id: str, indent: int = 0) -> str | None:
        """Recursively generate code starting from a node, following FLOW."""
        if node_id in self._visited:
            return None
        self._visited.add(node_id)

        node = self.graph.get_node(node_id)
        if not node:
            return None

        code = self._generate_node(node, indent)

        # If it's a statement, follow exec_out
        if self._is_statement(node):
            if code and isinstance(code, str):
                self._output.append(code)
            
            # Follow simple sequence flow
            next_node = self._get_output_connection(node, "exec_out")
            if next_node:
                self._generate_from_node(next_node.id, indent)

        return code

    def _is_statement(self, node: Node) -> bool:
        """Check if a node produces a statement (not just an expression)."""
        statement_types = {
            "variable_set", "print", "if", "elif", "else", "for", "while",
            "break", "continue", "return", "function_define", "class_define",
            "import", "import_from", "try", "except", "raise", "with", "pass", "delete",
            "function_call", "attribute_set", "subscript_set"
        }
        return node.node_type in statement_types

    def _generate_node(self, node: Node, indent: int = 0) -> str | None:
        """Generate code for a single node."""
        node_type = node.node_type

        # Literals
        if node_type == "literal_int":
            return str(node.data.get("value", 0))
        elif node_type == "literal_float":
            return str(node.data.get("value", 0.0))
        elif node_type == "literal_str":
            val = node.data.get("value", "")
            return repr(val)
        elif node_type == "literal_bool":
            val = node.data.get("value", False)
            return "True" if val else "False"
        elif node_type == "literal_none":
            return "None"
        elif node_type == "literal_list":
            return self._gen_list(node)
        elif node_type == "literal_dict":
            return self._gen_dict(node)
        elif node_type == "literal_tuple":
            return self._gen_tuple(node)
        elif node_type == "literal_set":
            return self._gen_set(node)

        # Variables
        elif node_type == "variable_get":
            return node.data.get("name", "?")
        elif node_type == "variable_set":
            return self._gen_variable_set(node, indent)

        # Math
        elif node_type in ("math_add", "math_subtract", "math_multiply", "math_divide",
                          "math_mod", "math_power", "math_floor_div",
                          "math_bit_and", "math_bit_or", "math_bit_xor",
                          "math_lshift", "math_rshift"):
            return self._gen_math_op(node)
        elif node_type == "math_negate":
            val = self._get_input_value(node, "value")
            return f"(-{val})" if val else "(-?)"

        # Compare
        elif node_type in ("compare_eq", "compare_ne", "compare_lt", "compare_lte",
                          "compare_gt", "compare_gte", "compare_is", "compare_is_not",
                          "compare_in", "compare_not_in"):
            return self._gen_compare_op(node)

        # Boolean
        elif node_type == "bool_and":
            return self._gen_bool_op(node, "and")
        elif node_type == "bool_or":
            return self._gen_bool_op(node, "or")
        elif node_type == "bool_not":
            val = self._get_input_value(node, "value")
            return f"not {val}" if val else "not ?"

        # Control flow - these generate statements, not expressions
        elif node_type == "if":
            return self._gen_if(node, indent)
        elif node_type == "elif":
            return self._gen_elif(node, indent)
        elif node_type == "else":
            return self._gen_else(node, indent)
        elif node_type == "for":
            return self._gen_for(node, indent)
        elif node_type == "while":
            return self._gen_while(node, indent)
        elif node_type == "break":
            return self._indent_str(indent) + "break"
        elif node_type == "continue":
            return self._indent_str(indent) + "continue"
        elif node_type == "return":
            return self._gen_return(node, indent)
        elif node_type == "pass":
            return self._indent_str(indent) + "pass"

        # Functions
        elif node_type == "function_define":
            return self._gen_function_def(node, indent)
        elif node_type == "function_call":
            return self._gen_call(node)
        elif node_type == "lambda":
            return self._gen_lambda(node)

        # Classes
        elif node_type == "class_define":
            return self._gen_class_def(node, indent)

        # IO
        elif node_type == "print":
            return self._gen_print(node, indent)
        elif node_type == "input":
            val = self._get_input_value(node, "prompt")
            return f"input({val})"

        # Import
        elif node_type == "import":
            names = node.data.get("names", [])
            return self._indent_str(indent) + f"import {', '.join(names)}"
        elif node_type == "import_from":
            module = node.data.get("module", "")
            names = node.data.get("names", [])
            return self._indent_str(indent) + f"from {module} import {', '.join(names)}"

        # Exception handling
        elif node_type == "try":
            return self._gen_try(node, indent)
        elif node_type == "except":
            return self._gen_except(node, indent)
        elif node_type == "raise":
            return self._gen_raise(node, indent)

        # Context managers
        elif node_type == "with":
            return self._gen_with(node, indent)

        # Subscript and attribute
        elif node_type == "subscript":
            obj = self._get_input_value(node, "obj")
            idx = self._get_input_value(node, "index")
            if obj and idx:
                return f"{obj}[{idx}]"
            return "?[?]"
        elif node_type == "attribute":
            obj = self._get_input_value(node, "obj")
            attr = node.data.get("attr", "?")
            if obj:
                return f"{obj}.{attr}"
            return f"?.{attr}"
        elif node_type == "to_int":
            val = self._get_input_value(node, "value") or "?"
            return f"int({val})"
        elif node_type == "to_float":
            val = self._get_input_value(node, "value") or "?"
            return f"float({val})"
        elif node_type == "to_str":
            val = self._get_input_value(node, "value") or "?"
            return f"str({val})"
        elif node_type == "to_bool":
            val = self._get_input_value(node, "value") or "?"
            return f"bool({val})"
        elif node_type == "slice":
            obj = self._get_input_value(node, "obj")
            start = self._get_input_value(node, "start") or ""
            stop = self._get_input_value(node, "stop") or ""
            return f"{obj}[{start}:{stop}]"

        # Comprehensions
        elif node_type == "list_comp":
            return self._gen_list_comp(node)
        elif node_type == "dict_comp":
            return self._gen_dict_comp(node)
        elif node_type == "if_exp":
            return self._gen_if_exp(node)

        elif node_type == "fstring":
            parts = node.data.get("parts", [])
            content = ""
            for part in parts:
                if part["type"] == "literal":
                    content += str(part["value"])
                elif part["type"] == "expr":
                    val = self._get_input_value(node, f"part{part['index']}") or "?"
                    # Strip quotes if it's a literal string being inserted? No, f-string handles it.
                    # Wait, if it's an expression, we want {expr}
                    content += "{" + val + "}"
            return f'f"{content}"'

        # Special
        elif node_type == "delete":
            target = self._get_input_value(node, "target") or "?"
            return self._indent_str(indent) + f"del {target}"

        elif node_type == "attribute_set":
            obj = self._get_input_value(node, "obj") or "?"
            attr = node.data.get("attr", "?")
            val = self._get_input_value(node, "value") or "None"
            return self._indent_str(indent) + f"{obj}.{attr} = {val}"

        elif node_type == "subscript_set":
            obj = self._get_input_value(node, "obj") or "?"
            idx = self._get_input_value(node, "index") or "?"
            val = self._get_input_value(node, "value") or "None"
            return self._indent_str(indent) + f"{obj}[{idx}] = {val}"

        return None

    def _get_input_value(self, node: Node, port_name: str) -> str | None:
        """Get the value connected to an input port."""
        edges = self.graph.find_edges_to(node.id, port_name)
        if not edges:
            # Check for default value
            for inp in node.inputs:
                if inp.name == port_name and inp.default_value is not None:
                    return repr(inp.default_value)
            return None

        edge = edges[0]
        source_node = self.graph.get_node(edge.source_node)
        if not source_node:
            return None

        val = self._generate_node(source_node)
        return val

    def _get_output_connection(self, node: Node, port_name: str) -> Node | None:
        """Get the node connected to an output port."""
        edges = self.graph.find_edges_from(node.id, port_name)
        if edges:
            return self.graph.get_node(edges[0].target_node)
        return None

    def _indent_str(self, indent: int) -> str:
        return "    " * indent

    def _gen_list(self, node: Node) -> str:
        elements = []
        for i in range(100):  # Check up to 100 elements
            inp = node.get_input(f"element{i}")
            if not inp:
                break
            val = self._get_input_value(node, f"element{i}")
            if val:
                elements.append(val)
        return f"[{', '.join(elements)}]"

    def _gen_dict(self, node: Node) -> str:
        pairs = []
        for i in range(100):
            key_inp = node.get_input(f"key{i}")
            val_inp = node.get_input(f"value{i}")
            if not key_inp or not val_inp:
                break
            key = self._get_input_value(node, f"key{i}")
            val = self._get_input_value(node, f"value{i}")
            if key and val:
                pairs.append(f"{key}: {val}")
        return "{" + ", ".join(pairs) + "}"

    def _gen_tuple(self, node: Node) -> str:
        elements = []
        for i in range(100):
            if not node.get_input(f"element{i}"):
                break
            val = self._get_input_value(node, f"element{i}")
            if val:
                elements.append(val)
        return "(" + ", ".join(elements) + ")"

    def _gen_set(self, node: Node) -> str:
        elements = []
        for i in range(100):
            if not node.get_input(f"element{i}"):
                break
            val = self._get_input_value(node, f"element{i}")
            if val:
                elements.append(val)
        return "{" + ", ".join(elements) + "}"

    def _gen_variable_set(self, node: Node, indent: int) -> str:
        name = node.data.get("name", "?")
        val = self._get_input_value(node, "value") or "None"
        return self._indent_str(indent) + f"{name} = {val}"

    def _gen_math_op(self, node: Node) -> str:
        op_map = {
            "math_add": "+", "math_subtract": "-", "math_multiply": "*",
            "math_divide": "/", "math_mod": "%", "math_power": "**",
            "math_floor_div": "//", "math_bit_and": "&", "math_bit_or": "|",
            "math_bit_xor": "^", "math_lshift": "<<", "math_rshift": ">>",
        }
        op = op_map.get(node.node_type, "+")
        a = self._get_input_value(node, "a") or "?"
        b = self._get_input_value(node, "b") or "?"
        return f"({a} {op} {b})"

    def _gen_compare_op(self, node: Node) -> str:
        op_map = {
            "compare_eq": "==", "compare_ne": "!=", "compare_lt": "<",
            "compare_lte": "<=", "compare_gt": ">", "compare_gte": ">=",
            "compare_is": "is", "compare_is_not": "is not",
            "compare_in": "in", "compare_not_in": "not in",
        }
        op = op_map.get(node.node_type, "==")
        a = self._get_input_value(node, "a") or "?"
        b = self._get_input_value(node, "b") or "?"
        return f"({a} {op} {b})"

    def _gen_bool_op(self, node: Node, op: str) -> str:
        a = self._get_input_value(node, "a") or "?"
        b = self._get_input_value(node, "b") or "?"
        return f"({a} {op} {b})"

    def _gen_if(self, node: Node, indent: int) -> str:
        cond = self._get_input_value(node, "condition") or "?"
        self._output.append(self._indent_str(indent) + f"if {cond}:")
        
        # Then body
        then_node = self._get_output_connection(node, "then")
        if then_node:
            self._generate_from_node(then_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")

        # Else body
        else_node = self._get_output_connection(node, "else")
        if else_node:
            self._output.append(self._indent_str(indent) + "else:")
            self._generate_from_node(else_node.id, indent + 1)
            
        return None

    def _gen_elif(self, node: Node, indent: int) -> str:
        cond = self._get_input_value(node, "condition") or "?"
        self._output.append(self._indent_str(indent) + f"elif {cond}:")
        return None

    def _gen_else(self, node: Node, indent: int) -> str:
        self._output.append(self._indent_str(indent) + "else:")
        return None

    def _gen_for(self, node: Node, indent: int) -> str:
        iterable = self._get_input_value(node, "iterable") or "?"
        var = node.data.get("loop_var", "_")
        self._output.append(self._indent_str(indent) + f"for {var} in {iterable}:")
        
        # Body
        body_node = self._get_output_connection(node, "body")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        return None

    def _gen_while(self, node: Node, indent: int) -> str:
        cond = self._get_input_value(node, "condition") or "?"
        self._output.append(self._indent_str(indent) + f"while {cond}:")
        
        # Body
        body_node = self._get_output_connection(node, "body")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        return None

    def _gen_return(self, node: Node, indent: int) -> str:
        val = self._get_input_value(node, "value")
        if val:
            return self._indent_str(indent) + f"return {val}"
        return self._indent_str(indent) + "return"

    def _gen_function_def(self, node: Node, indent: int) -> str:
        name = node.data.get("name", "?")
        args = [inp.name for inp in node.inputs if inp.name not in ("exec_in", "func")]
        self._output.append(self._indent_str(indent) + f"def {name}({', '.join(args)}):")
        
        # Body
        body_node = self._get_output_connection(node, "body")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        return None

    def _gen_class_def(self, node: Node, indent: int) -> str:
        name = node.data.get("name", "?")
        self._output.append(self._indent_str(indent) + f"class {name}:")
        
        # Body
        body_node = self._get_output_connection(node, "body")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        return None

    def _gen_call(self, node: Node) -> str:
        name = node.data.get("name", "?")
        args = []
        for i in range(20):
            if node.get_input(f"arg{i}"):
                val = self._get_input_value(node, f"arg{i}")
                if val:
                    args.append(val)
        return f"{name}({', '.join(args)})"

    def _gen_lambda(self, node: Node) -> str:
        args = [inp.name for inp in node.inputs if inp.name != "func"]
        body = self._get_input_value(node, "element0") or "?"
        return f"lambda {', '.join(args)}: {body}"

    def _gen_print(self, node: Node, indent: int) -> str:
        val = self._get_input_value(node, "value") or "?"
        return self._indent_str(indent) + f"print({val})"

    def _gen_raise(self, node: Node, indent: int) -> str:
        val = self._get_input_value(node, "error") or "?"
        return self._indent_str(indent) + f"raise {val}"

    def _gen_try(self, node: Node, indent: int) -> str:
        self._output.append(self._indent_str(indent) + "try:")
        
        # Body
        body_node = self._get_output_connection(node, "body")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        # Except
        except_node = self._get_output_connection(node, "except")
        if except_node:
            self._generate_from_node(except_node.id, indent)
            
        # Finally
        finally_node = self._get_output_connection(node, "finally")
        if finally_node:
            self._output.append(self._indent_str(indent) + "finally:")
            self._generate_from_node(finally_node.id, indent + 1)

        return None

    def _gen_except(self, node: Node, indent: int) -> str:
        exc_type = node.data.get("type", "Exception")
        self._output.append(self._indent_str(indent) + f"except {exc_type}:")
        
        # Handler body
        body_node = self._get_output_connection(node, "handler")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        return None

    def _gen_with(self, node: Node, indent: int) -> str:
        ctx = self._get_input_value(node, "context") or "?"
        self._output.append(self._indent_str(indent) + f"with {ctx} as _:")
        
        # Body
        body_node = self._get_output_connection(node, "body")
        if body_node:
            self._generate_from_node(body_node.id, indent + 1)
        else:
            self._output.append(self._indent_str(indent + 1) + "pass")
            
        return None

    def _gen_list_comp(self, node: Node) -> str:
        elem = self._get_input_value(node, "element") or "?"
        iterable = self._get_input_value(node, "iterable") or "?"
        return f"[{elem} for _ in {iterable}]"

    def _gen_dict_comp(self, node: Node) -> str:
        key = self._get_input_value(node, "key") or "?"
        val = self._get_input_value(node, "value") or "?"
        iterable = self._get_input_value(node, "iterable") or "?"
        return f"{{{key}: {val} for _ in {iterable}}}"

    def _gen_if_exp(self, node: Node) -> str:
        cond = self._get_input_value(node, "condition") or "?"
        true_val = self._get_input_value(node, "true_value") or "?"
        false_val = self._get_input_value(node, "false_value") or "?"
        return f"({true_val} if {cond} else {false_val})"


def generate(graph: Graph) -> str:
    """Convenience function to generate code from a graph."""
    gen = CodeGenerator(graph)
    return gen.generate()