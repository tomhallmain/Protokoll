"""Toast notification for transient feedback (e.g. "Path copied to clipboard")."""

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve

from ..utils.theme_manager import ThemeManager


def show_toast(parent, message, duration_ms=2500):
    """
    Show a transient toast notification over the given parent widget.

    The toast is positioned at the bottom-center of the parent, shown for
    duration_ms, then fades out and is removed.

    Args:
        parent: QWidget to show the toast over (e.g. main window).
        message: Text to display in the toast.
        duration_ms: How long to show the toast before fading out, in milliseconds.
    """
    theme = ThemeManager.DARK_THEME
    base = theme["base"]
    text_color = theme["text"]
    success = theme["log_viewer"]["success"]

    toast = QFrame(parent)
    toast.setObjectName("toast")
    toast.setStyleSheet(f"""
        #toast {{
            background-color: {base};
            color: {text_color};
            border: 1px solid {success};
            border-radius: 6px;
            padding: 8px 16px;
        }}
        #toast QLabel {{
            color: {text_color};
            font-size: 13px;
        }}
    """)

    layout = QVBoxLayout(toast)
    layout.setContentsMargins(12, 8, 12, 8)
    label = QLabel(message)
    label.setObjectName("toastLabel")
    layout.addWidget(label)

    toast.setMinimumWidth(200)
    toast.adjustSize()
    toast.setFixedSize(toast.size())

    # Position at top-center of parent, just below the nav area
    x = (parent.width() - toast.width()) // 2
    y = 56
    toast.setGeometry(x, y, toast.width(), toast.height())
    toast.raise_()
    toast.show()

    def fade_out():
        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        # Parented to the toast, so a parent closing mid-fade takes the
        # animation with it instead of leaving it driving a deleted object.
        animation = QPropertyAnimation(effect, b"opacity", toast)
        animation.setDuration(300)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(toast.deleteLater)
        toast._animation = animation
        toast._effect = effect
        animation.start()

    # A child of the toast, so destroying the toast cancels it. A bare
    # QTimer.singleShot() belongs to no object and still fires after the parent
    # window is gone, and fade_out() then touches a deleted QFrame -- which
    # raises inside the event loop, where PyQt turns an unhandled exception into
    # an abort.
    fade_timer = QTimer(toast)
    fade_timer.setSingleShot(True)
    fade_timer.timeout.connect(fade_out)
    fade_timer.start(duration_ms)
