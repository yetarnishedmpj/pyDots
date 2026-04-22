# pyDOT - Visual Python Scripting Language

pyDOT is a powerful, cross-platform visual node-based editor that translates graphical logic into executable Python code in real-time. Designed for both beginners learning logic and experts prototyping complex scripts, pyDOT offers a seamless transition between visual flow and professional code.

## 🚀 Features

- **Visual Logic Design**: Drag-and-drop nodes to create variables, loops, conditionals, and classes.
- **Real-time Codegen**: Watch your Python code update instantly as you move nodes and connect wires.
- **Interactive Execution**: Run your visual scripts directly within the editor. Integrated console captures `print()` output and supports interactive `input()` via GUI popups.
- **Full Python Coverage**: Support for advanced features like `try/except`, `with` blocks, `lambda` functions, list comprehensions, and imports.
- **Professional Editor Tools**:
  - **Undo/Redo**: Full history support for all actions.
  - **Searchable Palette**: Quickly find nodes across multiple categories.
  - **Property Editor**: Precision control over variable names and literal values.
  - **Infinite Canvas**: Zoom and pan through large, complex logic graphs.
  - **Copy/Paste**: Easily duplicate logic branches.

## 🛠️ Installation

### Prerequisites
- Python 3.10 or higher
- PyQt6

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pyDOT.git
   cd pyDOT
   ```
2. Install dependencies:
   ```bash
   pip install PyQt6
   ```

## 📖 How to Use

1. **Run the Editor**:
   ```bash
   python -m src.main
   ```
2. **Build your Graph**:
   - Drag nodes from the **Node Palette** on the left.
   - Connect **Orange Ports** to define the order of execution (**FLOW**).
   - Connect **Colored Ports** to pass data between operations.
3. **Configure Nodes**: Click a node to edit its name or value in the **Node Properties** panel on the top-right.
4. **Execute**: Click the green **RUN** button to see your script in action!

## 🏗️ Architecture

- **Core**: AST-based parser and code generator using standard Python libraries.
- **UI**: High-performance hardware-accelerated graphics using PyQt6's GraphicsView framework.
- **Persistence**: Save and load your graphs using the native `.pydot` JSON format.

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests to expand the node library or improve the editor experience.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
