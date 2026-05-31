"""DatabaseModel: accesso SQL grezzo a SQLite.

Replica la filosofia di ``willowGestionale2.0/Model.py``:
- una connessione per operazione, gestita dal context manager
  ``_connect`` che fa commit/rollback/close (evita i lock su Windows);
- query costruite dinamicamente filtrando i ``**kwargs`` sulle colonne
  valide dell'enum di tabella.
"""

import sqlite3
from contextlib import contextmanager

from Gestionale_Enums import (
    DBAdminColumns,
    DBExpenseSharesColumns,
    DBExpensesColumns,
    DBIncomesColumns,
    DBUsersColumns,
)


class DatabaseModel:
    def __init__(self, db_path):
        self.db_path = db_path

    @contextmanager
    def _connect(self):
        """Apre/chiude una connessione facendo commit o rollback.

        Il context manager nativo di sqlite3 non chiude la connection: su
        Windows il file handle resterebbe aperto. Qui replichiamo
        l'auto-commit/rollback e aggiungiamo il close mancante."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Generici
    # ------------------------------------------------------------------

    def delete_row(self, table_name, primary_key_column, primary_key_value):
        query = f"DELETE FROM {table_name} WHERE {primary_key_column} = ?"
        with self._connect() as conn:
            conn.cursor().execute(query, (primary_key_value,))

    def update_row(self, table_name, column_name, new_value, primary_key_column, primary_key_value):
        query = f"UPDATE {table_name} SET {column_name} = ? WHERE {primary_key_column} = ?"
        with self._connect() as conn:
            conn.cursor().execute(query, (new_value, primary_key_value))

    def fetch_table(self, table_name):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            return cursor.fetchall()

    def _insert(self, table_name, columns_enum, **kwargs):
        valid = {c.value for c in columns_enum}
        fields = {k: v for k, v in kwargs.items() if k in valid}
        if not fields:
            raise ValueError("Nessun campo valido specificato per l'inserimento.")
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        query = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(fields.values()))
            return cursor.lastrowid

    def _update(self, table_name, columns_enum, pk_column, pk_value, **kwargs):
        valid = {c.value for c in columns_enum}
        fields = {k: v for k, v in kwargs.items() if k in valid and k != pk_column}
        if not fields:
            return
        assignments = ", ".join([f"{k} = ?" for k in fields.keys()])
        query = f"UPDATE {table_name} SET {assignments} WHERE {pk_column} = ?"
        with self._connect() as conn:
            conn.cursor().execute(query, (*fields.values(), pk_value))

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def add_user(self, **kwargs):
        return self._insert("users", DBUsersColumns, **kwargs)

    def update_user(self, user_id, **kwargs):
        self._update("users", DBUsersColumns, DBUsersColumns.ID.value, user_id, **kwargs)

    def remove_user(self, user_id):
        self.delete_row("users", DBUsersColumns.ID.value, user_id)

    def fetch_users(self):
        return self.fetch_table("users")

    def fetch_user_by_id(self, user_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return cursor.fetchone()

    def fetch_user_by_fullname(self, first_name, last_name):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE first_name = ? AND last_name = ?",
                (first_name, last_name),
            )
            return cursor.fetchone()

    def count_users(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------

    def add_expense(self, **kwargs):
        return self._insert("expenses", DBExpensesColumns, **kwargs)

    def update_expense(self, expense_id, **kwargs):
        self._update("expenses", DBExpensesColumns, DBExpensesColumns.ID.value, expense_id, **kwargs)

    def remove_expense(self, expense_id):
        self.delete_row("expenses", DBExpensesColumns.ID.value, expense_id)

    def fetch_expenses(self):
        return self.fetch_table("expenses")

    def fetch_expense_by_id(self, expense_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
            return cursor.fetchone()

    def fetch_expenses_by_user_id(self, user_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expenses WHERE user_id = ?", (user_id,))
            return cursor.fetchall()

    def fetch_last_expense_insert(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 1")
            return cursor.fetchone()

    # ------------------------------------------------------------------
    # Expense shares
    # ------------------------------------------------------------------

    def add_expense_share(self, **kwargs):
        return self._insert("expense_shares", DBExpenseSharesColumns, **kwargs)

    def update_expense_share(self, share_id, **kwargs):
        self._update(
            "expense_shares", DBExpenseSharesColumns,
            DBExpenseSharesColumns.ID.value, share_id, **kwargs,
        )

    def remove_expense_share(self, share_id):
        self.delete_row("expense_shares", DBExpenseSharesColumns.ID.value, share_id)

    def remove_shares_for_expense(self, expense_id):
        self.delete_row("expense_shares", DBExpenseSharesColumns.EXPENSE_ID.value, expense_id)

    def fetch_expense_shares(self):
        return self.fetch_table("expense_shares")

    def fetch_share_by_id(self, share_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expense_shares WHERE id = ?", (share_id,))
            return cursor.fetchone()

    def fetch_shares_by_expense_id(self, expense_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expense_shares WHERE expense_id = ?", (expense_id,))
            return cursor.fetchall()

    # ------------------------------------------------------------------
    # Incomes
    # ------------------------------------------------------------------

    def add_income(self, **kwargs):
        return self._insert("incomes", DBIncomesColumns, **kwargs)

    def update_income(self, income_id, **kwargs):
        self._update("incomes", DBIncomesColumns, DBIncomesColumns.ID.value, income_id, **kwargs)

    def remove_income(self, income_id):
        self.delete_row("incomes", DBIncomesColumns.ID.value, income_id)

    def fetch_incomes(self):
        return self.fetch_table("incomes")

    def fetch_income_by_id(self, income_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incomes WHERE id = ?", (income_id,))
            return cursor.fetchone()

    def fetch_incomes_by_user_id(self, user_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incomes WHERE user_id = ?", (user_id,))
            return cursor.fetchall()

    def fetch_last_income_insert(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incomes ORDER BY id DESC LIMIT 1")
            return cursor.fetchone()

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def add_admin(self, **kwargs):
        return self._insert("admin", DBAdminColumns, **kwargs)

    def update_admin(self, admin_id, **kwargs):
        self._update("admin", DBAdminColumns, DBAdminColumns.ID.value, admin_id, **kwargs)

    def fetch_admin(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admin ORDER BY id ASC LIMIT 1")
            return cursor.fetchone()

    def count_admin(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM admin")
            return cursor.fetchone()[0]
