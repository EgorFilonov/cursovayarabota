"""Учёт партий, продаж и списаний в SQLite."""

import sqlite3
from datetime import date
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "store.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    purchase_price INTEGER NOT NULL,
    sale_price INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    received_on TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    quantity_left INTEGER NOT NULL,
    purchase_price INTEGER NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    sold_on TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    revenue INTEGER NOT NULL,
    cost INTEGER NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS write_offs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    written_off_on TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Открывает файл SQLite.

    Args:
        db_path: Путь к базе. Если не передан, берётся data/store.sqlite3.

    Returns:
        Соединение, в котором строка читается по имени столбца.
    """
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    """Создаёт таблицы, если их ещё нет.

    Args:
        connection: Открытое соединение SQLite.
    """
    connection.executescript(SCHEMA)
    connection.commit()


def create_product(connection: sqlite3.Connection, payload: dict) -> dict:
    """Добавляет товар в справочник.

    Args:
        connection: Открытое соединение SQLite.
        payload: Название, группа, единица и цены.

    Returns:
        Запись товара с новым id.
    """
    connection.execute(
        """
        INSERT INTO products (name, group_name, unit, purchase_price, sale_price)
        VALUES (:name, :group_name, :unit, :purchase_price, :sale_price)
        """,
        payload,
    )
    product_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    connection.commit()
    product = get_product(connection, product_id)
    if product is None:
        raise RuntimeError("Товар не прочитался после записи")
    return product


def list_products(connection: sqlite3.Connection) -> list[dict]:
    """Возвращает справочник товаров.

    Args:
        connection: Открытое соединение SQLite.

    Returns:
        Список товаров по возрастанию id.
    """
    rows = connection.execute(
        """
        SELECT id, name, group_name, unit, purchase_price, sale_price
        FROM products
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_product(connection: sqlite3.Connection, product_id: int) -> dict | None:
    """Ищет товар по id.

    Args:
        connection: Открытое соединение SQLite.
        product_id: Идентификатор товара.

    Returns:
        Запись товара или None.
    """
    row = connection.execute(
        """
        SELECT id, name, group_name, unit, purchase_price, sale_price
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def create_batch(connection: sqlite3.Connection, payload: dict) -> dict:
    """Оприходует партию.

    Args:
        connection: Открытое соединение SQLite.
        payload: Товар, дата поступления и количество.

    Returns:
        Созданная партия.

    Raises:
        KeyError: Такого товара нет.
    """
    product = get_product(connection, payload["product_id"])
    if product is None:
        raise KeyError(payload["product_id"])
    received_on = _as_day(payload["received_on"])
    connection.execute(
        """
        INSERT INTO batches (
            product_id, received_on, quantity, quantity_left, purchase_price
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            payload["product_id"],
            received_on,
            payload["quantity"],
            payload["quantity"],
            product["purchase_price"],
        ),
    )
    batch_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    connection.commit()
    row = connection.execute(
        """
        SELECT id, product_id, received_on, quantity, quantity_left, purchase_price
        FROM batches
        WHERE id = ?
        """,
        (batch_id,),
    ).fetchone()
    return dict(row)


def _consume(
    connection: sqlite3.Connection,
    product_id: int,
    day: str,
    quantity: int,
) -> int:
    left = quantity
    cost = 0
    rows = connection.execute(
        """
        SELECT id, quantity_left, purchase_price
        FROM batches
        WHERE product_id = ? AND quantity_left > 0 AND received_on <= ?
        ORDER BY received_on, id
        """,
        (product_id, day),
    ).fetchall()
    for row in rows:
        if left == 0:
            break
        take = min(left, int(row["quantity_left"]))
        connection.execute(
            "UPDATE batches SET quantity_left = quantity_left - ? WHERE id = ?",
            (take, row["id"]),
        )
        cost += take * int(row["purchase_price"])
        left -= take
    if left > 0:
        connection.rollback()
        raise ValueError("Недостаточно остатка")
    return cost


def create_sale(connection: sqlite3.Connection, payload: dict) -> dict:
    """Списывает товар в продажу по самым ранним партиям.

    Args:
        connection: Открытое соединение SQLite.
        payload: Товар, дата и количество.

    Returns:
        Продажа с выручкой и себестоимостью.

    Raises:
        KeyError: Такого товара нет.
        ValueError: На эту дату остатка не хватает.
    """
    product = get_product(connection, payload["product_id"])
    if product is None:
        raise KeyError(payload["product_id"])
    sold_on = _as_day(payload["sold_on"])
    cost = _consume(connection, payload["product_id"], sold_on, payload["quantity"])
    revenue = payload["quantity"] * product["sale_price"]
    connection.execute(
        """
        INSERT INTO sales (product_id, sold_on, quantity, revenue, cost)
        VALUES (?, ?, ?, ?, ?)
        """,
        (payload["product_id"], sold_on, payload["quantity"], revenue, cost),
    )
    sale_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    connection.commit()
    row = connection.execute(
        """
        SELECT id, product_id, sold_on, quantity, revenue, cost
        FROM sales
        WHERE id = ?
        """,
        (sale_id,),
    ).fetchone()
    return dict(row)


