import datetime
from typing import Any, Literal

from aiohttp import ClientSession
from async_lru import alru_cache
from disnake.ext import tasks

from .types import Detection, LangCodeAndOrName


class TranslationClient:
    BASE_URL = "https://translation.googleapis.com/language/translate/v2"

    def __init__(self, key: str, session: ClientSession | None = None):
        self.key = key
        self.session = session or ClientSession()
        self._invalidate_language_cache.start()

    async def _api(self, method: str, **params: dict[str, Any]) -> dict[str, Any]:
        return await self.session.fetch_json(
            f"{self.BASE_URL}/{method.strip('/')}", params={"key": self.key, **params}
        )

    async def translate(
        self,
        text: str,
        target: str,
        source: str | None = None,
        format: Literal["text", "html"] = "text",
    ) -> tuple[str, str | None]:
        data = await self._api(
            "/",
            key=self.key,
            q=text,
            target=target,
            source=source or "",
            format=format,
        )
        translations: list[dict[str, str]] = data["data"]["translations"]
        translation = translations[0]
        translated_text = translation["translatedText"]
        detected_source_language = translation.get("detectedSourceLanguage")
        return translated_text, detected_source_language

    async def detect(self, text: str) -> Detection:
        data = await self._api("/detect", q=text)
        detections: list[Detection] = data["data"]["detections"]
        return detections[0]

    @alru_cache(cache_exceptions=False)
    async def languages(self, target: str | None = None) -> list[LangCodeAndOrName]:
        data = await self._api("/languages", target=target or "")
        languages: list[dict[str, str]] = data["data"]["languages"]
        return [list(lang.values()) for lang in languages]

    @tasks.loop(time=datetime.time())
    async def _invalidate_language_cache(self) -> None:
        self.languages.cache_clear()