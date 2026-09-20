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
    if not parent.isVisible():
        # Nothing to show it over. The fade would come due seconds later, by
        # which time the parent can be closed or freed, and what runs then has
        # no safe way to find that out - see below.
        return

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

    # The fade is built now, while the toast is known to be alive, and wired up
    # entirely between objects: the timer starts the animation, the animation
    # deletes the toast. Every piece is parented to the toast, so destroying it
    # destroys them and nothing is left to fire.
    #
    # The delay deliberately schedules no Python of its own. A function called
    # back seconds later still holds the widget, and by then Qt may have freed
    # it without PyQt noticing -- sip.isdeleted() then reports the wrapper as
    # live and the first attribute touched is an access violation, which no
    # amount of checking inside that function can catch.
    effect = QGraphicsOpacityEffect(toast)
    toast.setGraphicsEffect(effect)

    fade = QPropertyAnimation(effect, b"opacity", toast)
    fade.setDuration(300)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    fade.finished.connect(toast.deleteLater)

    fade_timer = QTimer(toast)
    fade_timer.setSingleShot(True)
    fade_timer.timeout.connect(fade.start)
    fade_timer.start(duration_ms)
