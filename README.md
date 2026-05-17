# 🤖 Quiz Bot — Telegram-бот для генерации тестов

Генерирует интерактивные тесты по теме или содержимому файла с помощью Groq (LLaMA 3).

---

## ⚙️ Установка

### 1. Клонируй / скопируй файлы

Убедись, что в папке есть:
```
bot.py
requirements.txt
```

### 2. Создай виртуальное окружение и установи зависимости

```bash
python -m venv venv
source venv/bin/activate       # Linux / macOS
venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

### 3. Получи токены

| Сервис | Где получить |
|--------|-------------|
| **Telegram Bot Token** | [@BotFather](https://t.me/BotFather) → `/newbot` |
| **Groq API Key** | [console.groq.com](https://console.groq.com) → API Keys |

### 4. Задай переменные окружения

**Linux / macOS:**
```bash
export BOT_TOKEN="ваш_telegram_токен"
export GROQ_API_KEY="ваш_groq_ключ"
```

**Windows (cmd):**
```cmd
set BOT_TOKEN=ваш_telegram_токен
set GROQ_API_KEY=ваш_groq_ключ
```

**Или через `.env` файл** (установи `python-dotenv`):
```
BOT_TOKEN=ваш_telegram_токен
GROQ_API_KEY=ваш_groq_ключ
```
И добавь в начало `bot.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

### 5. Запусти бота

```bash
python bot.py
```

---

## 🚀 Использование

| Действие | Что делать |
|----------|-----------|
| Тест по теме | Напиши тему, например: `Фотосинтез` или `Python decorators` |
| Тест по файлу | Пришли PDF, DOCX или TXT как документ |
| Выбор параметров | Кнопки: количество вопросов (5 / 10 / 15) и сложность |
| Ответ | Нажми на кнопку с вариантом ответа |
| Перезапуск | `/start` |

### Команды
- `/start` — начать / перезапустить
- `/help` — справка

---

## 🏗️ Структура

```
bot.py              — основной файл бота
requirements.txt    — зависимости
```

### Ключевые компоненты `bot.py`

| Функция | Назначение |
|---------|-----------|
| `generate_questions()` | Запрос к Groq, до 3 попыток при невалидном JSON |
| `parse_questions()` | Строгая валидация структуры вопросов |
| `handle_topic()` | Приём темы от пользователя |
| `handle_file()` | Извлечение текста из PDF / DOCX / TXT |
| `handle_callback()` | Обработка всех кнопок (num / diff / ans) |
| `show_results()` | Итоговый экран с результатом |

---

## 🔒 Приватность

Бот работает в режиме **одноразовых сессий**:
- Данные хранятся только в `context.user_data` (оперативная память процесса)
- После завершения теста сессия очищается (`clear_session`)
- Никакая информация не пишется в файлы или базу данных

---

## 🛠️ Зависимости

| Библиотека | Назначение |
|-----------|-----------|
| `python-telegram-bot` | Telegram Bot API |
| `groq` | Groq LLM API (LLaMA 3) |
| `PyMuPDF` | Чтение PDF |
| `python-docx` | Чтение DOCX |
