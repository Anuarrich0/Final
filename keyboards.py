from telegram import InlineKeyboardButton, InlineKeyboardMarkup


MAX_BUTTON_TEXT_BYTES = 64


def utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def truncate_utf8(text: str, max_bytes: int = MAX_BUTTON_TEXT_BYTES) -> str:
    if utf8_len(text) <= max_bytes:
        return text

    suffix = "..."
    available = max_bytes - utf8_len(suffix)
    if available <= 0:
        return suffix[:max_bytes]

    result = []
    used = 0
    for char in text:
        char_len = utf8_len(char)
        if used + char_len > available:
            break
        result.append(char)
        used += char_len

    return "".join(result).rstrip() + suffix


def difficulty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("😊 Лёгкий", callback_data="diff_easy"),
                InlineKeyboardButton("🧠 Средний", callback_data="diff_medium"),
                InlineKeyboardButton("🔥 Сложный", callback_data="diff_hard"),
            ]
        ]
    )


def num_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("5", callback_data="num_5"),
                InlineKeyboardButton("10", callback_data="num_10"),
                InlineKeyboardButton("15", callback_data="num_15"),
            ]
        ]
    )


def options_keyboard(question: dict, q_index: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(truncate_utf8(opt), callback_data=f"ans_{q_index}_{index}")]
        for index, opt in enumerate(question["options"])
    ]
    return InlineKeyboardMarkup(buttons)
