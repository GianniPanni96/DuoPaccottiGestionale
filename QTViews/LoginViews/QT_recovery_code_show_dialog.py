"""Mostra (una volta sola) il recovery code generato per un utente/admin."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class QTRecoveryCodeShowDialog(QDialog):
    def __init__(self, recovery_code: str, parent=None):
        super().__init__(parent)
        self.recovery_code = recovery_code
        self.setWindowTitle("Codice di recupero")
        self.setModal(True)
        self.resize(440, 240)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Conserva questo codice di recupero")
        f = title.font()
        f.setBold(True)
        f.setPointSize(15)
        title.setFont(f)
        root.addWidget(title)

        info = QLabel(
            "E' l'unico modo per reimpostare la password se la dimentichi.\n"
            "Verra' mostrato una sola volta: salvalo in un posto sicuro."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid);")
        root.addWidget(info)

        code_row = QHBoxLayout()
        self.code_field = QLineEdit(self.recovery_code)
        self.code_field.setReadOnly(True)
        f2 = self.code_field.font()
        f2.setPointSize(16)
        f2.setBold(True)
        self.code_field.setFont(f2)
        self.code_field.setAlignment(Qt.AlignCenter)
        code_row.addWidget(self.code_field, stretch=1)

        copy_btn = QPushButton("Copia")
        copy_btn.clicked.connect(self._copy)
        code_row.addWidget(copy_btn)
        root.addLayout(code_row)

        root.addStretch(1)

        ok_btn = QPushButton("Ho salvato il codice")
        ok_btn.clicked.connect(self.accept)
        root.addWidget(ok_btn)

    def _copy(self):
        QApplication.clipboard().setText(self.recovery_code)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def reject(self):
        return
