"""Минимальное FastAPI-приложение для ИС «Овощной магазин»."""

from fastapi import FastAPI

app = FastAPI(title="ИС «Овощной магазин»")


@app.get("/")
def read_root() -> dict[str, str]:
    """Корневой эндпоинт."""
    return {"message": "Овощной магазин работает"}
