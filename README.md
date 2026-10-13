# Обувной магазин

Курсовая работа. Тема: информационная система обувного магазина.

Автор: Филонов Егор.

Веб-API для учёта ассортимента: модель, бренд, размер, цена и остаток на складе.
Стек: Python, FastAPI, SQLite, Swagger (OpenAPI).

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn shoe_store.main:app --reload
```

На Windows окружение включается так: `.venv\Scripts\activate`.

Swagger открывается по адресу http://127.0.0.1:8000/docs

## Проверки

```bash
ruff check .
pytest
```
