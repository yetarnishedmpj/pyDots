"""pyDOT - Visual Python Scripting Language

A cross-platform visual node-based scripting language where Python code is
represented as connected nodes in a graph.
"""

__version__ = "0.1.0"

# Expose core functionality for library usage
from .core.parser import parse
from .core.codegen import generate
from .core.executor import execute
from .core.graph import Graph, Node, Edge, PortType
