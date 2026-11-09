"""Тесты для основного приложения."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_read_root() -> None:
    """Проверяет корневой эндпоинт."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Овощной магазин работает"}
