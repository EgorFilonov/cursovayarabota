"""Каталог обуви в SQLite."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shoes.sqlite3"

CREATE_SHOES = """
CREATE TABLE IF NOT EXISTS shoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    size REAL NOT NULL,
    color TEXT NOT NULL,
    price INTEGER NOT NULL,
    stock INTEGER NOT NULL
)
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Открывает файл SQLite и включает внешние ключи.

    Args:
        db_path: Путь к файлу базы. Если не передан, берётся data/shoes.sqlite3.

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
    """Создаёт таблицу каталога, если её ещё нет.

    Args:
        connection: Открытое соединение SQLite.
    """
    connection.execute(CREATE_SHOES)
    connection.commit()


def _to_shoe(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "brand": row["brand"],
        "category": row["category"],
        "size": row["size"],
        "color": row["color"],
        "price": row["price"],
        "stock": row["stock"],
    }


def list_shoes(connection: sqlite3.Connection) -> list[dict]:
    """Возвращает все модели по возрастанию id.

    Args:
        connection: Открытое соединение SQLite.

    Returns:
        Список записей каталога. Пустой, если таблица ещё пустая.
    """
    rows = connection.execute(
        """
        SELECT id, name, brand, category, size, color, price, stock
        FROM shoes
        ORDER BY id
        """
    ).fetchall()
    return [_to_shoe(row) for row in rows]


def get_shoe(connection: sqlite3.Connection, shoe_id: int) -> dict | None:
    """Ищет модель по идентификатору.

    Args:
        connection: Открытое соединение SQLite.
        shoe_id: Идентификатор записи.

    Returns:
        Запись каталога или None, если такого id нет.
    """
    row = connection.execute(
        """
        SELECT id, name, brand, category, size, color, price, stock
        FROM shoes
        WHERE id = ?
        """,
        (shoe_id,),
    ).fetchone()
    if row is None:
        return None
    return _to_shoe(row)


def create_shoe(connection: sqlite3.Connection, payload: dict) -> dict:
    """Добавляет модель в каталог.

    Args:
        connection: Открытое соединение SQLite.
        payload: Поля новой модели без id.

    Returns:
        Сохранённая запись вместе с новым id.
    """
    cursor = connection.execute(
        """
        INSERT INTO shoes (name, brand, category, size, color, price, stock)
        VALUES (:name, :brand, :category, :size, :color, :price, :stock)
        """,
        payload,
    )
    connection.commit()
    created = get_shoe(connection, int(cursor.lastrowid))
    if created is None:
        raise RuntimeError("Запись не прочиталась сразу после вставки")
    return created


def delete_shoe(connection: sqlite3.Connection, shoe_id: int) -> bool:
    """Удаляет модель из каталога.

    Args:
        connection: Открытое соединение SQLite.
        shoe_id: Идентификатор записи.

    Returns:
        True, если строка была удалена.
    """
    cursor = connection.execute("DELETE FROM shoes WHERE id = ?", (shoe_id,))
    connection.commit()
    return cursor.rowcount > 0
