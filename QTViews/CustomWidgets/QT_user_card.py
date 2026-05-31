"""Card cliccabile di un utente per la tab Utenti."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from Gestionale_Enums import DBUsersColumns, UserStatus


class QTUserCard(QFrame):
    def __init__(self, user: dict, on_open_detail=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.on_open_detail = on_open_detail
        self.user_id = user[DBUsersColumns.ID.value]

        self.setFixedSize(260, 110)
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QTUserCard { background-color: palette(alternate-base); border-radius: 10px;"
            " border: 1px solid palette(mid); }"
            "QTUserCard:hover { border: 1px solid palette(highlight); }"
        )
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_avatar())

        info = QVBoxLayout()
        info.setSpacing(2)

        name = QLabel(
            f"{self.user[DBUsersColumns.FIRST_NAME.value]} "
            f"{self.user[DBUsersColumns.LAST_NAME.value]}"
        )
        f = name.font()
        f.setBold(True)
        f.setPointSize(12)
        name.setFont(f)
        info.addWidget(name)

        email = self.user.get(DBUsersColumns.EMAIL.value) or "—"
        email_label = QLabel(email)
        email_label.setStyleSheet("color: palette(mid);")
        info.addWidget(email_label)

        status = self.user.get(DBUsersColumns.STATUS.value, UserStatus.ATTIVO.value)
        has_password = bool(self.user.get(DBUsersColumns.PASSWORD_LOGIN.value))
        badge = QLabel(f"{status}{'' if has_password else ' · senza password'}")
        badge.setStyleSheet("color: palette(mid); font-size: 9pt;")
        info.addWidget(badge)

        info.addStretch(1)
        layout.addLayout(info, stretch=1)

    def _build_avatar(self) -> QLabel:
        avatar = QLabel()
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignCenter)

        photo_path = self.user.get(DBUsersColumns.PHOTO_PATH.value) or ""
        if photo_path and Path(photo_path).exists():
            pix = QPixmap(photo_path).scaled(
                56, 56, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            avatar.setPixmap(pix)
            avatar.setStyleSheet("border-radius: 28px;")
        else:
            initials = (
                self.user[DBUsersColumns.FIRST_NAME.value][:1]
                + self.user[DBUsersColumns.LAST_NAME.value][:1]
            ).upper()
            avatar.setText(initials)
            avatar.setStyleSheet(
                "background-color: palette(highlight); color: palette(highlighted-text);"
                " border-radius: 28px; font-size: 18pt; font-weight: bold;"
            )
        return avatar

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_open_detail is not None:
            self.on_open_detail(self.user_id)
        super().mouseReleaseEvent(event)
