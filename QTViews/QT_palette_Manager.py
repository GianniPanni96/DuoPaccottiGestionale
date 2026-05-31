from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class QTPaletteManager:
    """Gestisce la QPalette globale + uno stylesheet applicativo coerente.

    La palette di sistema resta la base: gli override modificano solo i
    ruoli dichiarati. Ripreso da willowGestionale2.0."""

    ROLE_BY_NAME = {
        "window": QPalette.ColorRole.Window,
        "window-text": QPalette.ColorRole.WindowText,
        "base": QPalette.ColorRole.Base,
        "alternate-base": QPalette.ColorRole.AlternateBase,
        "tool-tip-base": QPalette.ColorRole.ToolTipBase,
        "tool-tip-text": QPalette.ColorRole.ToolTipText,
        "placeholder-text": QPalette.ColorRole.PlaceholderText,
        "text": QPalette.ColorRole.Text,
        "button": QPalette.ColorRole.Button,
        "button-text": QPalette.ColorRole.ButtonText,
        "bright-text": QPalette.ColorRole.BrightText,
        "light": QPalette.ColorRole.Light,
        "midlight": QPalette.ColorRole.Midlight,
        "mid": QPalette.ColorRole.Mid,
        "dark": QPalette.ColorRole.Dark,
        "shadow": QPalette.ColorRole.Shadow,
        "highlight": QPalette.ColorRole.Highlight,
        "highlighted-text": QPalette.ColorRole.HighlightedText,
        "link": QPalette.ColorRole.Link,
        "link-visited": QPalette.ColorRole.LinkVisited,
    }

    GROUP_BY_NAME = {
        "active": QPalette.ColorGroup.Active,
        "inactive": QPalette.ColorGroup.Inactive,
        "disabled": QPalette.ColorGroup.Disabled,
    }

    DEFAULT_OVERRIDES = {
        "highlight": "#2e7d57",
        "highlighted-text": "#ffffff",
        "button-text": "#ffffff",
        "mid": "#c2c2c2",
    }

    APP_STYLESHEET = """
        QPushButton {
            background-color: palette(button);
            color: palette(button-text);
            border: 1px solid palette(highlight);
            border-radius: 4px;
            padding: 5px 10px;
        }
        QPushButton:hover { border-color: palette(light); }
        QPushButton:pressed { background-color: palette(dark); border-color: palette(highlight); }
        QPushButton:disabled {
            background-color: palette(window);
            color: palette(mid);
            border-color: palette(mid);
        }
        QLineEdit {
            background-color: palette(base);
            color: palette(text);
            border: none;
            border-bottom: 1px solid palette(midlight);
            padding: 4px 2px;
        }
        QLineEdit:focus { border-bottom: 2px solid palette(highlight); }
        QToolTip {
            background-color: palette(midlight);
            color: palette(text);
            border: 1px solid palette(mid);
            padding: 4px 6px;
        }
    """

    def __init__(self, app: QApplication | None = None):
        self.app = app or QApplication.instance()
        if self.app is None:
            raise RuntimeError("QTPaletteManager richiede una QApplication attiva.")
        self._system_palette = QPalette(self.app.palette())
        self._palette = QPalette(self._system_palette)
        self._system_stylesheet = self.app.styleSheet()

    @classmethod
    def install(cls, app=None, overrides=None) -> "QTPaletteManager":
        manager = cls(app)
        manager.apply(cls.DEFAULT_OVERRIDES if overrides is None else overrides)
        return manager

    def apply(self, overrides: Mapping[str, str | QColor] | None = None) -> None:
        self._palette = QPalette(self._system_palette)
        if overrides:
            for role_name, color in overrides.items():
                self._set_color(role_name, color)
        self.app.setPalette(self._palette)
        self.app.setStyleSheet(self._merged_stylesheet())

    def _set_color(self, role_name: str, color: str | QColor) -> None:
        qt_color = QColor(color)
        if not qt_color.isValid():
            raise ValueError(f"Colore Qt non valido: {color!r}")
        self._palette.setColor(self._role(role_name), qt_color)

    def _merged_stylesheet(self) -> str:
        if not self._system_stylesheet.strip():
            return self.APP_STYLESHEET
        return f"{self._system_stylesheet}\n{self.APP_STYLESHEET}"

    @classmethod
    def _role(cls, role_name: str) -> QPalette.ColorRole:
        normalized = role_name.strip().lower().replace("_", "-")
        return cls.ROLE_BY_NAME[normalized]
