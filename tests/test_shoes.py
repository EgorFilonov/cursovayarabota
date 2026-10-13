"""Проверки каталога. Каждый тест получает свой файл SQLite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from shoe_store.db import connect, init_db
from shoe_store.main import app, get_db


def _payload(**overrides: object) -> dict:
    data = {
        "name": "Classic Leather",
        "brand": "Ralf",
        "category": "boots",
        "size": 42,
        "color": "black",
        "price": 7500,
        "stock": 4,
    }
    data.update(overrides)
    return data


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    """Подменяет базу на временный файл SQLite."""
    db_path = tmp_path / "shoes.sqlite3"

    def override_db() -> Iterator:
        connection = connect(db_path)
        init_db(connection)
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_root_points_to_swagger(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_catalog_is_empty_at_start(client: TestClient) -> None:
    response = client.get("/shoes")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_read_shoe(client: TestClient) -> None:
    created = client.post("/shoes", json=_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["id"] == 1
    assert body["brand"] == "Ralf"
    assert body["price"] == 7500

    fetched = client.get("/shoes/1")
    assert fetched.status_code == 200
    assert fetched.json() == body

    catalog = client.get("/shoes")
    assert catalog.json() == [body]


def test_missing_shoe_returns_404(client: TestClient) -> None:
    response = client.get("/shoes/99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Модель с таким id не найдена"


def test_negative_price_is_rejected(client: TestClient) -> None:
    response = client.post("/shoes", json=_payload(price=-1))
    assert response.status_code == 422


def test_delete_shoe(client: TestClient) -> None:
    client.post("/shoes", json=_payload())
    deleted = client.delete("/shoes/1")
    assert deleted.status_code == 204
    assert client.get("/shoes/1").status_code == 404
    missing = client.delete("/shoes/1")
    assert missing.status_code == 404


def test_storage_is_sqlite_file(client: TestClient, tmp_path) -> None:
    """Файл базы начинается с заголовка SQLite, не с другой СУБД."""
    created = client.post("/shoes", json=_payload(name="Runner", category="sneakers"))
    assert created.status_code == 201
    db_file = tmp_path / "shoes.sqlite3"
    assert db_file.read_bytes().startswith(b"SQLite format 3")
