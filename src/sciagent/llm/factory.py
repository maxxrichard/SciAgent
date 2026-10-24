from __future__ import annotations

from sciagent.core.config import Settings
from sciagent.llm.base import LLMClient
from sciagent.llm.openai_compat import OpenAICompatibleLLM
from sciagent.llm.rule_based import RuleBasedLLM


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_backend == "vllm":
        return OpenAICompatibleLLM(
            settings.llm_base_url,
            settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            max_tokens=settings.llm_max_tokens,
        )
    return RuleBasedLLM()
