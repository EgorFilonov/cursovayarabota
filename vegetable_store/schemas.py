"""Схемы запросов и ответов овощного магазина."""

from datetime import date

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Новый товар."""

    name: str = Field(min_length=1, max_length=100)
    group_name: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=20)
    purchase_price: int = Field(ge=0)
    sale_price: int = Field(ge=0)


class Product(ProductCreate):
    """Товар, уже записанный в справочник."""

    id: int


class BatchCreate(BaseModel):
    """Приход партии."""

    product_id: int
    received_on: date
    quantity: int = Field(gt=0)


class SaleCreate(BaseModel):
    """Продажа."""

    product_id: int
    sold_on: date
    quantity: int = Field(gt=0)


class WriteOffCreate(BaseModel):
    """Списание брака."""

    product_id: int
    written_off_on: date
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)


class Movement(BaseModel):
    """Остаток и оборот товара на день."""

    product_id: int
    name: str
    group_name: str
    incoming: int
    outgoing: int
    balance: int


class Spoilage(BaseModel):
    """Доля списанного товара от прихода."""

    received: int
    written_off: int
    spoilage_percent: float


class Margin(BaseModel):
    """Маржа товарной группы."""

    group_name: str
    revenue: int
    cost: int
    margin: int
    margin_percent: float
