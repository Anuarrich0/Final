from telegram.ext import ContextTypes


def get_session(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "session" not in context.user_data:
        context.user_data["session"] = {}
    return context.user_data["session"]


def clear_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["session"] = {}
