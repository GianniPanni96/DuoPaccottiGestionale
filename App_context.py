"""Container di dependency-injection: istanzia e cabla model, servizi,
controller, parser, config manager ed event bus. E' l'unico oggetto
passato alle view.

Ordine di costruzione studiato per evitare cicli:
db_model -> session_context -> query services base -> visibility ->
query services finanziari -> auth -> analyzer -> controller -> parser.
"""

from AnalyzerServices.Expense_analyzer_service import ExpenseAnalyzerService
from AnalyzerServices.Income_analyzer_service import IncomeAnalyzerService
from AnalyzerServices.Refund_analyzer_service import RefundAnalyzerService
from Controllers.Admin_controller import AdminController
from Controllers.Expense_controller import ExpenseController
from Controllers.Income_controller import IncomeController
from Controllers.Refund_controller import RefundController
from Controllers.User_controller import UserController
from Event_bus import EventBus
from Model import DatabaseModel
from OtherServices.Session_context import SessionContext
from OtherServices.User_auth_service import UserAuthService
from OtherServices.Visibility_service import VisibilityService
from ParserServices.bank_statement_parser import BankStatementParser
from ParserServices.esselunga_receipt_parser import EsselungaReceiptParser
from QueryServices.Admin_query_service import AdminQueryService
from QueryServices.Expense_shares_query_service import ExpenseSharesQueryService
from QueryServices.Expenses_query_service import ExpensesQueryService
from QueryServices.Incomes_query_service import IncomesQueryService
from QueryServices.Users_query_service import UsersQueryService


class AppContext:
    def __init__(self, config_manager, db_path, images_path=""):
        self.db_path = db_path
        self.images_path = images_path
        self.config_manager = config_manager

        # Manager di config esposti per comodita' delle view.
        self.app_settings_manager = config_manager.app_settings_manager
        self.catalogs_manager = config_manager.catalogs_manager
        self.category_hints_manager = config_manager.category_hints_manager
        self.gui_preferences_manager = config_manager.gui_preferences_manager

        # Model + sessione.
        self.db_model = DatabaseModel(db_path)
        self.session_context = SessionContext()

        # Query services base (no visibilita').
        self.users_query_service = UsersQueryService(self.db_model)
        self.admin_query_service = AdminQueryService(self.db_model)
        self.expense_shares_query_service = ExpenseSharesQueryService(self.db_model)

        # Filtro visibilita' + query services finanziari.
        self.visibility_service = VisibilityService(
            self.session_context, self.expense_shares_query_service
        )
        self.expenses_query_service = ExpensesQueryService(self.db_model, self.visibility_service)
        self.incomes_query_service = IncomesQueryService(self.db_model, self.visibility_service)

        # Autenticazione.
        self.user_auth_service = UserAuthService(
            self.users_query_service,
            self.db_model,
            self.admin_query_service,
            self.session_context,
        )

        # Analyzer.
        self.expense_analyzer_service = ExpenseAnalyzerService(self.expenses_query_service)
        self.income_analyzer_service = IncomeAnalyzerService(self.incomes_query_service)
        self.refund_analyzer_service = RefundAnalyzerService(
            self.expenses_query_service,
            self.expense_shares_query_service,
            self.users_query_service,
        )

        # Controller.
        self.refund_controller = RefundController(self.db_model, self.expense_shares_query_service)
        self.expense_controller = ExpenseController(
            self.db_model,
            self.users_query_service,
            self.refund_controller,
            self.app_settings_manager,
        )
        self.income_controller = IncomeController(self.db_model, self.app_settings_manager)
        self.user_controller = UserController(self.db_model, self.users_query_service)
        self.admin_controller = AdminController(self.db_model, self.admin_query_service)

        # Parser PDF.
        self.bank_parser = BankStatementParser(self.category_hints_manager)
        self.esselunga_parser = EsselungaReceiptParser(self.category_hints_manager)

        # Bus eventi.
        self.event_bus = EventBus()
