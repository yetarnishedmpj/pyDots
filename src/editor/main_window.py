"""pyDOT - Visual Python Editor

Main window and application setup.
"""

import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QSplitter, QMenuBar, QMenu, QFileDialog,
    QMessageBox, QScrollArea, QLabel, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsWidget, QGraphicsLayoutItem, QGraphicsLinearLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QInputDialog
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, pyqtSlot, QMimeData
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QAction, QDrag, QFont, QPainterPath
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from ..core.graph import Graph, Node, Edge, PortType, NODE_DEFINITIONS, create_node, PORT_COLORS
from ..core.parser import parse as parse_graph
from ..core.codegen import generate as generate_code


class NodeGraphicsItem(QGraphicsItem):
    """Visual representation of a node in the graph."""

    def __init__(self, node: Node, editor: 'NodeEditor'):
        super().__init__()
        self.node = node
        self.editor = editor
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(node.x, node.y)

        # Node dimensions
        self.width = max(node.width, 140)
        self.height = max(node.height, 60)

        # Colors
        defn = NODE_DEFINITIONS.get(node.node_type, {})
        self.node_color = QColor(defn.get("color", "#555"))
        self.bg_color = QColor("#2a2a3a")
        self.border_color = QColor("#4a4a5a")
        self.selected_color = QColor("#6a6a8a")

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget=None):
        # Draw background
        bg = self.bg_color if not self.isSelected() else self.selected_color
        painter.fillRect(self.boundingRect(), bg)

        # Draw border
        pen = QPen(self.border_color if not self.isSelected() else self.selected_color, 2)
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())

        # Draw header
        header_rect = QRectF(0, 0, self.width, 24)
        painter.fillRect(header_rect, self.node_color)

        # Draw label
        pen = QPen(QColor("#fff"))
        painter.setPen(pen)
        font = QFont("Arial", 9)
        painter.setFont(font)
        painter.drawText(QPointF(8, 16), self.node.label)

        # Draw value if it's a literal
        if self.node.data.get("value") is not None:
            val = str(self.node.data["value"])
            if len(val) > 10:
                val = val[:10] + "..."
            painter.drawText(QPointF(self.width - 50, 16), val)

        # Draw ports
        self._draw_ports(painter)

    def _draw_ports(self, painter: QPainter):
        """Draw input and output ports."""
        # Input ports (left side)
        input_count = len(self.node.inputs)
        if input_count > 0:
            spacing = self.height / (input_count + 1)
            for i, port in enumerate(self.node.inputs):
                y = spacing * (i + 1)
                self._draw_port(painter, 0, y, port, is_input=True)

        # Output ports (right side)
        output_count = len(self.node.outputs)
        if output_count > 0:
            spacing = self.height / (output_count + 1)
            for i, port in enumerate(self.node.outputs):
                y = spacing * (i + 1)
                self._draw_port(painter, self.width, y, port, is_input=False)

    def _draw_port(self, painter: QPainter, x: float, y: float, port: 'Port', is_input: bool):
        """Draw a single port circle."""
        color_str = PORT_COLORS.get(port.port_type, "#aaa")
        color = QColor(color_str)
        
        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(color.darker(150)))
        painter.drawEllipse(int(x - 6), int(y - 6), 12, 12)

        # Draw port label
        pen = QPen(QColor("#aaa"))
        painter.setPen(pen)
        font = QFont("Arial", 7)
        painter.setFont(font)
        label_x = x + 10 if is_input else x - 40
        painter.drawText(int(label_x), int(y + 4), port.name)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update node data
            self.node.x = self.pos().x()
            self.node.y = self.pos().y()

            # Update connections
            if hasattr(self.editor.scene, "connection_items"):
                for conn in self.editor.scene.connection_items:
                    if conn.source_node.id == self.node.id or conn.target_node.id == self.node.id:
                        conn.prepareGeometryChange()
                        conn.update()

        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.editor.on_node_moved(self)


