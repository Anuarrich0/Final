import os
import json
import re
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from groq import Groq
import fitz  # PyMuPDF
from docx import Document

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

GROQ_API_KEY = "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"
BOT_TOKEN = "8680671969:AAHJuVwvdORg271SGChVNaZTdvC8a8WgEeA"

groq_client = Groq(api_key=GROQ_API_KEY)

# ─── Состояния сессии ────────────────────────────────────────────────────────

def get_session(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "session" not in context.user_data:
        context.user_data["session"] = {}
    return context.user_data["session"]

def clear_session(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["session"] = {}

# ─── Генерация теста через Groq ──────────────────────────────────────────────

QUESTION_SCHEMA = """
Верни ТОЛЬКО валидный JSON-массив, без пояснений, без markdown-блоков, без лишнего текста.
Формат каждого объекта строго такой:
{
  "question": "Текст вопроса",
  "options": ["A) вариант1", "B) вариант2", "C) вариант3", "D) вариант4"],
  "correct_index": 0,
  "explanation": "Краткое объяснение правильного ответа (1-2 предложения)"
}

Правила:
- correct_index — целое число от 0 до 3 (индекс правильного ответа в массиве options)
- Каждый вопрос имеет ровно 4 варианта: A), B), C), D)
- Только один вариант правильный
- Объяснение — короткое, по делу
- Никаких вложенных структур, только плоский массив объектов
"""

def build_prompt(topic: str, num_questions: int, difficulty: str) -> str:
    diff_map = {"easy": "лёгкий", "medium": "средний", "hard": "сложный"}
    diff_label = diff_map.get(difficulty, "средний")
    return (
        f"Создай тест из {num_questions} вопросов на тему: «{topic}».\n"
        f"Уровень сложности: {diff_label}.\n\n"
        f"{QUESTION_SCHEMA}"
    )

def parse_questions(raw: str) -> list[dict] | None:
    """Извлекает JSON из ответа, возвращает список вопросов или None."""
    raw = raw.strip()
    # Убираем возможные markdown-обёртки
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    # Ищем JSON-массив
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) == 0:
        return None
    # Валидация каждого вопроса
    for item in data:
        if not isinstance(item, dict):
            return None
        if not all(k in item for k in ("question", "options", "correct_index", "explanation")):
            return None
        if not isinstance(item["options"], list) or len(item["options"]) != 4:
            return None
        if not isinstance(item["correct_index"], int) or not (0 <= item["correct_index"] <= 3):
            return None
    return data

async def generate_questions(topic: str, num_questions: int, difficulty: str) -> list[dict] | str:
    """
    Возвращает список вопросов или строку с ошибкой.
    Делает до 3 попыток, если Groq вернул невалидный формат.
    """
    prompt = build_prompt(topic, num_questions, difficulty)
    max_attempts = 3
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
            )
            raw = response.choices[0].message.content
            questions = parse_questions(raw)
            if questions is not None:
                return questions[:num_questions]
            # Невалидный формат — добавим в промпт замечание и повторим
            last_error = f"Попытка {attempt}: невалидный JSON-формат от модели."
            logger.warning(last_error)
            prompt = (
                f"Предыдущий ответ был неверно отформатирован. Попробуй снова строго по схеме.\n\n"
                + build_prompt(topic, num_questions, difficulty)
            )
        except Exception as e:
            last_error = f"Ошибка Groq API: {e}"
            logger.error(last_error)
            break

    return f"❌ Не удалось сгенерировать тест после {max_attempts} попыток.\nПричина: {last_error}"

# ─── Извлечение текста из файлов ─────────────────────────────────────────────

def extract_text_from_pdf(path: str) -> str:
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def extract_text_from_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()

# ─── Вспомогательные UI-функции ──────────────────────────────────────────────

def difficulty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😊 Лёгкий", callback_data="diff_easy"),
            InlineKeyboardButton("🧠 Средний", callback_data="diff_medium"),
            InlineKeyboardButton("🔥 Сложный", callback_data="diff_hard"),
        ]
    ])

