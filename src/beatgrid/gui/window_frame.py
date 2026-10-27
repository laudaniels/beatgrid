from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt

# Width of the window's own edge: a 2 px outline plus a little room to grab
# for resizing (the main window is frameless, see widgets/title_bar.py).
FRAME_WIDTH = 5
OUTLINE_WIDTH = 2

_CURSORS = {
    Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
    Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
}


def resize_edges(pos: QPoint, rect: QRect, margin: int = FRAME_WIDTH) -> Qt.Edge:
    """Which window edges (none, one, or two for a corner) a point in the
    window's own coordinates is close enough to for resizing. Corners get a
    larger grab area, as in most window managers."""
    corner = margin * 3
    edges = Qt.Edge(0)
    near_left, near_right = pos.x() < margin, pos.x() >= rect.width() - margin
    near_top, near_bottom = pos.y() < margin, pos.y() >= rect.height() - margin
    if near_left or near_right:
        if pos.y() < corner:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= rect.height() - corner:
            edges |= Qt.Edge.BottomEdge
    if near_top or near_bottom:
        if pos.x() < corner:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= rect.width() - corner:
            edges |= Qt.Edge.RightEdge
    if near_left:
        edges |= Qt.Edge.LeftEdge
    if near_right:
        edges |= Qt.Edge.RightEdge
    if near_top:
        edges |= Qt.Edge.TopEdge
    if near_bottom:
        edges |= Qt.Edge.BottomEdge
    return edges


def cursor_for(edges: Qt.Edge) -> Qt.CursorShape:
    diagonal_down = (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge)
    diagonal_up = (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge)
    if edges in diagonal_down:
        return Qt.CursorShape.SizeFDiagCursor
    if edges in diagonal_up:
        return Qt.CursorShape.SizeBDiagCursor
    return _CURSORS.get(edges, Qt.CursorShape.ArrowCursor)
