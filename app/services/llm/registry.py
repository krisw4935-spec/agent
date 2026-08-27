"""LLM model registry with pre-initialized instances and reasoning streaming support."""

from typing import (
    Any,
    Dict,
    List,
    Mapping,
    cast,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessageChunk
from langchain_openai import ChatOpenAI
import langchain_openai.chat_models.base as _lc_openai_base
from pydantic import SecretStr

from app.core.config import settings
from app.core.logging import logger

# Preserve reasoning_content from OpenAI/SenseNova/DeepSeek streaming deltas in langchain AIMessageChunk
_original_convert_delta = _lc_openai_base._convert_delta_to_message_chunk


def _patched_convert_delta(
    delta: Mapping[str, Any], default_class: type[BaseMessageChunk]
) -> BaseMessageChunk:
    chunk = _original_convert_delta(delta, default_class)
    if isinstance(chunk, AIMessageChunk):
        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
        if reasoning:
            chunk.additional_kwargs["reasoning_content"] = reasoning
    return chunk


_lc_openai_base._convert_delta_to_message_chunk = _patched_convert_delta

_API_KEY = SecretStr(settings.OPENAI_API_KEY)
_BASE_URL = settings.OPENAI_BASE_URL


def _build_chat_openai(model_name: str, **kwargs: Any) -> ChatOpenAI:
    """Create a ChatOpenAI client pointed at the configured OpenAI-compatible gateway."""
    params: dict[str, Any] = {
        "model": model_name,
        "api_key": _API_KEY,
        "base_url": _BASE_URL,
        "max_completion_tokens": settings.MAX_TOKENS,
        "temperature": settings.DEFAULT_LLM_TEMPERATURE,
    }
    if "max_tokens" in kwargs:
        params.pop("max_completion_tokens", None)
    params.update(kwargs)
    return ChatOpenAI(**params)


def _build_registry_entries() -> List[Dict[str, Any]]:
    """Build ordered model list: default first, then unique fallbacks."""
    names: List[str] = []
    for name in [settings.DEFAULT_LLM_MODEL, *settings.LLM_FALLBACK_MODELS]:
        if name and name not in names:
            names.append(name)
    return [{"name": name, "llm": _build_chat_openai(name)} for name in names]


class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    # Ordered by preference: index 0 is the default and the head of the circular
    # fallback chain, so it degrades newest -> cheapest.
    LLMS: List[Dict[str, Any]] = _build_registry_entries()

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        When kwargs are provided a fresh ChatOpenAI instance is returned with
        those overrides applied, leaving the shared registry entry untouched.

        Args:
            model_name: Name of the model to retrieve.
            **kwargs: Optional arguments to override default model configuration.

        Returns:
            BaseChatModel instance.

        Raises:
            ValueError: If model_name is not found in LLMS.
        """
        model_entry = next((e for e in cls.LLMS if e["name"] == model_name), None)

        if not model_entry:
            available = ", ".join(e["name"] for e in cls.LLMS)
            raise ValueError(f"model '{model_name}' not found in registry. available models: {available}")

        if kwargs:
            base_llm = cast(ChatOpenAI, model_entry["llm"])
            logger.debug(
                "creating_llm_with_custom_args",
                model_name=model_name,
                model=base_llm.model_name,
                custom_args=list(kwargs.keys()),
            )
            return _build_chat_openai(base_llm.model_name, **kwargs)

        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Return all registered model names in order.

        Returns:
            List of model name strings.
        """
        return [e["name"] for e in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Return the model entry at a specific index, wrapping to 0 if out of range.

        Args:
            index: Index into LLMS.

        Returns:
            Model entry dict.
        """
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]