def num_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5", callback_data="num_5"),
            InlineKeyboardButton("10", callback_data="num_10"),
            InlineKeyboardButton("15", callback_data="num_15"),
        ]
    ])

def options_keyboard(question: dict, q_index: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(opt, callback_data=f"ans_{q_index}_{i}")]
        for i, opt in enumerate(question["options"])
    ]
    return InlineKeyboardMarkup(buttons)

# ─── Команды ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_session(context)
    await update.message.reply_text(
        "👋 Привет! Я бот для генерации тестов.\n\n"
        "📝 *Как начать:*\n"
        "• Напиши любую тему — я сгенерирую тест\n"
        "• Или пришли файл (PDF, DOCX, TXT) — тест по его содержимому\n\n"
        "📌 /help — подробная справка",
        parse_mode="Markdown",
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Справка по боту*\n\n"
        "*Команды:*\n"
        "• /start — начать заново\n"
        "• /help — эта справка\n\n"
        "*Как работает:*\n"
        "1️⃣ Отправь тему (например: «Французская революция», «Python ООП»)\n"
        "   или файл PDF / DOCX / TXT\n"
        "2️⃣ Выбери количество вопросов и сложность\n"
        "3️⃣ Отвечай на вопросы, нажимая кнопки\n"
        "4️⃣ После каждого ответа — моментальная обратная связь\n"
        "5️⃣ В конце — итоговый результат\n\n"
        "⚡ Данные не сохраняются — каждая сессия одноразовая.",
        parse_mode="Markdown",
    )

# ─── Обработка темы (текстовое сообщение) ────────────────────────────────────

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(context)
    # Если идёт тест — игнорируем лишние сообщения
    if session.get("state") in ("quiz", "choosing_num", "choosing_diff"):
        await update.message.reply_text("⏳ Сначала завершите текущий тест или нажмите /start.")
        return

    topic = update.message.text.strip()
    if len(topic) < 3:
        await update.message.reply_text("⚠️ Тема слишком короткая. Напиши подробнее.")
        return

    session["topic"] = topic
    session["state"] = "choosing_num"
    await update.message.reply_text(
        f"📖 Тема: *{topic}*\n\nСколько вопросов?",
        parse_mode="Markdown",
        reply_markup=num_questions_keyboard(),
    )

# ─── Обработка файлов ─────────────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(context)
    if session.get("state") in ("quiz", "choosing_num", "choosing_diff"):
        await update.message.reply_text("⏳ Сначала завершите текущий тест или нажмите /start.")
        return

    msg = update.message
    document = msg.document

    if document is None:
        await msg.reply_text("⚠️ Пожалуйста, пришли файл как документ (не как фото).")
        return

    filename = document.file_name or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("pdf", "docx", "txt"):
        await msg.reply_text("⚠️ Поддерживаются только PDF, DOCX и TXT файлы.")
        return

    status_msg = await msg.reply_text("⏳ Читаю файл...")

    try:
        tg_file = await document.get_file()
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)

        if ext == "pdf":
            text = extract_text_from_pdf(tmp_path)
        elif ext == "docx":
            text = extract_text_from_docx(tmp_path)
        else:
            text = extract_text_from_txt(tmp_path)

        os.unlink(tmp_path)

        if not text or len(text) < 50:
            await status_msg.edit_text("❌ Не удалось извлечь текст из файла. Попробуй другой файл.")
            return

        # Ограничиваем размер контекста для Groq
        topic = text[:3000]
        session["topic"] = topic
        session["state"] = "choosing_num"
        session["source"] = f"файл «{filename}»"

        await status_msg.edit_text(
            f"✅ Файл прочитан: *{filename}*\n\nСколько вопросов?",
            parse_mode="Markdown",
            reply_markup=num_questions_keyboard(),
        )
    except Exception as e:
        logger.error(f"File handling error: {e}")
        await status_msg.edit_text(f"❌ Ошибка при обработке файла:\n`{e}`", parse_mode="Markdown")

