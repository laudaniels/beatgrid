from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from beatgrid.gui import theme, tooltips

HEIGHT = 34


class TitleBar(QWidget):
    """BeatGrid's own title bar (the main window is frameless): the window
    title plus minimise / maximise-restore / close. Dragging it moves the
    window and double-clicking toggles maximised -- both handed to the window
    system (startSystemMove), so they behave like a normal title bar.

    Exists because Qt's own Wayland decorations under WSLg are a fixed light
    grey that can't follow the app's dark theme."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self.setFixedHeight(HEIGHT)
        self.setAutoFillBackground(False)

        self.title_label = QLabel(window.windowTitle())
        font = QFont(self.title_label.font())
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.1)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet(f"color: {theme.TEXT.name()};")

        self.minimize_button = self._button("–", tooltips.TITLE_MINIMIZE, window.showMinimized)
        self.maximize_button = self._button("□", tooltips.TITLE_MAXIMIZE, self.toggle_maximized)
        self.close_button = self._button("✕", tooltips.TITLE_CLOSE, window.close, danger=True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 2)
        layout.setSpacing(0)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            layout.addWidget(button)

        window.windowTitleChanged.connect(self.title_label.setText)
        window.installEventFilter(self)  # follow maximise/restore for the button
        self._sync_maximize_button()

    def _button(self, text: str, tooltip: str, action, *, danger: bool = False) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(46, HEIGHT - 2)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hover = "#c42b1c" if danger else theme.BUTTON.name()
        button.setStyleSheet(
            f"QToolButton {{ color: {theme.TEXT.name()}; border: none; font-size: 14px; }}"
            f"QToolButton:hover {{ background: {hover}; }}"
        )
        button.clicked.connect(action)
        return button

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def _sync_maximize_button(self) -> None:
        maximized = self._window.isMaximized()
        self.maximize_button.setText("❐" if maximized else "□")
        self.maximize_button.setToolTip(
            tooltips.TITLE_RESTORE if maximized else tooltips.TITLE_MAXIMIZE
        )

    def eventFilter(self, watched, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if watched is self._window and event.type() == QEvent.Type.WindowStateChange:
            self._sync_maximize_button()
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme.TITLE_BAR)
        # a thin accent line separating the title bar from the toolbar
        painter.setPen(QPen(QColor(theme.OUTLINE), 2))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
