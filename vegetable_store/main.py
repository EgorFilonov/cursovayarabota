"""Точка входа ИС «Овощной магазин»."""

import sqlite3
from collections.abc import Iterator
from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException, status

from vegetable_store.db import (
    connect,
    create_batch,
    create_product,
    create_sale,
    create_write_off,
    init_db,
    list_products,
    margin_by_group,
    spoilage,
    stock_on,
)
from vegetable_store.schemas import (
    BatchCreate,
    Margin,
    Movement,
    Product,
    ProductCreate,
    SaleCreate,
    Spoilage,
    WriteOffCreate,
)

SELLER = "seller"
MERCHANDISER = "merchandiser"

app = FastAPI(
    title="Овощной магазин",
    description=(
        "Оперативный учёт скоропортящихся товаров и контроль списаний. "
        "Роли передаются заголовком X-Role: seller (продавец) "
        "или merchandiser (товаровед)."
    ),
    version="0.1.0",
)


def get_db() -> Iterator[sqlite3.Connection]:
    """Открывает SQLite на время одного запроса.

    Yields:
        Соединение с уже созданными таблицами.
    """
    connection = connect()
    try:
        init_db(connection)
        yield connection
    finally:
        connection.close()


def _role(x_role: str | None) -> str:
    if x_role not in {SELLER, MERCHANDISER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нужен заголовок X-Role: seller или merchandiser",
        )
    return x_role


def _only(role: str, allowed: set[str]) -> None:
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Эту операцию выполняет другая роль",
        )


@app.get("/")
def read_root() -> dict[str, str]:
    """Подсказывает, где лежит описание API.

    Returns:
        Название сервиса и путь к Swagger.
    """
    return {"service": "vegetable-store", "docs": "/docs"}


@app.get("/products", response_model=list[Product])
def read_products(
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> list[dict]:
    """Возвращает справочник товаров.

    Args:
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Список товаров.
    """
    _role(x_role)
    return list_products(connection)


@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def add_product(
    payload: ProductCreate,
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> dict:
    """Добавляет товар. Это делает товаровед.

    Args:
        payload: Название, группа и цены.
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Созданный товар.
    """
    _only(_role(x_role), {MERCHANDISER})
    return create_product(connection, payload.model_dump())


@app.post("/batches", status_code=status.HTTP_201_CREATED)
def add_batch(
    payload: BatchCreate,
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> dict:
    """Оприходует партию. Это делает товаровед.

    Args:
        payload: Товар, дата поступления и количество.
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Созданная партия.

    Raises:
        HTTPException: Товара нет в справочнике.
    """
    _only(_role(x_role), {MERCHANDISER})
    try:
        return create_batch(connection, payload.model_dump())
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        ) from None


@app.post("/sales", status_code=status.HTTP_201_CREATED)
def add_sale(
    payload: SaleCreate,
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> dict:
    """Проводит продажу. Это делает продавец.

    Args:
        payload: Товар, дата и количество.
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Продажа с выручкой и себестоимостью.

    Raises:
        HTTPException: Товара нет или остатка не хватает.
    """
    _only(_role(x_role), {SELLER})
    try:
        return create_sale(connection, payload.model_dump())
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        ) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from None


@app.post("/write-offs", status_code=status.HTTP_201_CREATED)
def add_write_off(
    payload: WriteOffCreate,
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> dict:
    """Списывает брак. Это делает товаровед.

    Args:
        payload: Товар, дата, количество и причина.
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Запись списания.

    Raises:
        HTTPException: Товара нет или остатка не хватает.
    """
    _only(_role(x_role), {MERCHANDISER})
    try:
        return create_write_off(connection, payload.model_dump())
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        ) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from None


@app.get("/stock", response_model=list[Movement])
def read_stock(
    on: date,
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> list[dict]:
    """Возвращает приход, расход и остаток на день.

    Args:
        on: Дата, на конец которой нужен остаток.
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Обороты по каждому товару.
    """
    _role(x_role)
    return stock_on(connection, on.isoformat())


@app.get("/spoilage", response_model=Spoilage)
def read_spoilage(
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> dict:
    """Возвращает процент испорченного товара.

    Args:
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Приход, списание и процент порчи.
    """
    _role(x_role)
    return spoilage(connection)


@app.get("/margin", response_model=list[Margin])
def read_margin(
    connection: sqlite3.Connection = Depends(get_db),
    x_role: str | None = Header(default=None),
) -> list[dict]:
    """Возвращает маржинальность по товарным группам.

    Args:
        connection: Соединение SQLite.
        x_role: Роль сотрудника.

    Returns:
        Выручка, себестоимость и маржа каждой группы.
    """
    _role(x_role)
    return margin_by_group(connection)