class ConnectionGraphicsItem(QGraphicsItem):
    """Visual representation of a connection between nodes."""

    def __init__(self, edge: Edge, source_node: Node, target_node: Node):
        super().__init__()
        self.edge = edge
        self.source_node = source_node
        self.target_node = target_node
        self.setZValue(-1)  # Draw behind nodes

    def _get_source_pos(self) -> QPointF:
        idx = next((i for i, p in enumerate(self.source_node.outputs) if p.name == self.edge.source_port), 0)
        px, py = self.source_node.output_rect(idx)
        return QPointF(px, py)

    def _get_target_pos(self) -> QPointF:
        idx = next((i for i, p in enumerate(self.target_node.inputs) if p.name == self.edge.target_port), 0)
        px, py = self.target_node.input_rect(idx)
        return QPointF(px, py)

    def boundingRect(self) -> QRectF:
        s = self._get_source_pos()
        t = self._get_target_pos()
        return QRectF(
            min(s.x(), t.x()) - 10,
            min(s.y(), t.y()) - 10,
            abs(t.x() - s.x()) + 20,
            abs(t.y() - s.y()) + 20
        )

    def paint(self, painter: QPainter, option, widget=None):
        pen = QPen(QColor("#68a"), 2)
        painter.setPen(pen)

        source_pos = self._get_source_pos()
        target_pos = self._get_target_pos()

        # Draw bezier curve
        dx = target_pos.x() - source_pos.x()
        control_offset = max(abs(dx) * 0.5, 50)

        path = QPainterPath(source_pos)
        path.cubicTo(
            QPointF(source_pos.x() + control_offset, source_pos.y()),
            QPointF(target_pos.x() - control_offset, target_pos.y()),
            target_pos
        )
        painter.drawPath(path)


