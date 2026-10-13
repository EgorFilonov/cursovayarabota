"""Схемы запросов и ответов каталога."""

from enum import Enum

from pydantic import BaseModel, Field


class ShoeCategory(str, Enum):
    """Тип обуви в каталоге."""

    SNEAKERS = "sneakers"
    BOOTS = "boots"
    SHOES = "shoes"
    SANDALS = "sandals"


class ShoeCreate(BaseModel):
    """Данные новой модели, которые приходят в теле запроса."""

    name: str = Field(min_length=1, max_length=100, examples=["Classic Leather"])
    brand: str = Field(min_length=1, max_length=80, examples=["Ralf"])
    category: ShoeCategory
    size: float = Field(gt=0, le=60, examples=[42])
    color: str = Field(min_length=1, max_length=40, examples=["black"])
    price: int = Field(ge=0, description="Цена в рублях", examples=[7500])
    stock: int = Field(ge=0, examples=[4])


class Shoe(ShoeCreate):
    """Модель обуви, уже записанная в каталог."""

    id: int
