"""Проверки учёта. У каждого теста свой файл SQLite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from vegetable_store.db import connect, init_db
from vegetable_store.main import app, get_db

MERCH = {"X-Role": "merchandiser"}
SELLER = {"X-Role": "seller"}


def _product(**overrides: object) -> dict:
    data = {
        "name": "Картофель",
        "group_name": "Овощи",
        "unit": "кг",
        "purchase_price": 20,
        "sale_price": 40,
    }
    data.update(overrides)
    return data


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    """Подменяет базу на временный файл SQLite."""
    db_path = tmp_path / "store.sqlite3"

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


def test_seller_cannot_receive_batch(client: TestClient) -> None:
    created = client.post("/products", headers=MERCH, json=_product())
    assert created.status_code == 201
    denied = client.post(
        "/batches",
        headers=SELLER,
        json={"product_id": 1, "received_on": "2026-10-01", "quantity": 10},
    )
    assert denied.status_code == 403


def test_stock_sale_and_write_off(client: TestClient) -> None:
    client.post("/products", headers=MERCH, json=_product())
    client.post(
        "/products",
        headers=MERCH,
        json=_product(
            name="Укроп",
            group_name="Зелень",
            purchase_price=30,
            sale_price=70,
        ),
    )
    arrived = client.post(
        "/batches",
        headers=MERCH,
        json={"product_id": 1, "received_on": "2026-10-01", "quantity": 10},
    )
    assert arrived.status_code == 201
    sold = client.post(
        "/sales",
        headers=SELLER,
        json={"product_id": 1, "sold_on": "2026-10-01", "quantity": 4},
    )
    assert sold.status_code == 201
    assert sold.json()["revenue"] == 160
    assert sold.json()["cost"] == 80
    written = client.post(
        "/write-offs",
        headers=MERCH,
        json={
            "product_id": 1,
            "written_off_on": "2026-10-01",
            "quantity": 1,
            "reason": "гниль",
        },
    )
    assert written.status_code == 201
    stock = client.get("/stock", headers=SELLER, params={"on": "2026-10-01"})
    potato = stock.json()[0]
    assert potato["incoming"] == 10
    assert potato["outgoing"] == 5
    assert potato["balance"] == 5
    spoil = client.get("/spoilage", headers=MERCH)
    assert spoil.json()["spoilage_percent"] == 10.0
    margin = client.get("/margin", headers=SELLER).json()
    vegetables = next(row for row in margin if row["group_name"] == "Овощи")
    assert vegetables["margin"] == 80
    assert vegetables["margin_percent"] == 50.0


def test_cannot_sell_more_than_stock(client: TestClient) -> None:
    client.post("/products", headers=MERCH, json=_product())
    client.post(
        "/batches",
        headers=MERCH,
        json={"product_id": 1, "received_on": "2026-10-01", "quantity": 2},
    )
    response = client.post(
        "/sales",
        headers=SELLER,
        json={"product_id": 1, "sold_on": "2026-10-01", "quantity": 3},
    )
    assert response.status_code == 400


def test_earlier_batch_is_sold_first(client: TestClient) -> None:
    client.post(
        "/products",
        headers=MERCH,
        json=_product(purchase_price=10, sale_price=50),
    )
    client.post(
        "/batches",
        headers=MERCH,
        json={"product_id": 1, "received_on": "2026-10-01", "quantity": 2},
    )
    client.post(
        "/batches",
        headers=MERCH,
        json={"product_id": 1, "received_on": "2026-10-02", "quantity": 5},
    )
    sold = client.post(
        "/sales",
        headers=SELLER,
        json={"product_id": 1, "sold_on": "2026-10-02", "quantity": 2},
    )
    assert sold.status_code == 201
    assert sold.json()["cost"] == 20
    stock = client.get("/stock", headers=SELLER, params={"on": "2026-10-02"})
    assert stock.json()[0]["balance"] == 5
