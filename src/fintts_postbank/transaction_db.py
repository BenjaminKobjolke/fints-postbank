"""SQLite database for tracking sent transactions."""

import hashlib
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path


class TransactionDatabase:
    """SQLite database for tracking which transactions have been sent to the API.

    This prevents duplicate submissions when running the update-api mode multiple times.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the transaction database.

        Args:
            db_path: Path to the SQLite database file. Defaults to project root.
        """
        if db_path is None:
            # Default to project root
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / ".fints_transactions.db"

        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_transactions (
                    id INTEGER PRIMARY KEY,
                    fints_username TEXT NOT NULL,
                    transaction_date DATE NOT NULL,
                    amount TEXT NOT NULL,
                    name TEXT NOT NULL,
                    purpose_hash TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(fints_username, transaction_date, amount, purpose_hash)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS last_balance (
                    fints_username TEXT PRIMARY KEY,
                    balance_value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @staticmethod
    def _hash_purpose(purpose: str) -> str:
        """Create a hash of the transaction purpose for deduplication.

        Args:
            purpose: The transaction purpose/description.

        Returns:
            SHA256 hash of the purpose (first 16 chars).
        """
        return hashlib.sha256(purpose.encode("utf-8")).hexdigest()[:16]

    def is_transaction_sent(
        self,
        fints_username: str,
        transaction_date: date,
        amount: Decimal,
        name: str,
        purpose: str,
    ) -> bool:
        """Check if a transaction has already been sent.

        Args:
            fints_username: The FinTS username (for multi-account support).
            transaction_date: The transaction date.
            amount: The transaction amount.
            name: The transaction name/applicant.
            purpose: The transaction purpose/description.

        Returns:
            True if the transaction has already been sent.
        """
        purpose_hash = self._hash_purpose(purpose)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM sent_transactions
                WHERE fints_username = ?
                  AND transaction_date = ?
                  AND amount = ?
                  AND purpose_hash = ?
                LIMIT 1
                """,
                (fints_username, transaction_date.isoformat(), str(amount), purpose_hash),
            )
            return cursor.fetchone() is not None

    def mark_transaction_sent(
        self,
        fints_username: str,
        transaction_date: date,
        amount: Decimal,
        name: str,
        purpose: str,
    ) -> None:
        """Mark a transaction as sent.

        Args:
            fints_username: The FinTS username (for multi-account support).
            transaction_date: The transaction date.
            amount: The transaction amount.
            name: The transaction name/applicant.
            purpose: The transaction purpose/description.
        """
        purpose_hash = self._hash_purpose(purpose)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sent_transactions
                    (fints_username, transaction_date, amount, name, purpose_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fints_username, transaction_date.isoformat(), str(amount), name, purpose_hash),
            )
            conn.commit()

    def get_last_balance(self, fints_username: str) -> Decimal | None:
        """Get the last stored balance for a user.

        Args:
            fints_username: The FinTS username.

        Returns:
            The last balance as Decimal, or None if no balance stored.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT balance_value FROM last_balance WHERE fints_username = ?",
                (fints_username,),
            )
            row = cursor.fetchone()
            return Decimal(row[0]) if row else None

    def update_last_balance(self, fints_username: str, balance_value: Decimal) -> None:
        """Update the stored balance for a user.

        Args:
            fints_username: The FinTS username.
            balance_value: The new balance value.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO last_balance (fints_username, balance_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(fints_username)
                DO UPDATE SET balance_value = excluded.balance_value,
                              updated_at = excluded.updated_at
                """,
                (fints_username, str(balance_value)),
            )
            conn.commit()

    def get_sent_count(self, fints_username: str | None = None) -> int:
        """Get the count of sent transactions.

        Args:
            fints_username: Optional filter by username.

        Returns:
            Number of sent transactions.
        """
        with sqlite3.connect(self.db_path) as conn:
            if fints_username:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM sent_transactions WHERE fints_username = ?",
                    (fints_username,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM sent_transactions")
            result = cursor.fetchone()
            return result[0] if result else 0
