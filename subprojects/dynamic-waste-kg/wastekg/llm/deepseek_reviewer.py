"""提供 DeepSeek 默认配置的大模型复核器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from wastekg.llm.reviewer import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL, LLMReviewerConfig, OpenAICompatibleReviewer

DEFAULT_DEEPSEEK_BASE_URL = DEFAULT_LLM_BASE_URL
DEFAULT_DEEPSEEK_MODEL = DEFAULT_LLM_MODEL


@dataclass(slots=True)
class DeepSeekReviewer(OpenAICompatibleReviewer):
    """DeepSeek 默认配置包装器。

    这个类保留旧调用方式：

    ```python
    reviewer = DeepSeekReviewer()
    ```

    但实际 HTTP 调用、JSON 解析、类别约束都由通用
    `OpenAICompatibleReviewer` 完成。以后如果换模型，优先使用
    `OpenAICompatibleReviewer(LLMReviewerConfig(...))`，不用改感知流水线。
    """

    api_key: Optional[str] = None
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    model: str = DEFAULT_DEEPSEEK_MODEL
    timeout: int = 30
    temperature: float = 0.0
    max_tokens: int = 400

    def __post_init__(self) -> None:
        env_config = LLMReviewerConfig.from_environment(prefix="DEEPSEEK", provider_name="deepseek")
        config = LLMReviewerConfig(
            provider_name="deepseek",
            api_key=self.api_key or env_config.api_key,
            base_url=(self.base_url if self.base_url != DEFAULT_DEEPSEEK_BASE_URL else env_config.base_url).rstrip("/"),
            model=self.model if self.model != DEFAULT_DEEPSEEK_MODEL else env_config.model,
            timeout=self.timeout if self.timeout != 30 else env_config.timeout,
            temperature=self.temperature if self.temperature != 0.0 else env_config.temperature,
            max_tokens=self.max_tokens if self.max_tokens != 400 else env_config.max_tokens,
        )
        self.config = config
