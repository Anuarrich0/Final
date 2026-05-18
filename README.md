# Quiz Bot

Telegram-бот, который делает тесты по теме или по содержимому файла. Для генерации вопросов используется Groq.

Поддерживаются файлы:

- PDF
- DOCX
- TXT

## Установка

Создать виртуальное окружение и поставить зависимости:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Для Windows активация окружения:

```cmd
venv\Scripts\activate
```

## Настройка

Создать файл `.env` в корне проекта. Можно взять за основу `.env.example`.

Минимально нужны два значения:

```env
BOT_TOKEN=telegram_bot_token
GROQ_API_KEY=groq_api_key
```

Дополнительные настройки:

```env
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TEMPERATURE=0.7
GROQ_MAX_TOKENS=4096
MAX_FILE_CONTEXT_CHARS=3000
```

`BOT_TOKEN` создается через BotFather в Telegram. `GROQ_API_KEY` берется в кабинете Groq.

## Запуск

```bash
python bot.py
```

После запуска бот слушает сообщения через polling.

## Как пользоваться

Отправить боту тему, например:

```text
Python decorators
```

Или отправить документ PDF, DOCX или TXT. После этого бот предложит выбрать количество вопросов и сложность.

Команды:

- `/start` - начать заново
- `/help` - справка

## Структура проекта

```text
bot.py              точка входа
config.py           настройки и .env
handlers.py         обработчики Telegram
llm.py              запросы к Groq
prompts.py          текст промпта
question_parser.py  проверка ответа модели
file_extractors.py  чтение файлов
keyboards.py        inline-кнопки
session.py          состояние пользователя
requirements.txt    зависимости
```

## Примечания

Состояние пользователя хранится только в памяти процесса через `context.user_data`.

Файл `.env` не нужно коммитить. Для примера настроек есть `.env.example`.
