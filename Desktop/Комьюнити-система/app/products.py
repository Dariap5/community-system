"""Hardcoded products for the MVP."""

PRODUCTS: dict[str, dict[str, object]] = {
    "community": {
        "name": "Доступ в комьюнити",
        "price": 2990,
        "description": "Закрытое комьюнити с материалами и сообществом",
    },
}


def get_product(product_id: str) -> dict[str, object] | None:
    return PRODUCTS.get(product_id)