class NodeScene(QGraphicsScene):
    """Graphics scene containing nodes and connections."""

    node_double_clicked = pyqtSignal(str)  # node_id

    def __init__(self, editor: 'NodeEditor'):
        super().__init__()
        self.editor = editor
        self.setBackgroundBrush(QBrush(QColor("#1a1a2e")))
        self.setSceneRect(-5000, -5000, 10000, 10000)

        self.node_items: dict[str, NodeGraphicsItem] = {}
        self.connection_items: list[ConnectionGraphicsItem] = []

        # Dragging state
        self.dragging_connection = False
        self.drag_source_port = None
        self.drag_source_node = None
        self.drag_line = None

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw a grid background."""
        super().drawBackground(painter, rect)

        # Draw grid
        left = int(rect.left())
        top = int(rect.top())
        right = int(rect.right())
        bottom = int(rect.bottom())

        grid_size = 50
        
        # Pen for small grid
        pen_light = QPen(QColor("#252538"), 0.5)
        # Pen for large grid
        pen_dark = QPen(QColor("#2a2a40"), 1.0)

        # Draw vertical lines
        for x in range(left - (left % grid_size), right, grid_size):
            painter.setPen(pen_dark if x % (grid_size * 2) == 0 else pen_light)
            painter.drawLine(x, top, x, bottom)

        # Draw horizontal lines
        for y in range(top - (top % grid_size), bottom, grid_size):
            painter.setPen(pen_dark if y % (grid_size * 2) == 0 else pen_light)
            painter.drawLine(left, y, right, y)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            node_type = event.mimeData().text()
            pos = event.scenePos()
            self.editor.create_node_at(node_type, pos.x(), pos.y())
            event.acceptProposedAction()

    def add_node(self, node: Node) -> NodeGraphicsItem:
        """Add a node to the scene."""
        item = NodeGraphicsItem(node, self.editor)
        self.node_items[node.id] = item
        super().addItem(item)
        return item

    def remove_node(self, node_id: str):
        """Remove a node from the scene."""
        if node_id in self.node_items:
            item = self.node_items[node_id]
            self.removeItem(item)
            del self.node_items[node_id]

    def clear(self):
        """Clear all nodes and connections."""
        super().clear()
        self.node_items.clear()
        self.connection_items.clear()

    def get_node_at(self, x: float, y: float) -> Node | None:
        """Find node at given position."""
        items = self.items(x, y)
        for item in items:
            if isinstance(item, NodeGraphicsItem):
                return item.node
        return None

    def mousePressEvent(self, event):
        pos = event.scenePos()
        # Check if clicked on a port
        for node in self.editor.graph.nodes.values():
            # Check input ports
            for i, port in enumerate(node.inputs):
                px, py = node.input_rect(i)
                if (pos.x() - px)**2 + (pos.y() - py)**2 < 144:  # 12 pixel radius
                    self._start_connection_drag(node, port, px, py)
                    return

            # Check output ports
            for i, port in enumerate(node.outputs):
                px, py = node.output_rect(i)
                if (pos.x() - px)**2 + (pos.y() - py)**2 < 144:
                    self._start_connection_drag(node, port, px, py)
                    return

        super().mousePressEvent(event)

    def _start_connection_drag(self, node, port, x, y):
        self.dragging_connection = True
        self.drag_source_node = node
        self.drag_source_port = port
        self.drag_line = self.addLine(x, y, x, y, QPen(QColor("#68a"), 2))

    def mouseMoveEvent(self, event):
        if self.dragging_connection and self.drag_line:
            line = self.drag_line.line()
            line.setP2(event.scenePos())
            self.drag_line.setLine(line)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging_connection:
            pos = event.scenePos()
            
            # Clean up the drag line FIRST before rebuild_scene clears everything
            if self.drag_line:
                self.removeItem(self.drag_line)
                self.drag_line = None

            target_node = None
            target_port = None

            # Find target port
            for node in self.editor.graph.nodes.values():
                for i, port in enumerate(node.inputs):
                    px, py = node.input_rect(i)
                    if (pos.x() - px)**2 + (pos.y() - py)**2 < 144:
                        target_node = node
                        target_port = port
                        break
                if target_port: break
                for i, port in enumerate(node.outputs):
                    px, py = node.output_rect(i)
                    if (pos.x() - px)**2 + (pos.y() - py)**2 < 144:
                        target_node = node
                        target_port = port
                        break
                if target_port: break

            if target_port and target_node and target_port != self.drag_source_port:
                s_port = self.drag_source_port
                t_port = target_port
                s_node = self.drag_source_node
                t_node = target_node

                if s_port.is_input != t_port.is_input:
                    if s_port.is_input:
                        s_port, t_port = t_port, s_port
                        s_node, t_node = t_node, s_node
                    
                    edge = Edge(s_node.id, s_port.name, t_node.id, t_port.name)
                    self.editor.save_state()
                    if self.editor.graph.add_edge(edge):
                        self.editor.rebuild_scene()
                        self.editor.update_code()

            self.dragging_connection = False
            self.drag_source_node = None
            self.drag_source_port = None
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.selectedItems():
                if isinstance(item, NodeGraphicsItem):
                    self.editor.graph.remove_node(item.node.id)
            self.editor.rebuild_scene()
            self.editor.update_code()
        else:
            super().keyPressEvent(event)


class NodeGraphicsView(QGraphicsView):
    """View for the node scene with pan and zoom."""

    def __init__(self, scene: NodeScene):
        super().__init__(scene)
        self.scene = scene
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Pan state
        self.panning = False
        self.last_pan = QPointF()

    def wheelEvent(self, event):
        """Handle zoom with mouse wheel."""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Save the scene pos
        old_pos = self.mapToScene(event.position().toPoint())

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        # Get the new position
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to keep mouse over the same point
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = True
            self.last_pan = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.panning:
            delta = event.position() - self.last_pan
            self.last_pan = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Delete selected nodes
            if self.scene.selectedItems():
                self.scene.editor.save_state()
                for item in self.scene.selectedItems():
                    if isinstance(item, NodeGraphicsItem):
                        self.scene.editor.graph.remove_node(item.node.id)
                self.scene.editor.rebuild_scene()
                self.scene.editor.update_code()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.scene.editor.undo()
            elif event.key() == Qt.Key.Key_Y:
                self.scene.editor.redo()
            elif event.key() == Qt.Key.Key_C:
                self.scene.editor.copy_selection()
            elif event.key() == Qt.Key.Key_V:
                self.scene.editor.paste_selection()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Right-click menu for the scene."""
        menu = QMenu(self)
        
        # Check if clicked on a node
        item = self.itemAt(event.pos())
        if isinstance(item, NodeGraphicsItem):
            delete_action = menu.addAction("Delete Node")
            delete_action.triggered.connect(lambda: self._delete_node(item))
        else:
            # Clicked on empty space - show quick add menu
            add_menu = menu.addMenu("Add Node")
            
            # Categorize nodes
            categories = {}
            for node_type, defn in NODE_DEFINITIONS.items():
                cat = defn.get("category", "Other")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append((node_type, defn.get("label", node_type)))
            
            scene_pos = self.mapToScene(event.pos())
            for cat, nodes in sorted(categories.items()):
                cat_menu = add_menu.addMenu(cat)
                for node_type, label in sorted(nodes, key=lambda x: x[1]):
                    action = cat_menu.addAction(label)
                    action.triggered.connect(lambda checked, nt=node_type: 
                        self.scene.editor.create_node_at(nt, scene_pos.x(), scene_pos.y()))
        
        menu.exec(event.globalPos())

    def _delete_node(self, item: NodeGraphicsItem):
        self.scene.editor.graph.remove_node(item.node.id)
        self.scene.editor.rebuild_scene()
        self.scene.editor.update_code()


