"""Tab Utenti: card degli utenti in flow-layout + creazione nuovo utente."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from QTViews.CustomWidgets.QT_flow_layout import FlowLayout
from QTViews.CustomWidgets.QT_user_card import QTUserCard

if TYPE_CHECKING:
    from App_context import AppContext


class QTUsersView(QWidget):
    def __init__(self, app_context: "AppContext", on_open_detail=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.on_open_detail = on_open_detail
        self.users_query_service = app_context.users_query_service
        self._cards = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("Utenti del nucleo")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        top.addWidget(title)
        top.addStretch(1)
        add_btn = QPushButton("Aggiungi utente")
        add_btn.clicked.connect(self._on_add)
        top.addWidget(add_btn)
        root.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(scroll, stretch=1)

        self._cards_container = QWidget()
        self._flow = FlowLayout(self._cards_container, margin=4, spacing=14)
        scroll.setWidget(self._cards_container)

        self._empty_label = QLabel("Nessun utente. Aggiungine uno.")
        self._empty_label.setStyleSheet("color: palette(mid);")
        self._empty_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self._empty_label)

    def refresh(self):
        for card in self._cards:
            self._flow.removeWidget(card)
            card.deleteLater()
        self._cards = []

        users = self.users_query_service.retrieve_users_map_list()
        for user in users:
            card = QTUserCard(user, on_open_detail=self.on_open_detail, parent=self._cards_container)
            self._flow.addWidget(card)
            self._cards.append(card)

        self._empty_label.setVisible(not users)

    def _on_add(self):
        from QTViews.Creators.QT_user_create_view import QTUserCreateView
        dialog = QTUserCreateView(app_context=self.app_context, parent=self)
        if dialog.exec() != dialog.Accepted:
            return
        self.refresh()
        if dialog.created_user_id is not None and self.on_open_detail is not None:
            self.on_open_detail(dialog.created_user_id)
