"""The one place that talks to the language-model endpoint.

Any OpenAI-compatible chat endpoint works: the official `openai` client is
pointed at your base URL. Nothing here knows about fires; it sends messages and
returns the model's text, and turns every way that can fail into one error type
so the caller has one thing to catch. Secrets come from the environment only.
"""

import os
from dataclasses import dataclass

import openai
from openai.types.chat import ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONObject

Messages = list[ChatCompletionMessageParam]  # the SDK's own message type, so the call checks

REQUIRED = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")


class LLMError(RuntimeError):
    """Anything that went wrong talking to the model: network, status, timeout."""


class LLMConfigError(LLMError):
    """The endpoint is not configured, so the detector cannot be built."""


@dataclass(frozen=True)
class LLMSettings:
    """Where the endpoint is and which model to ask. Read from the environment."""

    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "LLMSettings":
        """LLM_BASE_URL, LLM_API_KEY and LLM_MODEL, all required."""
        missing = [name for name in REQUIRED if not os.environ.get(name)]
        if missing:
            raise LLMConfigError("set " + ", ".join(missing) + " in the environment")
        return cls(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"])


class LLMClient:
    """Sends one chat request and returns the reply text. Async, one connection pool."""

    def __init__(self, settings: LLMSettings, timeout: float = 8.0) -> None:
        """`timeout` is per request, in seconds; one retry on transient failures."""
        self.model = settings.model
        self._client = openai.AsyncOpenAI(
            base_url=settings.base_url, api_key=settings.api_key, timeout=timeout, max_retries=1
        )

    async def complete_json(self, messages: Messages) -> str:
        """Ask for a JSON object and return the raw text of the reply.

        JSON mode is requested first. Some compatible servers reject the
        `response_format` field; those get the same request without it, and the
        prompt's own instruction to answer in JSON has to carry the day.
        """
        try:
            try:
                return await self._create(messages, json_mode=True)
            except openai.BadRequestError:
                return await self._create(messages, json_mode=False)
        except openai.APIError as exc:  # timeouts, connection errors and HTTP errors alike
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    async def _create(self, messages: Messages, json_mode: bool) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            response_format=ResponseFormatJSONObject(type="json_object") if json_mode else openai.omit,
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMError("empty reply")
        return content

    async def aclose(self) -> None:
        await self._client.close()