class NodePaletteButton(QPushButton):
    """Button in the palette that supports dragging."""

    def __init__(self, node_type: str, label: str, parent=None):
        super().__init__(f"    {label}", parent)
        self.node_type = node_type
        self.setToolTip(f"Drag to add {label} node")
        self.setStyleSheet("""
            QPushButton {
                background: #2a2a3a;
                color: #ccc;
                border: none;
                padding: 6px 10px;
                text-align: left;
            }
            QPushButton:hover {
                background: #3a3a5a;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
                return

            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.node_type)
            drag.setMimeData(mime_data)

            # Create a ghost of the button for the drag icon
            drag.setPixmap(self.grab())
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.CopyAction)


class NodePalette(QFrame):
    """Sidebar with available node types."""

    node_selected = pyqtSignal(str)  # node_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = []
        self.setup_ui()

    def setup_ui(self):
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)
        self.setStyleSheet("background: #252535; border-right: 1px solid #3a3a4a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("Node Palette")
        title.setStyleSheet("font-weight: bold; color: #aaa; padding: 5px;")
        layout.addWidget(title)

        # Search bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search nodes...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background: #1a1a2a;
                color: #fff;
                border: 1px solid #3a3a4a;
                border-radius: 3px;
                padding: 4px;
                margin: 5px;
            }
        """)
        self.search_edit.textChanged.connect(self.filter_nodes)
        layout.addWidget(self.search_edit)

        # Scroll area for categories
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        self.container_layout = QVBoxLayout(container)

        # Categorize nodes
        categories = {}
        for node_type, defn in NODE_DEFINITIONS.items():
            cat = defn.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((node_type, defn.get("label", node_type)))

        for cat, nodes in sorted(categories.items()):
            # Category header
            cat_label = QPushButton(f"  {cat}")
            cat_label.setStyleSheet("""
                QPushButton {
                    background: #1a1a2a;
                    color: #888;
                    border: none;
                    padding: 8px 5px;
                    text-align: left;
                    font-weight: bold;
                }
            """)
            cat_label.setEnabled(False)
            self.container_layout.addWidget(cat_label)

            # Node buttons
            for node_type, label in sorted(nodes, key=lambda x: x[1]):
                btn = NodePaletteButton(node_type, label)
                btn.clicked.connect(lambda checked, nt=node_type: self.node_selected.emit(nt))
                self.container_layout.addWidget(btn)
                self.buttons.append((btn, cat_label, label.lower(), cat.lower()))

        self.container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def filter_nodes(self, text: str):
        """Filter visible nodes by text."""
        text = text.lower()
        active_categories = set()
        
        # First pass: hide/show buttons and find which categories have matches
        for btn, cat_label, label_lower, cat_lower in self.buttons:
            match = text in label_lower or text in cat_lower
            btn.setVisible(match)
            if match:
                active_categories.add(cat_label)
        
        # Second pass: hide/show category headers
        for _, cat_label, _, _ in self.buttons:
            cat_label.setVisible(cat_label in active_categories)


