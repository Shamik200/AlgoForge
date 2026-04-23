"""SQLite persistence layer for the OMS."""

import json
import sqlite3
from pathlib import Path

from algoforge.oms.models import Order, OrderStatus, OrderType


class OrderStore:
    """SQLite-backed order persistence for crash recovery and audit trail."""

    def __init__(self, db_path: str = "oms_orders.db") -> None:
        """Initialize the store and ensure the schema exists.

        Args:
            db_path: Path to the SQLite database file. Use ":memory:" for testing.
        """
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        """Create the orders table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                correlation_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                order_type TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                status TEXT NOT NULL,
                max_candles INTEGER NOT NULL,
                elapsed_candles INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def save_order(self, order: Order) -> None:
        """Insert a new order into the database.

        Args:
            order: The Order to persist.
        """
        self._conn.execute(
            """INSERT INTO orders
               (correlation_id, symbol, direction, order_type, price, quantity,
                status, max_candles, elapsed_candles, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order.correlation_id,
                order.symbol,
                order.direction,
                order.order_type.value,
                order.price,
                order.quantity,
                order.status.value,
                order.max_candles,
                order.elapsed_candles,
                order.created_at.isoformat(),
                order.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def update_order(self, order: Order) -> None:
        """Update an existing order in the database.

        Args:
            order: The Order with updated fields.
        """
        self._conn.execute(
            """UPDATE orders SET
               status = ?, elapsed_candles = ?, updated_at = ?
               WHERE correlation_id = ?""",
            (
                order.status.value,
                order.elapsed_candles,
                order.updated_at.isoformat(),
                order.correlation_id,
            ),
        )
        self._conn.commit()

    def get_active_orders(self) -> list[Order]:
        """Load all non-terminal orders from the database.

        Returns:
            List of active Order objects.
        """
        cursor = self._conn.execute(
            "SELECT * FROM orders WHERE status NOT IN (?, ?, ?)",
            (OrderStatus.FILLED.value, OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value),
        )
        return [self._row_to_order(row) for row in cursor.fetchall()]

    def get_order_by_correlation_id(self, correlation_id: str) -> Order | None:
        """Look up a single order by its correlation ID.

        Args:
            correlation_id: The unique correlation identifier.

        Returns:
            The Order if found, else None.
        """
        cursor = self._conn.execute(
            "SELECT * FROM orders WHERE correlation_id = ?",
            (correlation_id,),
        )
        row = cursor.fetchone()
        return self._row_to_order(row) if row else None

    def _row_to_order(self, row: sqlite3.Row) -> Order:
        """Convert a database row into an Order object."""
        from datetime import datetime
        return Order(
            correlation_id=row["correlation_id"],
            symbol=row["symbol"],
            direction=row["direction"],
            order_type=OrderType(row["order_type"]),
            price=row["price"],
            quantity=row["quantity"],
            status=OrderStatus(row["status"]),
            max_candles=row["max_candles"],
            elapsed_candles=row["elapsed_candles"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
