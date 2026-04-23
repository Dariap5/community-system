from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


MENU_PRODUCTS = "🛍 Продукты"
MENU_MY_SUBS = "📂 Мои подписки"
MENU_SUPPORT = "❓ Поддержка"
MENU_OFFER = "📄 Оферта"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_PRODUCTS), KeyboardButton(text=MENU_MY_SUBS)],
            [KeyboardButton(text=MENU_SUPPORT), KeyboardButton(text=MENU_OFFER)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )