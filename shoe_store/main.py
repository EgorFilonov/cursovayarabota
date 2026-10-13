"""Точка входа веб-API обувного магазина."""

import sqlite3
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, status

from shoe_store.db import (
    connect,
    create_shoe,
    delete_shoe,
    get_shoe,
    init_db,
    list_shoes,
)
from shoe_store.schemas import Shoe, ShoeCreate

app = FastAPI(
    title="Обувной магазин",
    description="Учёт ассортимента: модель, бренд, размер, цена и остаток на складе.",
    version="0.1.0",
)


def get_db() -> Iterator[sqlite3.Connection]:
    """Открывает SQLite на время одного запроса.

    Yields:
        Соединение с уже созданной таблицей каталога.
    """
    connection = connect()
    try:
        init_db(connection)
        yield connection
    finally:
        connection.close()


@app.get("/")
def read_root() -> dict[str, str]:
    """Подсказывает, где лежит описание API.

    Returns:
        Название сервиса и путь к Swagger.
    """
    return {"service": "shoe-store", "docs": "/docs"}


@app.get("/shoes", response_model=list[Shoe])
def read_shoes(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """Возвращает каталог обуви.

    Args:
        connection: Соединение SQLite для этого запроса.

    Returns:
        Список моделей. Пустой, если в базе ещё ничего нет.
    """
    return list_shoes(connection)


@app.get("/shoes/{shoe_id}", response_model=Shoe)
def read_shoe(shoe_id: int, connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """Возвращает одну модель.

    Args:
        shoe_id: Идентификатор записи.
        connection: Соединение SQLite для этого запроса.

    Returns:
        Запись каталога.

    Raises:
        HTTPException: Модели с таким id нет.
    """
    shoe = get_shoe(connection, shoe_id)
    if shoe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Модель с таким id не найдена",
        )
    return shoe


@app.post("/shoes", response_model=Shoe, status_code=status.HTTP_201_CREATED)
def add_shoe(
    payload: ShoeCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Добавляет модель в каталог.

    Args:
        payload: Название, бренд, размер, цена и остаток.
        connection: Соединение SQLite для этого запроса.

    Returns:
        Созданная запись с идентификатором.
    """
    return create_shoe(connection, payload.model_dump(mode="json"))


@app.delete("/shoes/{shoe_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_shoe(shoe_id: int, connection: sqlite3.Connection = Depends(get_db)) -> None:
    """Удаляет модель из каталога.

    Args:
        shoe_id: Идентификатор записи.
        connection: Соединение SQLite для этого запроса.

    Raises:
        HTTPException: Модели с таким id нет.
    """
    deleted = delete_shoe(connection, shoe_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Модель с таким id не найдена",
        )
