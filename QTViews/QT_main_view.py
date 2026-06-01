"""Finestra principale: QMenuBar + QTabWidget (Utenti, Spese, Entrate,
Analisi) + menu utente in alto a destra.

Ogni tab di dominio e' uno QStackedWidget che alterna lista e dettaglio,
cosi' la barra delle tab resta sempre visibile. La tab Analisi e' un
placeholder fino allo step 3. In sessione admin le tab finanziarie sono
disabilitate (l'admin non accede ai dati finanziari)."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Gestionale_Enums import DBUsersColumns
from Utils.View_utils import ViewUtils
from QTViews.ListViews.QT_expenses_view import QTExpensesView
from QTViews.ListViews.QT_incomes_view import QTIncomesView
from QTViews.QT_analysis_view import QTAnalysisView
from QTViews.QT_users_view import QTUsersView

if TYPE_CHECKING:
    from App_context import AppContext


class QTMainWindow(QMainWindow):
    TAB_USERS = "Utenti"
    TAB_EXPENSES = "Spese"
    TAB_INCOMES = "Entrate"
    TAB_ANALYSIS = "Analisi"

    FINANCIAL_TABS = (TAB_EXPENSES, TAB_INCOMES, TAB_ANALYSIS)

    def __init__(self, app_context: "AppContext"):
        super().__init__()
        self.app_context = app_context

        self.login_status = False
        self.logged_user_id = -1
        self.is_admin = False

        self._tab_pages = {}
        self.user_detail_view = None
        self.expense_detail_view = None
        self.income_detail_view = None

        self.setWindowTitle(self._window_title())
        self.resize(1150, 740)

        self._build_menu_bar()
        self.tabview = QTabWidget()
        self.tabview.setObjectName("MainTabView")
        self._build_tabs()
        self.setCentralWidget(self.tabview)
        self._build_menu_corner()

        self.app_context.event_bus.subscribe(
            ViewUtils.EventBusKeys.LOGIN_STATUS_CHANGED.value, self._on_login_status_changed
        )

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _window_title(self) -> str:
        name = self.app_context.app_settings_manager.get_collective_name()
        return f"DuoPaccotti — {name}"

    def _build_menu_bar(self):
        top_bar = QWidget(self)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 8, 0)
        top_layout.setSpacing(8)

        menubar = QMenuBar(top_bar)
        top_layout.addWidget(menubar, stretch=1)

        self.menu_actions_widget = QWidget(top_bar)
        self.menu_actions_layout = QHBoxLayout(self.menu_actions_widget)
        self.menu_actions_layout.setContentsMargins(4, 2, 4, 2)
        self.menu_actions_layout.setSpacing(8)
        top_layout.addWidget(self.menu_actions_widget, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self.setMenuWidget(top_bar)

        categories = menubar.addMenu("Categorie")
        categories.addAction("Gestisci categorie").triggered.connect(self._open_categories)

        settings = menubar.addMenu("Impostazioni")
        settings.addAction("Nome del nucleo").triggered.connect(self._edit_collective_name)
        settings.addAction("Finestra rimborsi").triggered.connect(self._edit_refund_window)
        settings.addAction("Default utente").triggered.connect(self._placeholder_action)

        self.admin_menu = menubar.addMenu("ADMIN")
        self.admin_menu.addAction("Gestione utenti").triggered.connect(
            lambda: self.tabview.setCurrentWidget(self._tab_pages[self.TAB_USERS])
        )

    def _build_tabs(self):
        # Utenti
        self.users_view = QTUsersView(
            app_context=self.app_context, on_open_detail=self._open_user_detail, parent=self
        )
        self.users_page = self._build_stack(self.users_view)
        self._tab_pages[self.TAB_USERS] = self.users_page
        self.tabview.addTab(self.users_page, self.TAB_USERS)

        # Spese
        self.expenses_view = QTExpensesView(
            app_context=self.app_context, on_open_detail=self._open_expense_detail, parent=self
        )
        self.expenses_page = self._build_stack(self.expenses_view)
        self._tab_pages[self.TAB_EXPENSES] = self.expenses_page
        self.tabview.addTab(self.expenses_page, self.TAB_EXPENSES)

        # Entrate
        self.incomes_view = QTIncomesView(
            app_context=self.app_context, on_open_detail=self._open_income_detail, parent=self
        )
        self.incomes_page = self._build_stack(self.incomes_view)
        self._tab_pages[self.TAB_INCOMES] = self.incomes_page
        self.tabview.addTab(self.incomes_page, self.TAB_INCOMES)

        # Analisi
        self.analysis_view = QTAnalysisView(app_context=self.app_context, parent=self)
        self.analysis_page = self.analysis_view
        self._tab_pages[self.TAB_ANALYSIS] = self.analysis_page
        self.tabview.addTab(self.analysis_page, self.TAB_ANALYSIS)

    @staticmethod
    def _build_stack(list_view) -> QStackedWidget:
        stack = QStackedWidget()
        stack.addWidget(list_view)
        return stack

    @staticmethod
    def _build_placeholder(name: str, sub: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(f"Tab «{name}»")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: palette(mid); font-size: 16pt;")
        sub_label = QLabel(sub)
        sub_label.setAlignment(Qt.AlignCenter)
        sub_label.setStyleSheet("color: palette(mid);")
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addWidget(sub_label)
        layout.addStretch(1)
        return page

    USER_ICON_SIZE = 36

    def _build_menu_corner(self):
        self.user_button = QToolButton()
        self.user_button.setPopupMode(QToolButton.InstantPopup)
        self.user_button.setText("👤")
        self.user_button.setIconSize(QSize(self.USER_ICON_SIZE, self.USER_ICON_SIZE))
        self.user_button.setCursor(Qt.PointingHandCursor)
        self.user_button.setToolTip("Menu utente")
        self.user_button.setStyleSheet(
            "QToolButton { border: 1px solid palette(mid); border-radius: 6px; padding: 4px 10px; }"
            "QToolButton::menu-indicator { image: none; width: 0px; }"
        )

        self.user_menu = QMenu(self.user_button)
        self.login_action = QAction("Esegui il login", self)
        self.login_action.triggered.connect(self._manage_login)
        self.user_menu.addAction(self.login_action)
        self.switch_account_action = QAction("Cambia utente", self)
        self.switch_account_action.triggered.connect(self._switch_account)
        self.switch_account_action.setEnabled(False)
        self.user_menu.addAction(self.switch_account_action)
        self.user_menu.addSeparator()
        self.admin_login_action = QAction("Login come amministratore", self)
        self.admin_login_action.triggered.connect(self._login_as_admin)
        self.user_menu.addAction(self.admin_login_action)
        self.user_button.setMenu(self.user_menu)

        self.session_label = QLabel("Non autenticato")
        self.session_label.setStyleSheet("color: palette(mid);")
        self.menu_actions_layout.addWidget(self.session_label)
        self.menu_actions_layout.addWidget(self.user_button)

    # ------------------------------------------------------------------
    # Navigazione lista <-> dettaglio
    # ------------------------------------------------------------------

    def _show_detail(self, stack, attr, widget):
        old = getattr(self, attr)
        if old is not None:
            stack.removeWidget(old)
            old.deleteLater()
        setattr(self, attr, widget)
        stack.addWidget(widget)
        stack.setCurrentWidget(widget)

    def _back_to_list(self, stack, list_view, attr):
        stack.setCurrentWidget(list_view)
        old = getattr(self, attr)
        if old is not None:
            stack.removeWidget(old)
            old.deleteLater()
            setattr(self, attr, None)

    def _open_user_detail(self, user_id):
        from QTViews.Details.QT_user_detail_view import QTUserDetailView
        view = QTUserDetailView(
            app_context=self.app_context, user_id=user_id, on_back=self._back_to_users_list, parent=self
        )
        self._show_detail(self.users_page, "user_detail_view", view)

    def _back_to_users_list(self):
        self._back_to_list(self.users_page, self.users_view, "user_detail_view")
        self.users_view.refresh()

    def _open_expense_detail(self, expense_id):
        from QTViews.Details.QT_expense_detail_view import QTExpenseDetailView
        view = QTExpenseDetailView(
            app_context=self.app_context, expense_id=expense_id, on_back=self._back_to_expenses_list, parent=self
        )
        self._show_detail(self.expenses_page, "expense_detail_view", view)

    def _back_to_expenses_list(self):
        self._back_to_list(self.expenses_page, self.expenses_view, "expense_detail_view")
        self.expenses_view.refresh()

    def _open_income_detail(self, income_id):
        from QTViews.Details.QT_income_detail_view import QTIncomeDetailView
        view = QTIncomeDetailView(
            app_context=self.app_context, income_id=income_id, on_back=self._back_to_incomes_list, parent=self
        )
        self._show_detail(self.incomes_page, "income_detail_view", view)

    def _back_to_incomes_list(self):
        self._back_to_list(self.incomes_page, self.incomes_view, "income_detail_view")
        self.incomes_view.refresh()

    # ------------------------------------------------------------------
    # Sessione / login
    # ------------------------------------------------------------------

    def apply_session_state(self, login_status: bool, user_id: int, is_admin: bool):
        self.login_status = login_status
        self.logged_user_id = user_id
        self.is_admin = is_admin
        self._toggle_login_widgets()
        self._reset_details()
        self._refresh_all_views()
        self._refresh_tabs_for_session()

    def _on_login_status_changed(self, payload):
        self.login_status = bool(payload.get("login_status"))
        self.logged_user_id = int(payload.get("logged_user_id", -1))
        self.is_admin = bool(payload.get("is_admin", False))
        self._toggle_login_widgets()
        self._reset_details()
        self._refresh_all_views()
        self._refresh_tabs_for_session()

    def _toggle_login_widgets(self):
        if self.login_status:
            self.login_action.setText("Esegui il logout")
            self.switch_account_action.setEnabled(True)
            self.admin_login_action.setEnabled(not self.is_admin)
            self.session_label.setText(self._session_text())
        else:
            self.login_action.setText("Esegui il login")
            self.switch_account_action.setEnabled(False)
            self.admin_login_action.setEnabled(True)
            self.session_label.setText("Non autenticato")
        self.admin_menu.menuAction().setVisible(self.is_admin)

    def _session_text(self) -> str:
        if self.is_admin:
            return "Amministratore"
        user = self.app_context.users_query_service.retrieve_user_map_by_id(self.logged_user_id)
        if user:
            return f"{user[DBUsersColumns.FIRST_NAME.value]} {user[DBUsersColumns.LAST_NAME.value]}"
        return "Utente"

    def _reset_details(self):
        self._back_to_list(self.users_page, self.users_view, "user_detail_view")
        self._back_to_list(self.expenses_page, self.expenses_view, "expense_detail_view")
        self._back_to_list(self.incomes_page, self.incomes_view, "income_detail_view")

    def _refresh_all_views(self):
        self.users_view.refresh()
        self.expenses_view.refresh()
        self.incomes_view.refresh()
        self.analysis_view.refresh()

    def _refresh_tabs_for_session(self):
        for name, page in self._tab_pages.items():
            idx = self.tabview.indexOf(page)
            disable = name in self.FINANCIAL_TABS and self.is_admin
            self.tabview.setTabEnabled(idx, not disable)
        if not self.tabview.isTabEnabled(self.tabview.currentIndex()):
            self.tabview.setCurrentWidget(self._tab_pages[self.TAB_USERS])

    # ------------------------------------------------------------------
    # Azioni menu utente
    # ------------------------------------------------------------------

    def _manage_login(self):
        if self.login_status:
            confirm = QMessageBox.question(
                self, "Logout", "Vuoi eseguire il logout?", QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self._do_logout()
            return
        from QTViews.LoginViews.QT_login_dialog import QTLoginDialog
        dialog = QTLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            if dialog.logged_as_admin:
                self.apply_session_state(True, -1, True)
            else:
                self.apply_session_state(True, dialog.user_id, False)

    def _switch_account(self):
        if not self.login_status:
            return
        self._do_logout(silent=True)
        from QTViews.LoginViews.QT_login_dialog import QTLoginDialog
        dialog = QTLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            if dialog.logged_as_admin:
                self.apply_session_state(True, -1, True)
            else:
                self.apply_session_state(True, dialog.user_id, False)

    def _login_as_admin(self):
        if self.login_status:
            self._do_logout(silent=True)
        from QTViews.LoginViews.QT_admin_login_dialog import QTAdminLoginDialog
        dialog = QTAdminLoginDialog(app_context=self.app_context, parent=self)
        dialog.exec()
        if dialog.success:
            self.apply_session_state(True, -1, True)

    def _do_logout(self, silent: bool = False):
        self.app_context.user_auth_service.logout()
        self.apply_session_state(False, -1, False)

    # ------------------------------------------------------------------
    # Azioni menu in alto
    # ------------------------------------------------------------------

    def _open_categories(self):
        self._placeholder_action()

    def _edit_collective_name(self):
        current = self.app_context.app_settings_manager.get_collective_name()
        name, ok = QInputDialog.getText(self, "Nome del nucleo", "Nome:", text=current)
        if ok and name.strip():
            self.app_context.app_settings_manager.set_collective_name(name.strip())
            self.setWindowTitle(self._window_title())

    def _edit_refund_window(self):
        from Utils.Refund_window_utils import WINDOW_LABELS

        settings = self.app_context.app_settings_manager
        keys = list(settings.REFUND_WINDOWS)
        labels = [WINDOW_LABELS.get(k, k) for k in keys]
        current_key = settings.get_refund_window()
        current_idx = keys.index(current_key) if current_key in keys else 0

        label, ok = QInputDialog.getItem(
            self,
            "Finestra rimborsi",
            "Periodo entro cui calcolare i rimborsi tra utenti:",
            labels,
            current_idx,
            editable=False,
        )
        if not ok:
            return
        settings.set_refund_window(keys[labels.index(label)])
        self.analysis_view.reset_refund_window()

    def _placeholder_action(self):
        QMessageBox.information(
            self, "In arrivo", "Questa funzione sara' disponibile in uno step successivo."
        )