class PropertyEditor(QWidget):
    """Panel for editing selected node properties."""

    property_changed = pyqtSignal()

    def __init__(self, editor: 'NodeEditor', parent=None):
        super().__init__(parent)
        self.editor = editor
        self.node: Node | None = None
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: #1e1e2e; border-left: 1px solid #3a3a4a;")
        self.setMinimumHeight(200)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Node Properties")
        header.setStyleSheet("color: #aaa; font-weight: bold; padding-bottom: 5px;")
        self.layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none;")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.addStretch()
        
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)

    def set_node(self, node: Node | None):
        self.node = node
        # Clear existing widgets
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not node:
            label = QLabel("No node selected")
            label.setStyleSheet("color: #666; font-style: italic;")
            self.container_layout.insertWidget(0, label)
            return

        # Add name/type label
        type_label = QLabel(f"Type: {node.node_type}")
        type_label.setStyleSheet("color: #888; font-size: 10px;")
        self.container_layout.insertWidget(0, type_label)

        # Dynamic fields based on node type
        if "name" in node.data or node.node_type in ("variable_set", "variable_get", "function_define", "function_call"):
            self._add_line_edit("Name", "name")
        
        if "value" in node.data or node.node_type.startswith("literal_"):
            val = node.data.get("value", "")
            if node.node_type == "literal_int":
                self._add_spin_box("Value", "value", int)
            elif node.node_type == "literal_float":
                self._add_double_spin_box("Value", "value")
            elif node.node_type == "literal_bool":
                self._add_checkbox("Value", "value")
            else:
                self._add_line_edit("Value", "value")

    def _add_line_edit(self, label: str, key: str):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        edit = QLineEdit(str(self.node.data.get(key, "")))
        edit.setStyleSheet("background: #2a2a3a; color: #fff; border: 1px solid #444;")
        edit.textChanged.connect(lambda text: self._update_data(key, text))
        layout.addWidget(edit)
        self.container_layout.insertLayout(self.container_layout.count() - 1, layout)

    def _add_spin_box(self, label: str, key: str, type_cast):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        spin = QSpinBox()
        spin.setRange(-999999, 999999)
        spin.setValue(int(self.node.data.get(key, 0)))
        spin.valueChanged.connect(lambda val: self._update_data(key, val))
        layout.addWidget(spin)
        self.container_layout.insertLayout(self.container_layout.count() - 1, layout)

    def _add_double_spin_box(self, label: str, key: str):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        spin = QDoubleSpinBox()
        spin.setRange(-999999.0, 999999.0)
        spin.setValue(float(self.node.data.get(key, 0.0)))
        spin.valueChanged.connect(lambda val: self._update_data(key, val))
        layout.addWidget(spin)
        self.container_layout.insertLayout(self.container_layout.count() - 1, layout)

    def _add_checkbox(self, label: str, key: str):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        cb = QCheckBox()
        cb.setChecked(bool(self.node.data.get(key, False)))
        cb.toggled.connect(lambda val: self._update_data(key, val))
        layout.addWidget(cb)
        self.container_layout.insertLayout(self.container_layout.count() - 1, layout)

    def _update_data(self, key: str, value: Any):
        if self.node:
            self.editor.save_state()
            
            old_value = self.node.data.get(key)
            self.node.data[key] = value
            
            # Sync variable names if changed
            if key == "name" and self.node.node_type in ("variable_set", "variable_get"):
                self.editor.sync_variable_names(old_value, value)

            # Update label for literals
            if self.node.node_type == "literal_int":
                self.node.label = str(value)
            elif self.node.node_type == "literal_float":
                self.node.label = str(value)
            elif self.node.node_type == "literal_str":
                self.node.label = f'"{value}"'
            elif self.node.node_type == "variable_get" or self.node.node_type == "variable_set":
                if key == "name":
                    self.node.label = f"{'Set' if 'set' in self.node.node_type else 'Get'}: {value}"
            
            self.property_changed.emit()


