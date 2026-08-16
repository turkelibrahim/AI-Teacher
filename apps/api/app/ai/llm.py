from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger("canli_ogretmen.ai.llm")

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a blocking response given a list of chat messages.
        Format of messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        pass

    @abstractmethod
    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response given a list of chat messages.
        """
        pass


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=float(settings.LLM_TIMEOUT)
        )
        self.model_name = settings.LLM_MODEL_NAME
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise e

    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            raise e


# Mock Provider for Testing
class MockLLMProvider(BaseLLMProvider):
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        return "This is a mocked response based on your context."

    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        yield "This "
        yield "is a "
        yield "mocked stream."


def get_llm_provider(mock: bool = False) -> BaseLLMProvider:
    if mock or settings.APP_ENV == "testing":
        return MockLLMProvider()
    return OpenAICompatibleProvider()
