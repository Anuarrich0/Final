import logging

from groq import Groq

from config import Settings
from prompts import build_prompt
from question_parser import parse_questions


logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = Groq(api_key=settings.groq_api_key)

    async def generate(
        self,
        topic: str,
        num_questions: int,
        difficulty: str,
    ) -> list[dict] | str:
        prompt = build_prompt(topic, num_questions, difficulty)
        max_attempts = 3
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.groq_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.settings.groq_temperature,
                    max_tokens=self.settings.groq_max_tokens,
                )
                raw = response.choices[0].message.content
                questions = parse_questions(raw)
                if questions is not None:
                    return questions[:num_questions]

                last_error = f"Попытка {attempt}: невалидный JSON-формат от модели."
                logger.warning(last_error)
                prompt = (
                    "Предыдущий ответ был неверно отформатирован. "
                    "Попробуй снова строго по схеме.\n\n"
                    + build_prompt(topic, num_questions, difficulty)
                )
            except Exception as exc:
                last_error = f"Ошибка Groq API: {exc}"
                logger.error(last_error)
                break

        return f"❌ Не удалось сгенерировать тест после {max_attempts} попыток.\nПричина: {last_error}"
