import re
import json
import asyncio
import google.generativeai as genai
from app.configs.settings import settings
from app.errors.exceptions import GeminiException

genai.configure(api_key=settings.gemini_api_key)


class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def _generate_content_sync(self, prompt: str) -> dict:
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        text = response.text

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            raise GeminiException("Gemini 응답을 JSON으로 파싱할 수 없습니다")

    async def generate_content(self, prompt: str) -> dict:
        try:
            return await asyncio.to_thread(self._generate_content_sync, prompt)
        except GeminiException:
            raise
        except Exception as e:
            raise GeminiException(f"Gemini API 호출 실패: {str(e)}")

    async def analyze_code(self, prompt: str) -> dict:
        return await self.generate_content(prompt)


gemini_service = GeminiService()
