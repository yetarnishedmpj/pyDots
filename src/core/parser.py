"""Python AST to pyDOT node graph parser.

Converts Python source code into a visual node graph representation.
"""

from __future__ import annotations
import ast
from typing import Any
from .graph import Graph, Node, Edge, PortType, NODE_DEFINITIONS, create_node


class ASTParser:
    """Parse Python AST into a pyDOT graph."""

    def __init__(self):
        self.graph = Graph()
        self._temp_counter = 0

    def _temp(self) -> str:
        self._temp_counter += 1
        return f"_t{self._temp_counter}"

    def parse(self, source: str) -> Graph:
        """Parse Python source into a graph."""
        tree = ast.parse(source)
        self.graph.clear()

        self._parse_statement_list(tree.body)

        return self.graph

    def _parse_statement_list(self, body: list[ast.stmt], flow_node: Node = None, flow_port: str = "exec_out") -> Node | None:
        """Parse a list of statements and chain them together via FLOW ports."""
        current_flow_node = flow_node
        current_flow_port = flow_port
        first_stmt_node = None

        for stmt in body:
            stmt_node = self._parse_statement(stmt)
            if not stmt_node:
                continue

            if not first_stmt_node:
                first_stmt_node = stmt_node

            # Connect to previous flow if applicable
            if current_flow_node:
                # Check if this node accepts flow input
                if any(p.name == "exec_in" for p in stmt_node.inputs):
                    self._connect_nodes(current_flow_node, stmt_node, current_flow_port, "exec_in")
                elif any(p.name == "condition" for p in stmt_node.inputs) and stmt_node.node_type == "if":
                    # If nodes might not have exec_in but we want to connect them to flow?
                    # Actually, our 'if' definition didn't have exec_in. Let's check.
                    pass

            # Update flow for next statement
            # For now, only simple statements have exec_out. 
            # Blocks like if/for/while merge their flow later (advanced).
            if any(p.name == "exec_out" for p in stmt_node.outputs):
                current_flow_node = stmt_node
                current_flow_port = "exec_out"
            else:
                # For block nodes, the flow continues after the block
                # (This needs more complex merge logic, but let's just break the chain for now)
                current_flow_node = None

        return first_stmt_node

    def _add_edge(self, source_id: str, source_port: str, target_id: str, target_port: str) -> bool:
        edge = Edge(source_id, source_port, target_id, target_port)
        return self.graph.add_edge(edge)

    def _parse_statement(self, stmt: ast.stmt) -> Node | None:
        """Parse a single statement."""
        handlers = {
            ast.Expr: self._parse_expr_stmt,
            ast.Assign: self._parse_assign,
            ast.AugAssign: self._parse_aug_assign,
            ast.For: self._parse_for,
            ast.While: self._parse_while,
            ast.If: self._parse_if,
            ast.FunctionDef: self._parse_function_def,
            ast.AsyncFunctionDef: self._parse_function_def,
            ast.ClassDef: self._parse_class_def,
            ast.Return: self._parse_return,
            ast.Delete: self._parse_delete,
            ast.Import: self._parse_import,
            ast.ImportFrom: self._parse_import_from,
            ast.Try: self._parse_try,
            ast.With: self._parse_with,
            ast.Raise: self._parse_raise,
            ast.Break: self._parse_break,
            ast.Continue: self._parse_continue,
            ast.Pass: self._parse_pass,
            ast.AnnAssign: self._parse_ann_assign,
        }

        handler = handlers.get(type(stmt))
        if handler:
            return handler(stmt)
        return None

    def _parse_expr_stmt(self, stmt: ast.Expr) -> Node | None:
        return self._parse_expression(stmt.value)

    def _parse_assign(self, stmt: ast.Assign) -> Node:
        """Parse: target = value"""
        target_name = self._get_target_name(stmt.targets[0])

        # Create variable set node
        node = create_node("variable_set", 0, 0)
        if not node:
            node = Node("variable_set", "Set Variable")
            node.add_input("value", PortType.ANY)
            node.add_output("result", PortType.ANY)
        node.data["name"] = target_name
        self.graph.add_node(node)

        # Parse value
        if stmt.value:
            val_node = self._parse_expression(stmt.value)
            if val_node:
                self.graph.add_node(val_node)
                # Connect to value input
                self._connect_nodes(val_node, node, "value", "value")

        return node

    def _parse_aug_assign(self, stmt: ast.AugAssign) -> Node:
        """Parse: target op= value (e.g., x += 1)"""
        target_name = self._get_target_name(stmt.target)
        op_map = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
                  ast.Mod: "%", ast.Pow: "**", ast.FloorDiv: "//",
                  ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^",
                  ast.LShift: "<<", ast.RShift: ">>"}
        op = op_map.get(type(stmt.op), "+")

        # Get current value
        get_node = create_node("variable_get", 0, 0)
        if get_node:
            get_node.data["name"] = target_name
            self.graph.add_node(get_node)

        # Create op node
        op_type = {"+": "math_add", "-": "math_subtract", "*": "math_multiply",
                   "/": "math_divide", "%": "math_mod", "**": "math_power",
                   "//": "math_floor_div", "&": "math_bit_and", "|": "math_bit_or",
                   "^": "math_bit_xor", "<<": "math_lshift", ">>": "math_rshift"}.get(op, "math_add")
        op_node = create_node(op_type, 0, 0)
        if op_node:
            self.graph.add_node(op_node)

            # Connect get to a input
            if get_node:
                self._connect_nodes(get_node, op_node, "value", "a")

            # Parse and connect value
            if stmt.value:
                val_node = self._parse_expression(stmt.value)
                if val_node:
                    self.graph.add_node(val_node)
                    self._connect_nodes(val_node, op_node, "value", "b")

            # Set variable with result
            set_node = create_node("variable_set", 0, 0)
            if set_node:
                set_node.data["name"] = target_name
                self.graph.add_node(set_node)
                self._connect_nodes(op_node, set_node, "result", "value")
                return set_node

        return None

    def _get_target_name(self, target) -> str:
        if isinstance(target, ast.Name):
            return target.id
        elif isinstance(target, ast.Attribute):
            return f"{self._get_target_name(target.value)}.{target.attr}"
        elif isinstance(target, ast.Subscript):
            return f"{self._get_target_name(target.value)}[...]"
        return "_"

    def _parse_for(self, stmt: ast.For) -> Node:
        """Parse: for item in iterable"""
        node = create_node("for", 0, 0)
        if not node:
            node = Node("for", "For Loop")
            node.add_input("exec_in", PortType.FLOW)
            node.add_input("iterable", PortType.LIST)
            node.add_output("body", PortType.FLOW)
            node.add_output("done", PortType.FLOW)
        node.data["loop_var"] = stmt.target.id if isinstance(stmt.target, ast.Name) else "_"
        self.graph.add_node(node)

        if stmt.iter:
            iter_node = self._parse_expression(stmt.iter)
            if iter_node:
                self.graph.add_node(iter_node)
                self._connect_nodes(iter_node, node, "value", "iterable")

        # Parse body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "body")

        return node

    def _parse_while(self, stmt: ast.While) -> Node:
        """Parse: while condition"""
        node = create_node("while", 0, 0)
        if not node:
            node = Node("while", "While Loop")
            node.add_input("exec_in", PortType.FLOW)
            node.add_input("condition", PortType.BOOL)
            node.add_output("body", PortType.FLOW)
            node.add_output("done", PortType.FLOW)
        self.graph.add_node(node)

        if stmt.test:
            cond_node = self._parse_expression(stmt.test)
            if cond_node:
                self.graph.add_node(cond_node)
                self._connect_nodes(cond_node, node, "value", "condition")

        # Parse body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "body")

        return node

    def _parse_if(self, stmt: ast.If) -> Node:
        """Parse: if condition"""
        node = create_node("if", 0, 0)
        if not node:
            node = Node("if", "If")
            node.add_input("exec_in", PortType.FLOW)
            node.add_input("condition", PortType.BOOL)
            node.add_output("then", PortType.FLOW)
            node.add_output("else", PortType.FLOW)
        self.graph.add_node(node)

        if stmt.test:
            cond_node = self._parse_expression(stmt.test)
            if cond_node:
                self.graph.add_node(cond_node)
                self._connect_nodes(cond_node, node, "value", "condition")

        # Parse then body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "then")

        # Parse else body
        if stmt.orelse:
            self._parse_statement_list(stmt.orelse, node, "else")

        return node

    def _parse_function_def(self, stmt) -> Node:
        """Parse: def name(args)"""
        node = create_node("function_define", 0, 0)
        if not node:
            node = Node("function_define", f"Function: {stmt.name}")
            node.add_output("func", PortType.OBJECT)
        node.data["name"] = stmt.name

        # Add argument inputs
        for arg in stmt.args.args:
            node.add_input(arg.arg, PortType.ANY)

        self.graph.add_node(node)

        # Parse body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "body")

        return node

    def _parse_class_def(self, stmt: ast.ClassDef) -> Node:
        """Parse: class name"""
        node = create_node("class_define", 0, 0)
        if not node:
            node = Node("class_define", f"Class: {stmt.name}")
            node.add_output("cls", PortType.OBJECT)
        node.data["name"] = stmt.name
        self.graph.add_node(node)

        # Parse body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "body")

        return node

    def _parse_return(self, stmt: ast.Return) -> Node:
        """Parse: return value"""
        node = create_node("return", 0, 0)
        if not node:
            node = Node("return", "Return")
            node.add_input("value", PortType.ANY)
        self.graph.add_node(node)

        if stmt.value:
            val_node = self._parse_expression(stmt.value)
            if val_node:
                self.graph.add_node(val_node)
                self._connect_nodes(val_node, node, "value", "value")

        return node

    def _parse_delete(self, stmt: ast.Delete) -> Node:
        """Parse: del target"""
        node = create_node("delete", 0, 0)
        if not node:
            node = Node("delete", "Delete")
            node.add_input("exec_in", PortType.FLOW)
            node.add_input("target", PortType.ANY)
            node.add_output("exec_out", PortType.FLOW)
        self.graph.add_node(node)

        if stmt.targets:
            target_node = self._parse_expression(stmt.targets[0])
            if target_node:
                self.graph.add_node(target_node)
                self._connect_nodes(target_node, node, "value", "target")

        return node

    def _parse_import(self, stmt: ast.Import) -> Node:
        """Parse: import names"""
        node = create_node("import", 0, 0)
        if not node:
            node = Node("import", "Import")
            node.add_output("module", PortType.OBJECT)
        node.data["names"] = [alias.name for alias in stmt.names]
        self.graph.add_node(node)
        return node

    def _parse_import_from(self, stmt: ast.ImportFrom) -> Node:
        """Parse: from module import names"""
        node = create_node("import_from", 0, 0)
        if not node:
            node = Node("import_from", f"From {stmt.module or '*'}")
            node.add_output("exports", PortType.OBJECT)
        node.data["module"] = stmt.module
        node.data["names"] = [alias.name for alias in stmt.names]
        self.graph.add_node(node)
        return node

    def _parse_try(self, stmt: ast.Try) -> Node:
        """Parse: try block"""
        node = create_node("try", 0, 0)
        if not node:
            node = Node("try", "Try")
            node.add_input("exec_in", PortType.FLOW)
            node.add_output("body", PortType.FLOW)
            node.add_output("except", PortType.FLOW)
            node.add_output("finally", PortType.FLOW)
            node.add_output("done", PortType.FLOW)
        self.graph.add_node(node)
        
        # Parse body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "body")
            
        # Parse handlers
        for handler in stmt.handlers:
            exc_node = create_node("except", 0, 0)
            if exc_node:
                self.graph.add_node(exc_node)
                exc_node.data["type"] = ast.unparse(handler.type) if handler.type else "Exception"
                # This is a bit simplified, but connects try to except
                self._connect_nodes(node, exc_node, "except", "exec_in")
                if handler.body:
                    self._parse_statement_list(handler.body, exc_node, "handler")

        # Parse finally
        if stmt.finalbody:
            self._parse_statement_list(stmt.finalbody, node, "finally")

        return node

    def _parse_with(self, stmt: ast.With) -> Node:
        """Parse: with context"""
        node = create_node("with", 0, 0)
        if not node:
            node = Node("with", "With")
            node.add_input("exec_in", PortType.FLOW)
            node.add_input("context", PortType.OBJECT)
            node.add_output("body", PortType.FLOW)
            node.add_output("done", PortType.FLOW)
        self.graph.add_node(node)

        if stmt.items:
            item = stmt.items[0]
            if item.context_expr:
                ctx_node = self._parse_expression(item.context_expr)
                if ctx_node:
                    self.graph.add_node(ctx_node)
                    self._connect_nodes(ctx_node, node, "value", "context")

        # Parse body
        if stmt.body:
            self._parse_statement_list(stmt.body, node, "body")

        return node

    def _parse_raise(self, stmt: ast.Raise) -> Node:
        """Parse: raise exc"""
        node = create_node("raise", 0, 0)
        if not node:
            node = Node("raise", "Raise")
            node.add_input("error", PortType.OBJECT)
        self.graph.add_node(node)

        if stmt.exc:
            exc_node = self._parse_expression(stmt.exc)
            if exc_node:
                self.graph.add_node(exc_node)
                self._connect_nodes(exc_node, node, "value", "error")

        return node

    def _parse_break(self, stmt: ast.Break) -> Node:
        node = create_node("break", 0, 0)
        if not node:
            node = Node("break", "Break")
        self.graph.add_node(node)
        return node

    def _parse_continue(self, stmt: ast.Continue) -> Node:
        node = create_node("continue", 0, 0)
        if not node:
            node = Node("continue", "Continue")
        self.graph.add_node(node)
        return node

    def _parse_pass(self, stmt: ast.Pass) -> Node:
        node = Node("pass", "Pass")
        self.graph.add_node(node)
        return node

    def _parse_ann_assign(self, stmt: ast.AnnAssign) -> Node:
        """Parse: target: type = value"""
        target_name = self._get_target_name(stmt.target)
        node = create_node("variable_set", 0, 0)
        if node:
            node.data["name"] = target_name
            node.data["annotation"] = ast.unparse(stmt.annotation) if stmt.annotation else ""
        self.graph.add_node(node)

        if stmt.value:
            val_node = self._parse_expression(stmt.value)
            if val_node:
                self.graph.add_node(val_node)
                self._connect_nodes(val_node, node, "value", "value")

        return node

    def _connect_nodes(self, source: Node, target: Node, source_port: str, target_port: str):
        """Helper to connect two nodes."""
        # Find the output port
        output_port = source_port
        if source_port not in [p.name for p in source.outputs]:
            output_port = source.outputs[0].name if source.outputs else "value"

        # Find the input port
        input_port = target_port
        self._add_edge(source.id, output_port, target.id, input_port)

    # ========== EXPRESSIONS ==========

    def _parse_expression(self, expr: ast.expr) -> Node | None:
        handlers = {
            ast.BinOp: self._parse_binop,
            ast.UnaryOp: self._parse_unaryop,
            ast.BoolOp: self._parse_boolop,
            ast.Compare: self._parse_compare,
            ast.Call: self._parse_call,
            ast.Name: self._parse_name,
            ast.Constant: self._parse_constant,
            ast.List: self._parse_list,
            ast.Tuple: self._parse_tuple,
            ast.Dict: self._parse_dict,
            ast.Set: self._parse_set,
            ast.Attribute: self._parse_attribute,
            ast.Subscript: self._parse_subscript,
            ast.Lambda: self._parse_lambda,
            ast.ListComp: self._parse_list_comp,
            ast.DictComp: self._parse_dict_comp,
            ast.SetComp: self._parse_set_comp,
            ast.GeneratorExp: self._parse_generator,
            ast.IfExp: self._parse_if_exp,
            ast.JoinedStr: self._parse_fstring,
            ast.FormattedValue: self._parse_formatted_value,
            ast.Slice: self._parse_slice,
            ast.Starred: self._parse_starred,
        }

        handler = handlers.get(type(expr))
        if handler:
            return handler(expr)
        return None

    def _parse_binop(self, expr: ast.BinOp) -> Node:
        op_map = {
            ast.Add: "math_add", ast.Sub: "math_subtract", ast.Mult: "math_multiply",
            ast.Div: "math_divide", ast.Mod: "math_mod", ast.Pow: "math_power",
            ast.FloorDiv: "math_floor_div", ast.BitAnd: "math_bit_and",
            ast.BitOr: "math_bit_or", ast.BitXor: "math_bit_xor",
            ast.LShift: "math_lshift", ast.RShift: "math_rshift",
        }
        op_type = op_map.get(type(expr.op), "math_add")
        node = create_node(op_type, 0, 0)

        if not node:
            labels = {"math_add": "a + b", "math_subtract": "a - b", "math_multiply": "a * b",
                      "math_divide": "a / b"}
            node = Node(op_type, labels.get(op_type, "Math"))
            node.add_input("a", PortType.FLOAT)
            node.add_input("b", PortType.FLOAT)
            node.add_output("result", PortType.FLOAT)

        self.graph.add_node(node)

        # Left operand
        if expr.left:
            left_node = self._parse_expression(expr.left)
            if left_node:
                self.graph.add_node(left_node)
                self._connect_nodes(left_node, node, "value", "a")

        # Right operand
        if expr.right:
            right_node = self._parse_expression(expr.right)
            if right_node:
                self.graph.add_node(right_node)
                self._connect_nodes(right_node, node, "value", "b")

        return node

    def _parse_unaryop(self, expr: ast.UnaryOp) -> Node:
        if isinstance(expr.op, ast.USub):
            node = create_node("math_negate", 0, 0)
            if not node:
                node = Node("math_negate", "-a")
                node.add_input("value", PortType.FLOAT)
                node.add_output("result", PortType.FLOAT)
        elif isinstance(expr.op, ast.UAdd):
            node = Node("math_positive", "+a")
            node.add_input("value", PortType.FLOAT)
            node.add_output("result", PortType.FLOAT)
        elif isinstance(expr.op, ast.Not):
            node = create_node("bool_not", 0, 0)
            if not node:
                node = Node("bool_not", "not a")
                node.add_input("value", PortType.BOOL)
                node.add_output("result", PortType.BOOL)
        else:
            node = Node("unary", "Unary")
            node.add_input("value", PortType.ANY)
            node.add_output("result", PortType.ANY)

        self.graph.add_node(node)

        if expr.operand:
            operand = self._parse_expression(expr.operand)
            if operand:
                self.graph.add_node(operand)
                self._connect_nodes(operand, node, "value", "value")

        return node

    def _parse_boolop(self, expr: ast.BoolOp) -> Node:
        if isinstance(expr.op, ast.And):
            node = create_node("bool_and", 0, 0)
            if not node:
                node = Node("bool_and", "a and b")
                node.add_input("a", PortType.BOOL)
                node.add_input("b", PortType.BOOL)
                node.add_output("result", PortType.BOOL)
        else:  # Or
            node = create_node("bool_or", 0, 0)
            if not node:
                node = Node("bool_or", "a or b")
                node.add_input("a", PortType.BOOL)
                node.add_input("b", PortType.BOOL)
                node.add_output("result", PortType.BOOL)

        self.graph.add_node(node)

        if expr.values:
            left = self._parse_expression(expr.values[0])
            if left:
                self.graph.add_node(left)
                self._connect_nodes(left, node, "value", "a")

            if len(expr.values) > 1:
                right = self._parse_expression(expr.values[1])
                if right:
                    self.graph.add_node(right)
                    self._connect_nodes(right, node, "value", "b")

        return node

    def _parse_compare(self, expr: ast.Compare) -> Node:
        ops = {
            ast.Eq: "compare_eq", ast.NotEq: "compare_ne", ast.Lt: "compare_lt",
            ast.LtE: "compare_lte", ast.Gt: "compare_gt", ast.GtE: "compare_gte",
            ast.Is: "compare_is", ast.IsNot: "compare_is_not",
            ast.In: "compare_in", ast.NotIn: "compare_not_in",
        }
        op_type = ops.get(type(expr.ops[0]), "compare_eq")
        node = create_node(op_type, 0, 0)

        if not node:
            labels = {"compare_eq": "a == b", "compare_ne": "a != b", "compare_lt": "a < b",
                      "compare_lte": "a <= b", "compare_gt": "a > b", "compare_gte": "a >= b"}
            node = Node(op_type, labels.get(op_type, "Compare"))
            node.add_input("a", PortType.ANY)
            node.add_input("b", PortType.ANY)
            node.add_output("result", PortType.BOOL)

        self.graph.add_node(node)

        if expr.left:
            left = self._parse_expression(expr.left)
            if left:
                self.graph.add_node(left)
                self._connect_nodes(left, node, "value", "a")

        if expr.comparators:
            right = self._parse_expression(expr.comparators[0])
            if right:
                self.graph.add_node(right)
                self._connect_nodes(right, node, "value", "b")

        return node

    def _parse_call(self, expr: ast.Call) -> Node:
        func_name = "unknown"
        if isinstance(expr.func, ast.Name):
            func_name = expr.func.id
        elif isinstance(expr.func, ast.Attribute):
            func_name = expr.func.attr

        # Try to use specific node type if available (e.g., "print", "input")
        node_type_map = {"int": "to_int", "float": "to_float", "str": "to_str", "bool": "to_bool"}
        node_type = node_type_map.get(func_name, func_name)
        node = create_node(node_type, 0, 0)
        
        if not node:
            node = create_node("function_call", 0, 0)
            if not node:
                node = Node("function_call", f"Call {func_name}")
                node.add_input("func", PortType.OBJECT)
                node.add_output("result", PortType.ANY)
            node.data["name"] = func_name
        
        self.graph.add_node(node)

        # Map arguments to ports
        # For 'print', it uses 'value'
        if func_name == "print" and expr.args:
            arg_node = self._parse_expression(expr.args[0])
            if arg_node:
                self.graph.add_node(arg_node)
                self._connect_nodes(arg_node, node, "value", "value")
        else:
            # Generic function call arguments
            for i, arg in enumerate(expr.args):
                arg_node = self._parse_expression(arg)
                if arg_node:
                    self.graph.add_node(arg_node)
                    port_name = f"arg{i}"
                    if not node.get_input(port_name):
                        node.add_input(port_name, PortType.ANY)
                    self._connect_nodes(arg_node, node, "value", port_name)

        # Handle keyword arguments
        for kw in expr.keywords:
            if kw.arg:
                arg_node = self._parse_expression(kw.value)
                if arg_node:
                    self.graph.add_node(arg_node)
                    if not node.get_input(kw.arg):
                        node.add_input(kw.arg, PortType.ANY)
                    self._connect_nodes(arg_node, node, "value", kw.arg)

        return node

    def _parse_name(self, expr: ast.Name) -> Node:
        node = create_node("variable_get", 0, 0)
        if not node:
            node = Node("variable_get", expr.id)
            node.add_output("value", PortType.ANY)
        node.data["name"] = expr.id
        self.graph.add_node(node)
        return node

    def _parse_constant(self, expr: ast.Constant) -> Node:
        value = expr.value

        if value is None:
            node = create_node("literal_none", 0, 0)
            if not node:
                node = Node("literal_none", "None")
                node.add_output("value", PortType.NONE)
            node.data["value"] = None

        elif isinstance(value, bool):
            node = create_node("literal_bool", 0, 0)
            if not node:
                node = Node("literal_bool", "True" if value else "False")
                node.add_output("value", PortType.BOOL)
            node.data["value"] = value

        elif isinstance(value, int):
            node = create_node("literal_int", 0, 0)
            if not node:
                node = Node("literal_int", str(value))
                node.add_output("value", PortType.INT)
            node.data["value"] = value

        elif isinstance(value, float):
            node = create_node("literal_float", 0, 0)
            if not node:
                node = Node("literal_float", str(value))
                node.add_output("value", PortType.FLOAT)
            node.data["value"] = value

        elif isinstance(value, str):
            node = create_node("literal_str", 0, 0)
            if not node:
                node = Node("literal_str", f'"{value}"')
                node.add_output("value", PortType.STR)
            node.data["value"] = value

        else:
            node = Node("literal", repr(value))
            node.add_output("value", PortType.ANY)
            node.data["value"] = value

        self.graph.add_node(node)
        return node

    def _parse_list(self, expr: ast.List) -> Node:
        node = create_node("literal_list", 0, 0)
        if not node:
            node = Node("literal_list", "List")
            node.add_output("value", PortType.LIST)
        self.graph.add_node(node)

        for i, elt in enumerate(expr.elts):
            # Skip if input already exists (from create_node)
            if not node.get_input(f"element{i}"):
                node.add_input(f"element{i}", PortType.ANY)
            elt_node = self._parse_expression(elt)
            if elt_node:
                self.graph.add_node(elt_node)
                self._connect_nodes(elt_node, node, "value", f"element{i}")

        return node

    def _parse_tuple(self, expr: ast.Tuple) -> Node:
        node = Node("literal_tuple", "Tuple")
        node.add_output("value", PortType.LIST)
        self.graph.add_node(node)

        for i, elt in enumerate(expr.elts):
            node.add_input(f"element{i}", PortType.ANY)
            elt_node = self._parse_expression(elt)
            if elt_node:
                self.graph.add_node(elt_node)
                self._connect_nodes(elt_node, node, "value", f"element{i}")

        return node

    def _parse_dict(self, expr: ast.Dict) -> Node:
        node = create_node("literal_dict", 0, 0)
        if not node:
            node = Node("literal_dict", "Dict")
            node.add_output("value", PortType.DICT)
        self.graph.add_node(node)

        for i, (key, val) in enumerate(zip(expr.keys, expr.values)):
            if not node.get_input(f"key{i}"):
                node.add_input(f"key{i}", PortType.ANY)
            if not node.get_input(f"value{i}"):
                node.add_input(f"value{i}", PortType.ANY)

            if key:
                key_node = self._parse_expression(key)
                if key_node:
                    self.graph.add_node(key_node)
                    self._connect_nodes(key_node, node, "value", f"key{i}")

            val_node = self._parse_expression(val)
            if val_node:
                self.graph.add_node(val_node)
                self._connect_nodes(val_node, node, "value", f"value{i}")

        return node

    def _parse_set(self, expr: ast.Set) -> Node:
        node = Node("literal_set", "Set")
        node.add_output("value", PortType.LIST)
        self.graph.add_node(node)

        for i, elt in enumerate(expr.elts):
            node.add_input(f"element{i}", PortType.ANY)
            elt_node = self._parse_expression(elt)
            if elt_node:
                self.graph.add_node(elt_node)
                self._connect_nodes(elt_node, node, "value", f"element{i}")

        return node

    def _parse_attribute(self, expr: ast.Attribute) -> Node:
        node = create_node("attribute", 0, 0)
        if not node:
            node = Node("attribute", f".{expr.attr}")
            node.add_input("obj", PortType.OBJECT)
            node.add_output("value", PortType.ANY)
        node.data["attr"] = expr.attr
        self.graph.add_node(node)

        if expr.value:
            obj_node = self._parse_expression(expr.value)
            if obj_node:
                self.graph.add_node(obj_node)
                self._connect_nodes(obj_node, node, "value", "obj")

        return node

    def _parse_subscript(self, expr: ast.Subscript) -> Node:
        node = create_node("subscript", 0, 0)
        if not node:
            node = Node("subscript", "[]")
            node.add_input("obj", PortType.ANY)
            node.add_input("index", PortType.ANY)
            node.add_output("value", PortType.ANY)

        self.graph.add_node(node)

        if expr.value:
            obj_node = self._parse_expression(expr.value)
            if obj_node:
                self.graph.add_node(obj_node)
                self._connect_nodes(obj_node, node, "value", "obj")

        if expr.slice:
            slice_node = self._parse_expression(expr.slice)
            if slice_node:
                self.graph.add_node(slice_node)
                self._connect_nodes(slice_node, node, "value", "index")

        return node

    def _parse_lambda(self, expr: ast.Lambda) -> Node:
        node = create_node("lambda", 0, 0)
        if not node:
            node = Node("lambda", "Lambda")
            node.add_output("func", PortType.OBJECT)

        for arg in expr.args.args:
            node.add_input(arg.arg, PortType.ANY)

        self.graph.add_node(node)

        # Lambda body
        body_node = self._parse_expression(expr.body)
        if body_node:
            self.graph.add_node(body_node)
            self._connect_nodes(body_node, node, "value", "element0")

        return node

    def _parse_list_comp(self, expr: ast.ListComp) -> Node:
        node = create_node("list_comp", 0, 0)
        if not node:
            node = Node("list_comp", "List Comp")
            node.add_input("element", PortType.ANY)
            node.add_input("iterable", PortType.LIST)
            node.add_output("result", PortType.LIST)

        # Element expression
        if expr.elt:
            elt_node = self._parse_expression(expr.elt)
            if elt_node:
                self.graph.add_node(elt_node)
                self._connect_nodes(elt_node, node, "value", "element")

        # Iterables
        for i, gen in enumerate(expr.generators):
            if gen.iter:
                iter_node = self._parse_expression(gen.iter)
                if iter_node:
                    self.graph.add_node(iter_node)
                    if not node.get_input("iterable"):
                        node.add_input("iterable", PortType.LIST)
                    self._connect_nodes(iter_node, node, "value", "iterable")

        self.graph.add_node(node)
        return node

    def _parse_dict_comp(self, expr: ast.DictComp) -> Node:
        node = Node("dict_comp", "Dict Comp")
        node.add_input("key", PortType.ANY)
        node.add_input("value", PortType.ANY)
        node.add_input("iterable", PortType.LIST)
        node.add_output("result", PortType.DICT)

        if expr.key:
            key_node = self._parse_expression(expr.key)
            if key_node:
                self.graph.add_node(key_node)
                self._connect_nodes(key_node, node, "value", "key")

        if expr.value:
            val_node = self._parse_expression(expr.value)
            if val_node:
                self.graph.add_node(val_node)
                self._connect_nodes(val_node, node, "value", "value")

        for gen in expr.generators:
            if gen.iter:
                iter_node = self._parse_expression(gen.iter)
                if iter_node:
                    self.graph.add_node(iter_node)
                    self._connect_nodes(iter_node, node, "value", "iterable")

        self.graph.add_node(node)
        return node

    def _parse_set_comp(self, expr: ast.SetComp) -> Node:
        node = Node("set_comp", "Set Comp")
        node.add_input("element", PortType.ANY)
        node.add_input("iterable", PortType.LIST)
        node.add_output("result", PortType.LIST)

        if expr.elt:
            elt_node = self._parse_expression(expr.elt)
            if elt_node:
                self.graph.add_node(elt_node)
                self._connect_nodes(elt_node, node, "value", "element")

        for gen in expr.generators:
            if gen.iter:
                iter_node = self._parse_expression(gen.iter)
                if iter_node:
                    self.graph.add_node(iter_node)
                    self._connect_nodes(iter_node, node, "value", "iterable")

        self.graph.add_node(node)
        return node

    def _parse_generator(self, expr: ast.GeneratorExp) -> Node:
        node = Node("generator", "Generator")
        node.add_input("element", PortType.ANY)
        node.add_input("iterable", PortType.LIST)
        node.add_output("result", PortType.LIST)

        if expr.elt:
            elt_node = self._parse_expression(expr.elt)
            if elt_node:
                self.graph.add_node(elt_node)
                self._connect_nodes(elt_node, node, "value", "element")

        for gen in expr.generators:
            if gen.iter:
                iter_node = self._parse_expression(gen.iter)
                if iter_node:
                    self.graph.add_node(iter_node)
                    self._connect_nodes(iter_node, node, "value", "iterable")

        self.graph.add_node(node)
        return node

    def _parse_if_exp(self, expr: ast.IfExp) -> Node:
        node = Node("if_exp", "If Expr")
        node.add_input("condition", PortType.BOOL)
        node.add_input("true_value", PortType.ANY)
        node.add_input("false_value", PortType.ANY)
        node.add_output("result", PortType.ANY)
        self.graph.add_node(node)

        if expr.test:
            cond_node = self._parse_expression(expr.test)
            if cond_node:
                self.graph.add_node(cond_node)
                self._connect_nodes(cond_node, node, "value", "condition")

        if expr.body:
            body_node = self._parse_expression(expr.body)
            if body_node:
                self.graph.add_node(body_node)
                self._connect_nodes(body_node, node, "value", "true_value")

        if expr.orelse:
            else_node = self._parse_expression(expr.orelse)
            if else_node:
                self.graph.add_node(else_node)
                self._connect_nodes(else_node, node, "value", "false_value")

        return node

    def _parse_fstring(self, expr: ast.JoinedStr) -> Node:
        node = Node("fstring", "f-string")
        node.add_output("value", PortType.STR)
        self.graph.add_node(node)

        for value in expr.values:
            if isinstance(value, ast.FormattedValue):
                inp = f"input{len([i for i in node.inputs if i.name.startswith('input')])}"
                node.add_input(inp, PortType.ANY)
                val_node = self._parse_formatted_value(value)
                if val_node:
                    self.graph.add_node(val_node)
                    self._connect_nodes(val_node, node, "value", inp)
            else:
                pass  # Handle literal string parts

        return node

    def _parse_formatted_value(self, expr: ast.FormattedValue) -> Node:
        return self._parse_expression(expr.value)

    def _parse_slice(self, expr: ast.Slice) -> Node:
        node = create_node("slice", 0, 0)
        if not node:
            node = Node("slice", "Slice")
            node.add_input("obj", PortType.ANY)
            node.add_input("start", PortType.INT)
            node.add_input("stop", PortType.INT)
            node.add_output("result", PortType.LIST)
        self.graph.add_node(node)
        return node

    def _parse_starred(self, expr: ast.Starred) -> Node:
        node = Node("starred", "*expr")
        node.add_input("value", PortType.ANY)
        node.add_output("result", PortType.ANY)
        self.graph.add_node(node)

        if expr.value:
            val_node = self._parse_expression(expr.value)
            if val_node:
                self.graph.add_node(val_node)
                self._connect_nodes(val_node, node, "value", "value")

        return node


def parse(source: str) -> Graph:
    """Convenience function to parse Python source into a graph."""
    parser = ASTParser()
    return parser.parse(source)