def create_write_off(connection: sqlite3.Connection, payload: dict) -> dict:
    """Списывает брак с самых ранних партий.

    Args:
        connection: Открытое соединение SQLite.
        payload: Товар, дата, количество и причина.

    Returns:
        Запись списания.

    Raises:
        KeyError: Такого товара нет.
        ValueError: На эту дату остатка не хватает.
    """
    if get_product(connection, payload["product_id"]) is None:
        raise KeyError(payload["product_id"])
    written_off_on = _as_day(payload["written_off_on"])
    _consume(
        connection,
        payload["product_id"],
        written_off_on,
        payload["quantity"],
    )
    connection.execute(
        """
        INSERT INTO write_offs (product_id, written_off_on, quantity, reason)
        VALUES (?, ?, ?, ?)
        """,
        (
            payload["product_id"],
            written_off_on,
            payload["quantity"],
            payload["reason"],
        ),
    )
    write_off_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    connection.commit()
    row = connection.execute(
        """
        SELECT id, product_id, written_off_on, quantity, reason
        FROM write_offs
        WHERE id = ?
        """,
        (write_off_id,),
    ).fetchone()
    return dict(row)


def stock_on(connection: sqlite3.Connection, day: str) -> list[dict]:
    """Считает приход, расход и остаток на конец дня.

    Args:
        connection: Открытое соединение SQLite.
        day: Дата в формате ГГГГ-ММ-ДД.

    Returns:
        Строка на каждый товар.
    """
    result = []
    for product in list_products(connection):
        product_id = product["id"]
        incoming = _sum(connection, "batches", "received_on", product_id, day, False)
        sales = _sum(connection, "sales", "sold_on", product_id, day, False)
        written = _sum(
            connection, "write_offs", "written_off_on", product_id, day, False
        )
        incoming_total = _sum(
            connection, "batches", "received_on", product_id, day, True
        )
        sales_total = _sum(connection, "sales", "sold_on", product_id, day, True)
        written_total = _sum(
            connection, "write_offs", "written_off_on", product_id, day, True
        )
        result.append(
            {
                "product_id": product_id,
                "name": product["name"],
                "group_name": product["group_name"],
                "incoming": incoming,
                "outgoing": sales + written,
                "balance": incoming_total - sales_total - written_total,
            }
        )
    return result


def spoilage(connection: sqlite3.Connection) -> dict:
    """Считает процент списанного товара от всего прихода.

    Args:
        connection: Открытое соединение SQLite.

    Returns:
        Приход, списание и процент порчи.
    """
    received = connection.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM batches"
    ).fetchone()[0]
    written_off = connection.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM write_offs"
    ).fetchone()[0]
    percent = 0.0 if received == 0 else round(written_off * 100 / received, 2)
    return {
        "received": received,
        "written_off": written_off,
        "spoilage_percent": percent,
    }


def margin_by_group(connection: sqlite3.Connection) -> list[dict]:
    """Считает маржу по товарным группам.

    Args:
        connection: Открытое соединение SQLite.

    Returns:
        Выручка, себестоимость и процент маржи для каждой группы.
    """
    rows = connection.execute(
        """
        SELECT
            p.group_name AS group_name,
            COALESCE(SUM(s.revenue), 0) AS revenue,
            COALESCE(SUM(s.cost), 0) AS cost
        FROM products AS p
        LEFT JOIN sales AS s ON s.product_id = p.id
        GROUP BY p.group_name
        ORDER BY p.group_name
        """
    ).fetchall()
    report = []
    for row in rows:
        revenue = int(row["revenue"])
        cost = int(row["cost"])
        margin = revenue - cost
        percent = 0.0 if revenue == 0 else round(margin * 100 / revenue, 2)
        report.append(
            {
                "group_name": row["group_name"],
                "revenue": revenue,
                "cost": cost,
                "margin": margin,
                "margin_percent": percent,
            }
        )
    return report


def _sum(
    connection: sqlite3.Connection,
    table: str,
    day_column: str,
    product_id: int,
    day: str,
    until: bool,
) -> int:
    sign = "<=" if until else "="
    query = (
        f"SELECT COALESCE(SUM(quantity), 0) FROM {table} "
        f"WHERE product_id = ? AND {day_column} {sign} ?"
    )
    return int(connection.execute(query, (product_id, day)).fetchone()[0])


def _as_day(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value
