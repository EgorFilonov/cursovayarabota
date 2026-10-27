# ИС «Овощной магазин»

Курсовая работа. Оперативный учёт скоропортящихся товаров и контроль списаний.

Роли: продавец и товаровед.
Сущности: товар, партия с датой поступления, списание брака, продажа.

Что делает система:

- учитывает приход, расход и остаток на выбранный день;
- считает процент испорченного товара;
- считает маржинальность по товарным группам.

Стек: Python, FastAPI, SQLite, Swagger (OpenAPI).

## Запуск

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn vegetable_store.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

Заголовок роли: `X-Role: seller` для продавца, `X-Role: merchandiser` для товароведа.

## Проверки

```bash
ruff check .
pytest
```
