import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from config import Settings
from file_extractors import SUPPORTED_EXTENSIONS, extract_text
from keyboards import MAX_BUTTON_TEXT_BYTES, difficulty_keyboard, num_questions_keyboard, options_keyboard, utf8_len
from llm import QuestionGenerator
from session import clear_session, get_session


logger = logging.getLogger(__name__)


def get_question_generator(context: ContextTypes.DEFAULT_TYPE) -> QuestionGenerator:
    return context.application.bot_data["question_generator"]


def get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_session(context)
    await update.message.reply_text(
        "👋 Привет! Я бот для генерации тестов.\n\n"
        "📝 *Как начать:*\n"
        "• Напиши любую тему — я сгенерирую тест\n"
        "• Или пришли файл (PDF, DOCX, TXT) — тест по его содержимому\n\n"
        "📌 /help — подробная справка",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(context)
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


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        await msg.reply_text("⚠️ Поддерживаются только PDF, DOCX и TXT файлы.")
        return

    status_msg = await msg.reply_text("⏳ Читаю файл...")
    tmp_path = None

    try:
        tg_file = await document.get_file()
        with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)

        text = extract_text(tmp_path, extension)
        if not text or len(text) < 50:
            await status_msg.edit_text("❌ Не удалось извлечь текст из файла. Попробуй другой файл.")
            return

        settings = get_settings(context)
        session["topic"] = text[: settings.max_file_context_chars]
        session["state"] = "choosing_num"
        session["source"] = f"файл «{filename}»"

        await status_msg.edit_text(
            f"✅ Файл прочитан: *{filename}*\n\nСколько вопросов?",
            parse_mode="Markdown",
            reply_markup=num_questions_keyboard(),
        )
    except Exception as exc:
        logger.error("File handling error: %s", exc)
        await status_msg.edit_text(f"❌ Ошибка при обработке файла:\n`{exc}`", parse_mode="Markdown")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    session = get_session(context)
    data = query.data

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

    if data.startswith("diff_") and session.get("state") == "choosing_diff":
        difficulty = data.split("_")[1]
        diff_labels = {"easy": "Лёгкий 😊", "medium": "Средний 🧠", "hard": "Сложный 🔥"}
        session["difficulty"] = difficulty
        session["state"] = "generating"

        await query.edit_message_text(
            f"✅ Сложность: *{diff_labels[difficulty]}*\n\n⏳ Генерирую тест, подожди...",
            parse_mode="Markdown",
        )

        result = await get_question_generator(context).generate(
            topic=session["topic"],
            num_questions=session["num_questions"],
            difficulty=difficulty,
        )

        if isinstance(result, str):
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

    if data.startswith("ans_") and session.get("state") == "quiz":
        _, q_index_raw, chosen_raw = data.split("_")
        q_index = int(q_index_raw)
        chosen = int(chosen_raw)

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


async def send_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    session = get_session(context)
    q_index = session["current_q"]
    question = session["questions"][q_index]
    total = len(session["questions"])
    options = question["options"]
    has_long_options = any(utf8_len(option) > MAX_BUTTON_TEXT_BYTES for option in options)

    text = f"❓ *Вопрос {q_index + 1} из {total}*\n\n{question['question']}"
    if has_long_options:
        text += "\n\n" + "\n".join(options)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=options_keyboard(question, q_index),
    )


async def show_results(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    session: dict,
) -> None:
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