class CodePanel(QWidget):
    """Panel showing generated Python code."""

    code_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: #1e1e2e; border-left: 1px solid #3a3a4a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QLabel("Python Code")
        header.setStyleSheet("""
            background: #252535;
            color: #aaa;
            padding: 8px 10px;
            font-weight: bold;
        """)
        layout.addWidget(header)

        # Code text edit
        self.code_edit = QTextEdit()
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background: #1e1e2e;
                color: #b0b0c0;
                border: none;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)
        self.code_edit.setReadOnly(False)
        self.code_edit.textChanged.connect(lambda: self.code_changed.emit(self.code_edit.toPlainText()))
        layout.addWidget(self.code_edit)

    def set_code(self, code: str):
        self.code_edit.setPlainText(code)

    def get_code(self) -> str:
        return self.code_edit.toPlainText()


class NodeEditor(QWidget):
    """Main node editor widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graph = Graph()
        self.current_file = None
        
        # Undo/Redo stack
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self._block_undo = False

        self.setup_ui()

    def save_state(self):
        """Save current graph state to undo stack."""
        if self._block_undo:
            return
        state = self.graph.to_dict()
        # Only save if different from last state
        if not self.undo_stack or self.undo_stack[-1] != state:
            self.undo_stack.append(state)
            self.redo_stack.clear()
            # Limit stack size
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return
        
        # Current state goes to redo
        self.redo_stack.append(self.graph.to_dict())
        
        # Restore state
        state = self.undo_stack.pop()
        self._restore_state(state)

    def redo(self):
        if not self.redo_stack:
            return
            
        # Current state goes to undo
        self.undo_stack.append(self.graph.to_dict())
        
        # Restore state
        state = self.redo_stack.pop()
        self._restore_state(state)

    def _restore_state(self, state: dict):
        self._block_undo = True
        try:
            self.graph = Graph.from_dict(state)
            self.rebuild_scene()
            self.update_code()
        finally:
            self._block_undo = False

    def copy_selection(self):
        """Copy selected nodes to internal clipboard."""
        selected = self.scene.selectedItems()
        nodes_to_copy = []
        for item in selected:
            if isinstance(item, NodeGraphicsItem):
                # We only copy the node data, not edges for now (simpler)
                n = item.node
                nodes_to_copy.append({
                    "node_type": n.node_type,
                    "label": n.label,
                    "x": n.x,
                    "y": n.y,
                    "data": n.data.copy()
                })
        
        if nodes_to_copy:
            self._clipboard = nodes_to_copy

    def paste_selection(self):
        """Paste nodes from internal clipboard."""
        if not hasattr(self, "_clipboard") or not self._clipboard:
            return
        
        self.save_state()
        self.scene.clearSelection()
        
        new_items = []
        for n_data in self._clipboard:
            node = create_node(n_data["node_type"], n_data["x"] + 20, n_data["y"] + 20)
            if not node:
                node = Node(n_data["node_type"], n_data["label"], n_data["x"] + 20, n_data["y"] + 20)
            node.data = n_data["data"].copy()
            
            self.graph.add_node(node)
            item = self.scene.add_node(node)
            item.setSelected(True)
            new_items.append(item)
            
        self.update_code()

    def sync_variable_names(self, old_name: str, new_name: str):
        """Update all nodes using old_name to use new_name."""
        if not old_name or not new_name or old_name == new_name:
            return
            
        for node in self.graph.nodes.values():
            if node.node_type in ("variable_get", "variable_set"):
                if node.data.get("name") == old_name:
                    node.data["name"] = new_name
                    # Update label
                    node.label = f"{'Set' if 'set' in node.node_type else 'Get'}: {new_name}"
        
        self.scene.update()

    def setup_ui(self):
        self.setStyleSheet("background: #1a1a2e;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Node palette (left sidebar)
        self.palette = NodePalette()
        self.palette.node_selected.connect(self.create_node_from_palette)
        layout.addWidget(self.palette)

        # Middle section (Scene + Console)
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        # Node scene view (center)
        self.scene = NodeScene(self)
        self.scene.selectionChanged.connect(self._on_selection_changed)
        self.view = NodeGraphicsView(self.scene)
        middle_layout.addWidget(self.view, stretch=3)

        # Console panel (bottom)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        self.console.setPlaceholderText("Console Output...")
        self.console.setStyleSheet("""
            QTextEdit {
                background: #0a0a1a;
                color: #0f0;
                border-top: 1px solid #3a3a4a;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 5px;
            }
        """)
        middle_layout.addWidget(self.console, stretch=1)
        
        layout.addWidget(middle_widget, stretch=1)

        # Right section (Code + Actions)
        right_widget = QWidget()
        right_widget.setMaximumWidth(350)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Property editor
        self.prop_editor = PropertyEditor(self)
        self.prop_editor.property_changed.connect(self.update_code)
        right_layout.addWidget(self.prop_editor, stretch=1)

        # Code panel
        self.code_panel = CodePanel()
        right_layout.addWidget(self.code_panel, stretch=2)

        # Buttons at bottom of code panel
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 10, 10, 10)
        
        self.parse_btn = QPushButton("Parse Python → Graph")
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background: #35a;
                color: white;
                border: none;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #46b;
            }
        """)
        self.parse_btn.clicked.connect(self.parse_code)
        btn_layout.addWidget(self.parse_btn)

        self.run_btn = QPushButton("RUN")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: #3a5;
                color: white;
                border: none;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #4b6;
            }
        """)
        self.run_btn.clicked.connect(self.run_graph)
        btn_layout.addWidget(self.run_btn)

        right_layout.addLayout(btn_layout)
        layout.addWidget(right_widget)

    def create_node_from_palette(self, node_type: str):
        """Create a new node from the palette at a default offset position."""
        offset = len(self.graph.nodes) * 20
        self.create_node_at(node_type, 200 + offset, 200 + offset)

    def create_node_at(self, node_type: str, x: float, y: float):
        """Create a new node at the specified position."""
        self.save_state()
        node = create_node(node_type, x, y)
        if node:
            self.graph.add_node(node)
            self.scene.add_node(node)
            self.update_code()

    def on_node_moved(self, item: NodeGraphicsItem):
        """Handle node moved event."""
        self.update_code()

    def _on_selection_changed(self):
        """Update property editor when selection changes."""
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], NodeGraphicsItem):
            self.prop_editor.set_node(selected[0].node)
        else:
            self.prop_editor.set_node(None)

    def parse_code(self):
        """Parse Python code from the code panel into a graph."""
        code = self.code_panel.get_code()
        if not code.strip():
            return

        try:
            self.graph = parse_graph(code)
            self.rebuild_scene()
            self.update_code()
        except Exception as e:
            QMessageBox.warning(self, "Parse Error", f"Failed to parse Python code:\n{e}")

    def rebuild_scene(self):
        """Rebuild the scene from the graph."""
        self.scene.clear()

        # Add nodes
        node_items = {}
        for node_id, node in self.graph.nodes.items():
            node_items[node_id] = self.scene.add_node(node)

        # Add connections
        for edge in self.graph.edges:
            source_node = self.graph.get_node(edge.source_node)
            target_node = self.graph.get_node(edge.target_node)
            if source_node and target_node:
                conn = ConnectionGraphicsItem(edge, source_node, target_node)
                self.scene.addItem(conn)
                self.scene.connection_items.append(conn)

        self.scene.update()

    def update_code(self):
        """Update the code panel from the graph."""
        code = generate_code(self.graph)
        self.code_panel.set_code(code)
        self.scene.update()

    def run_graph(self):
        """Execute the generated Python code."""
        code = self.code_panel.get_code()
        if not code.strip():
            return

        self.console.clear()
        self.console.append("--- Execution Started ---")
        
        import io
        import contextlib
        
        def gui_input(prompt=""):
            text, ok = QInputDialog.getText(self, "Input Required", prompt)
            return text if ok else ""

        stdout = io.StringIO()
        try:
            # Inject gui_input as the 'input' function
            exec_globals = {"__name__": "__main__", "input": gui_input}
            with contextlib.redirect_stdout(stdout):
                exec(code, exec_globals)
            self.console.append(stdout.getvalue())
        except Exception as e:
            self.console.append(f"ERROR: {e}")
        
        self.console.append("--- Execution Finished ---")

    def clear_graph(self):
        """Clear all nodes."""
        self.save_state()
        self.graph.clear()
        self.scene.clear()
        self.code_panel.set_code("")

    def new_file(self):
        self.clear_graph()
        self.current_file = None

    def save_file(self):
        if not self.current_file:
            self.current_file, _ = QFileDialog.getSaveFileName(
                self, "Save pyDOT Graph", "", "pyDOT Files (*.pydot);;All Files (*)"
            )
        if self.current_file:
            try:
                data = self.graph.to_dict()
                with open(self.current_file, "w") as f:
                    json.dump(data, f, indent=4)
                self.window().statusBar().showMessage(f"Saved: {self.current_file}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save graph:\n{e}")

    def load_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open pyDOT Graph", "", "pyDOT Files (*.pydot);;All Files (*)"
        )
        if filename:
            try:
                with open(filename, "r") as f:
                    data = json.load(f)
                self.graph = Graph.from_dict(data)
                self.current_file = filename
                self.rebuild_scene()
                self.update_code()
                self.window().statusBar().showMessage(f"Loaded: {filename}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load graph:\n{e}")


class MainWindow(QMainWindow):
    """Main window for pyDOT editor."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("pyDOT - Visual Python Editor")
        self.setGeometry(100, 100, 1400, 800)
        
        # Central widget with editor
        self.editor = NodeEditor()
        self.setCentralWidget(self.editor)

        self.setup_menu()
        self.statusBar().showMessage("Ready")

    def setup_menu(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # File menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.editor.clear_graph)
        file_menu.addAction(new_action)

        open_action = QAction("Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.editor.load_file)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.editor.save_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.editor.undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.editor.redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.editor.copy_selection)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.editor.paste_selection)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        clear_action = QAction("Clear All", self)
        clear_action.triggered.connect(self.editor.clear_graph)
        edit_menu.addAction(clear_action)

        # View menu
        view_menu = menubar.addMenu("View")
        
        fit_action = QAction("Fit View", self)
        fit_action.setShortcut("F")
        fit_action.triggered.connect(lambda: self.editor.view.fitInView(
            self.editor.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        view_menu.addAction(fit_action)

        view_menu.addSeparator()

        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.editor.view.scale(1.25, 1.25))
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.editor.view.scale(0.8, 0.8))
        view_menu.addAction(zoom_out_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        
        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        about_action = QAction("About pyDOT", self)
        about_action.triggered.connect(lambda: QMessageBox.about(
            self, "About pyDOT",
            "pyDOT v0.1.0\n\nA visual Python scripting language.\n\n"
            "Create nodes by clicking items in the left palette.\n"
            "Connect nodes by dragging from output ports to input ports."
        ))
        help_menu.addAction(about_action)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Keyboard Shortcuts",
            "Ctrl + N: New / Clear All\n"
            "Ctrl + S: Save\n"
            "Ctrl + O: Open\n"
            "Ctrl + Z: Undo\n"
            "Ctrl + Y: Redo\n"
            "Ctrl + C: Copy\n"
            "Ctrl + V: Paste\n"
            "Del / Backspace: Delete Node\n"
            "F: Fit View\n"
            "Middle Click: Pan View\n"
            "Mouse Wheel: Zoom"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark theme stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background: #0f0f1a;
        }
        QMenuBar {
            background: #1a1a2e;
            color: #ccc;
        }
        QMenuBar::item:selected {
            background: #2a2a3e;
        }
        QMenu {
            background: #1a1a2e;
            color: #ccc;
            border: 1px solid #3a3a4a;
        }
        QMenu::item:selected {
            background: #2a2a3e;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()