"""Definizione dello schema SQLite e creazione idempotente delle tabelle.

A differenza di Willow (script ``Create_table_*.py`` lanciati a mano),
qui lo schema e' centralizzato e ``create_schema`` viene invocato dal
bootstrap: se il file DB non esiste, le 5 tabelle vengono create al primo
avvio. Usa ``CREATE TABLE IF NOT EXISTS`` per essere idempotente.
"""

import sqlite3

from Gestionale_Enums import (
    DBAdminColumns,
    DBExpenseSharesColumns,
    DBExpensesColumns,
    DBIncomesColumns,
    DBUsersColumns,
    UserStatus,
    Visibility,
)

C_USERS = DBUsersColumns
C_EXP = DBExpensesColumns
C_SHARE = DBExpenseSharesColumns
C_INC = DBIncomesColumns
C_ADMIN = DBAdminColumns


def _users_table() -> str:
    cols = [
        f"{C_USERS.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
        f"{C_USERS.FIRST_NAME.value} TEXT NOT NULL",
        f"{C_USERS.LAST_NAME.value} TEXT NOT NULL",
        f"{C_USERS.EMAIL.value} TEXT",
        f"{C_USERS.TELEFONO.value} TEXT",
        f"{C_USERS.PHOTO_PATH.value} TEXT",
        f"{C_USERS.PASSWORD_LOGIN.value} TEXT",
        f"{C_USERS.RECOVERY_HASH.value} TEXT",
        f"{C_USERS.DEFAULT_VISIBILITY.value} TEXT NOT NULL DEFAULT '{Visibility.PUBBLICA.value}'",
        f"{C_USERS.STATUS.value} TEXT NOT NULL DEFAULT '{UserStatus.ATTIVO.value}'",
        f"{C_USERS.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"{C_USERS.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"UNIQUE ({C_USERS.FIRST_NAME.value}, {C_USERS.LAST_NAME.value})",
    ]
    return f"CREATE TABLE IF NOT EXISTS users ({', '.join(cols)})"


def _expenses_table() -> str:
    cols = [
        f"{C_EXP.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
        f"{C_EXP.DESCRIPTION.value} TEXT NOT NULL",
        f"{C_EXP.USER_ID.value} INTEGER NOT NULL",
        f"{C_EXP.CATEGORY.value} TEXT NOT NULL",
        f"{C_EXP.MERCHANT.value} TEXT",
        f"{C_EXP.TOTAL_AMOUNT.value} REAL NOT NULL",
        f"{C_EXP.NET_AMOUNT.value} REAL",
        f"{C_EXP.IVA_AMOUNT.value} REAL",
        f"{C_EXP.DATE.value} TIMESTAMP NOT NULL",
        f"{C_EXP.PAYMENT_METHOD.value} TEXT",
        f"{C_EXP.IS_SHARED.value} INTEGER NOT NULL DEFAULT 0",
        f"{C_EXP.ADVANCED_BY_USER_ID.value} INTEGER",
        f"{C_EXP.IS_SETTLED.value} INTEGER NOT NULL DEFAULT 0",
        f"{C_EXP.VISIBILITY.value} TEXT NOT NULL DEFAULT '{Visibility.PUBBLICA.value}'",
        f"{C_EXP.SOURCE.value} TEXT NOT NULL DEFAULT 'MANUALE'",
        f"{C_EXP.NOTE.value} TEXT",
        f"{C_EXP.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"{C_EXP.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"FOREIGN KEY ({C_EXP.USER_ID.value}) REFERENCES users({C_USERS.ID.value})",
        f"FOREIGN KEY ({C_EXP.ADVANCED_BY_USER_ID.value}) REFERENCES users({C_USERS.ID.value})",
    ]
    return f"CREATE TABLE IF NOT EXISTS expenses ({', '.join(cols)})"


def _expense_shares_table() -> str:
    cols = [
        f"{C_SHARE.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
        f"{C_SHARE.EXPENSE_ID.value} INTEGER NOT NULL",
        f"{C_SHARE.USER_ID.value} INTEGER NOT NULL",
        f"{C_SHARE.PERCENTAGE.value} REAL NOT NULL",
        f"{C_SHARE.AMOUNT.value} REAL NOT NULL",
        f"{C_SHARE.IS_SETTLED.value} INTEGER NOT NULL DEFAULT 0",
        f"{C_SHARE.SETTLED_AT.value} TIMESTAMP",
        f"{C_SHARE.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"{C_SHARE.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"FOREIGN KEY ({C_SHARE.EXPENSE_ID.value}) REFERENCES expenses({C_EXP.ID.value}) ON DELETE CASCADE",
        f"FOREIGN KEY ({C_SHARE.USER_ID.value}) REFERENCES users({C_USERS.ID.value})",
        f"UNIQUE ({C_SHARE.EXPENSE_ID.value}, {C_SHARE.USER_ID.value})",
    ]
    return f"CREATE TABLE IF NOT EXISTS expense_shares ({', '.join(cols)})"


def _incomes_table() -> str:
    cols = [
        f"{C_INC.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
        f"{C_INC.DESCRIPTION.value} TEXT NOT NULL",
        f"{C_INC.USER_ID.value} INTEGER NOT NULL",
        f"{C_INC.CATEGORY.value} TEXT NOT NULL",
        f"{C_INC.AMOUNT.value} REAL NOT NULL",
        f"{C_INC.DATE.value} TIMESTAMP NOT NULL",
        f"{C_INC.VISIBILITY.value} TEXT NOT NULL DEFAULT '{Visibility.PUBBLICA.value}'",
        f"{C_INC.SOURCE.value} TEXT NOT NULL DEFAULT 'MANUALE'",
        f"{C_INC.NOTE.value} TEXT",
        f"{C_INC.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"{C_INC.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"FOREIGN KEY ({C_INC.USER_ID.value}) REFERENCES users({C_USERS.ID.value})",
    ]
    return f"CREATE TABLE IF NOT EXISTS incomes ({', '.join(cols)})"


def _admin_table() -> str:
    cols = [
        f"{C_ADMIN.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT",
        f"{C_ADMIN.NAME.value} TEXT NOT NULL DEFAULT 'ADMIN'",
        f"{C_ADMIN.PASSWORD_LOGIN.value} TEXT NOT NULL",
        f"{C_ADMIN.RECOVERY_HASH.value} TEXT NOT NULL",
        f"{C_ADMIN.CREATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        f"{C_ADMIN.UPDATED_AT.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    ]
    return f"CREATE TABLE IF NOT EXISTS admin ({', '.join(cols)})"


ALL_TABLES = (
    _users_table,
    _expenses_table,
    _expense_shares_table,
    _incomes_table,
    _admin_table,
)


def create_schema(db_path: str) -> None:
    """Crea tutte le tabelle se non esistono. Idempotente."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        for table_builder in ALL_TABLES:
            cursor.execute(table_builder())
        conn.commit()
    finally:
        conn.close()
