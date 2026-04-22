"""pyDOT - Visual Python Scripting Language.

Entry point and version info.
"""

import sys

# Version info
__version__ = "0.1.0"
__author__ = "pyDOT Contributors"

# Available modules
from .core import graph, parser, codegen, executor


def run_editor():
    """Launch the visual node editor."""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            print("ERROR: PyQt6 or PySide6 is required for the visual editor.")
            print("Install with: pip install PySide6")
            print()
            print("You can still use pyDOT as a library:")
            print("  from pyDOT.core import parser, codegen")
            print("  graph = parser.parse('x = 5')")
            print("  code = codegen.generate(graph)")
            sys.exit(1)

    from .editor.main_window import main
    main()


if __name__ == "__main__":
    run_editor()