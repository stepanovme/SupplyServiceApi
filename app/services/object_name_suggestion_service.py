import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.mistral_retry import is_mistral_rate_limit, mistral_retry

API_KEY_ENV = "MISTRAL_OBJECT_NAME_API_KEY"
MODEL = "ministral-8b-2512"
SUGGESTIONS_COUNT = 5

PROMPT = (
    "Ты даёшь краткие рабочие названия строительным объектам. По полному названию объекта и виду работ "
    "составь {count} вариантов названия СТРОГО в одном из двух форматов:\n"
    "Формат А: <Улица/переулок/проспект без слов «улица», «переулок», «пр.», «пер.»> дом <номер> - <Работа>\n"
    "Формат Б: <Город> - <Улица/переулок/проспект без слов «улица», «переулок», «пр.», «пер.»> дом <номер> - <Работа>\n"
    "Правила:\n"
    "- Название улицы приводи в именительный падеж, как имя собственное (Конецгорскому -> Конецгорский, "
    "Богдана Хмельницкого остаётся как есть).\n"
    "- Слово «дом» пиши полностью, БЕЗ сокращений («д.», «д»), номер дома сразу после него.\n"
    "- Город пиши полностью, без сокращений («г.», «Арх.» и т.п.), в именительном падеже (Мелитополь, Архангельск).\n"
    "- Не пиши «п.», «пер.», «пр.», «ул.», запятые и никаких других сокращений.\n"
    "- <Работа> - одно короткое слово с большой буквы, обозначающее вид работ "
    "(Оконные работы -> Окна, Кровельные работы -> Кровля, Фасадные работы -> Фасад). "
    "В разных вариантах можно использовать синонимы (например Окна / Остекление), но не выдумывай новых видов работ.\n"
    "- Не добавляй ничего, чего нет во входных данных. Варианты должны различаться форматом (А/Б) и/или синонимом работы.\n"
    "Примеры:\n"
    "Объект: Многоквартирные дома по переулку Конецгорскому г. Архангельска. Дом 4; Работы: Оконные работы ->\n"
    "Конецгорский дом 4 - Окна\n"
    "Архангельск - Конецгорский дом 4 - Окна\n"
    "Объект: Жилое здание многоквартирного дома, расположенного по адресу: Запорожская область, г. Мелитополь, "
    "пр. Богдана Хмельницкого, д. 6; Работы: Кровельные работы ->\n"
    "Богдана Хмельницкого дом 6 - Кровля\n"
    "Мелитополь - Богдана Хмельницкого дом 6 - Кровля\n\n"
    'Верни ТОЛЬКО валидный JSON: {{"suggestions": ["...", "..."]}}\n\n'
    "Полное название объекта: {full_name}\n"
    "Вид работ: {work_type}"
)


class ObjectNameSuggestionService:
    def __init__(self, reference_repo: ReferenceObjectRepository) -> None:
        self.reference_repo = reference_repo

    @staticmethod
    def _get_api_key() -> str:
        api_key = os.getenv(API_KEY_ENV)
        if not api_key:
            load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
            api_key = os.getenv(API_KEY_ENV)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{API_KEY_ENV} is not set",
            )
        return api_key

    @staticmethod
    def _parse_suggestions(content: str) -> list[str]:
        cleaned = (content or "").strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось разобрать ответ модели",
            ) from exc
        items = data.get("suggestions") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Не удалось разобрать ответ модели")
        result: list[str] = []
        for item in items:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result

    def suggest(
        self,
        object_id: str | None = None,
        work_type_id: str | None = None,
        full_name: str | None = None,
        work_type_name: str | None = None,
    ):
        full_name = (full_name or "").strip() or None
        work_type_name = (work_type_name or "").strip() or None

        if not full_name:
            if not object_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Передайте object_id или full_name",
                )
            objects = self.reference_repo.get_objects_by_ids([object_id])
            if not objects:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
            full_name = objects[0].full_name or objects[0].short_name
            if not full_name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У объекта не заполнено название")

        if not work_type_name and work_type_id:
            work_types = self.reference_repo.get_work_types_by_ids([work_type_id])
            if not work_types:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work type not found")
            work_type_name = work_types[0].name

        try:
            from mistralai import Mistral
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mistralai package is not installed",
            ) from exc

        client = Mistral(api_key=self._get_api_key())
        prompt = PROMPT.format(
            count=SUGGESTIONS_COUNT,
            full_name=full_name,
            work_type=work_type_name or "не указан",
        )
        try:
            response = mistral_retry(
                client.chat.complete,
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
                throttle_key="object_name",
            )
        except Exception as exc:
            if is_mistral_rate_limit(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Сервис генерации временно перегружен. Попробуйте ещё раз через минуту.",
                ) from exc
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Не удалось сгенерировать названия") from exc

        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)

        return {
            "object_id": object_id,
            "full_name": full_name,
            "work_type_id": work_type_id,
            "work_type_name": work_type_name,
            "suggestions": self._parse_suggestions(content),
        }
