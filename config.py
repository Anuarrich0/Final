import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.7
    groq_max_tokens: int = 4096
    max_file_context_chars: int = 3000


def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    missing = [
        name
        for name, value in (
            ("BOT_TOKEN", bot_token),
            ("GROQ_API_KEY", groq_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Не заданы переменные окружения: "
            + ", ".join(missing)
            + ". Заполни .env или экспортируй их перед запуском."
        )

    return Settings(
        bot_token=bot_token,
        groq_api_key=groq_api_key,
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
        groq_temperature=float(os.getenv("GROQ_TEMPERATURE", "0.7")),
        groq_max_tokens=int(os.getenv("GROQ_MAX_TOKENS", "4096")),
        max_file_context_chars=int(os.getenv("MAX_FILE_CONTEXT_CHARS", "3000")),
    )