# ─── Обработка Callback-кнопок ────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = get_session(context)
    data = query.data

    # ── Выбор количества вопросов ──
    if data.startswith("num_") and session.get("state") == "choosing_num":
        num = int(data.split("_")[1])
        session["num_questions"] = num
        session["state"] = "choosing_diff"
        await query.edit_message_text(
            f"✅ Вопросов: *{num}*\n\nВыбери уровень сложности:",
            parse_mode="Markdown",
            reply_markup=difficulty_keyboard(),
        )
        return

    # ── Выбор сложности ──
    if data.startswith("diff_") and session.get("state") == "choosing_diff":
        difficulty = data.split("_")[1]
        diff_labels = {"easy": "Лёгкий 😊", "medium": "Средний 🧠", "hard": "Сложный 🔥"}
        session["difficulty"] = difficulty
        session["state"] = "generating"

        await query.edit_message_text(
            f"✅ Сложность: *{diff_labels[difficulty]}*\n\n⏳ Генерирую тест, подожди...",
            parse_mode="Markdown",
        )

        # Генерация
        result = await generate_questions(
            topic=session["topic"],
            num_questions=session["num_questions"],
            difficulty=difficulty,
        )

        if isinstance(result, str):  # Ошибка
            clear_session(context)
            await query.edit_message_text(result)
            return

        session["questions"] = result
        session["current_q"] = 0
        session["correct"] = 0
        session["state"] = "quiz"

        source_label = session.get("source", f"тема «{session['topic'][:60]}»")
        await query.edit_message_text(
            f"🎯 Тест готов!\n"
            f"📚 Источник: {source_label}\n"
            f"❓ Вопросов: {len(result)}\n\n"
            f"Поехали! 🚀"
        )
        await send_question(context, query.message.chat_id)
        return

    # ── Ответ на вопрос ──
    if data.startswith("ans_") and session.get("state") == "quiz":
        parts = data.split("_")
        q_index = int(parts[1])
        chosen = int(parts[2])

        # Защита от повторного нажатия
        if q_index != session.get("current_q"):
            return

        question = session["questions"][q_index]
        correct = question["correct_index"]
        is_correct = chosen == correct

        if is_correct:
            session["correct"] += 1
            result_icon = "✅ Правильно!"
        else:
            result_icon = f"❌ Неверно! Правильный ответ: *{question['options'][correct]}*"

        explanation = question.get("explanation", "")

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"{result_icon}\n\n💡 {explanation}",
            parse_mode="Markdown",
        )

        session["current_q"] += 1

        if session["current_q"] >= len(session["questions"]):
            await show_results(context, query.message.chat_id, session)
        else:
            await send_question(context, query.message.chat_id)

# ─── Отправка вопроса ─────────────────────────────────────────────────────────

async def send_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    session = get_session(context)
    q_index = session["current_q"]
    question = session["questions"][q_index]
    total = len(session["questions"])

    text = (
        f"❓ *Вопрос {q_index + 1} из {total}*\n\n"
        f"{question['question']}"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=options_keyboard(question, q_index),
    )

# ─── Итоговый результат ───────────────────────────────────────────────────────

async def show_results(context: ContextTypes.DEFAULT_TYPE, chat_id: int, session: dict):
    correct = session["correct"]
    total = len(session["questions"])
    pct = round(correct / total * 100)

    if pct >= 80:
        medal = "🥇"
    elif pct >= 60:
        medal = "🥈"
    elif pct >= 40:
        medal = "🥉"
    else:
        medal = "📉"

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"{medal} *Тест завершён!*\n\n"
            f"✅ Правильных ответов: *{correct} из {total}*\n"
            f"📊 Результат: *{pct}%*\n\n"
            f"Напиши новую тему или пришли файл, чтобы начать ещё один тест.\n"
            f"Или нажми /start."
        ),
        parse_mode="Markdown",
    )
    clear_session(context)

# ─── Запуск ───────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Бот запущен.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
