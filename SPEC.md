# pyDOT - Visual Python Scripting Language

A cross-platform visual node-based scripting language where Python code is represented as connected nodes in a graph.

## Architecture

- **Language Core**: Python AST-based parser that converts Python source to a node graph
- **Node Graph Engine**: Custom graph data structure with nodes, ports, and connections
- **Visual Editor**: PyQt6/PySide6 node editor with drag-and-drop node creation
- **Code Generator**: Reverse-transforms node graph back to executable Python

## Tech Stack

- **Language**: Python 3.10+
- **GUI Framework**: PyQt6 or PySide6
- **Parser**: Python `ast` module

## Project Structure

```
pyDOT/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── parser.py        # Python AST → Node Graph
│   │   ├── graph.py         # Node graph data structure
│   │   ├── codegen.py       # Node Graph → Python code
│   │   └── executor.py      # Execute node graphs
│   ├── editor/
│   │   ├── __init__.py
│   │   ├── main_window.py   # PyQt main window
│   │   ├── node_scene.py    # QGraphicsScene for nodes
│   │   ├── node_item.py     # QGraphicsItem for nodes
│   │   └── connection.py   # Wire connections between nodes
│   └── ui/
│       ├── __init__.py
│       └── node_palette.py  # Node creation sidebar
└── main.py                  # Entry point
```

## Phase 1: Core Infrastructure

1. Create project scaffold with pyproject.toml
2. Implement `Graph` data structure (nodes, ports, edges)
3. Build AST parser converting Python → node graph
4. Build code generator (node graph → Python)
5. Basic PyQt editor shell with node scene

## Phase 2: Visual Editor

1. Node palette with drag-and-drop
2. Node rendering with ports
3. Wire connections with Bezier curves
4. Pan/zoom scene navigation
5. Node selection and deletion

## Phase 3: Python Coverage

Full Python feature support:
- Variables (Assign node)
- Expressions (Math, Compare, Bool ops)
- Control flow (If/Else, For, While)
- Functions (Call, Define)
- Classes (Class def, Methods)
- Imports and modules
- Try/Except, With, Lambda

## Key Node Types

| Category | Nodes |
|----------|-------|
| Variables | Variable Get, Variable Set |
| Math | Add, Subtract, Multiply, Divide, Mod |
| Compare | ==, !=, <, >, <=, >= |
| Bool | And, Or, Not |
| Control | If, For, While, Function Define |
| Flow | Break, Continue, Return |
| IO | Print, Input |
| Types | Int, Float, Str, Bool, List, Dict |