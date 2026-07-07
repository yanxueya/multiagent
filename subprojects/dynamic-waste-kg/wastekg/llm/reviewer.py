"""实现 OpenAI-compatible 大模型视觉复核器。"""

from __future__ import annotations

import base64
import importlib
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from wastekg.perception.pipeline import ReviewResult
from wastekg.core.taxonomy import canonicalize_category_name

DEFAULT_LLM_BASE_URL = "https://api.deepseek.com"
DEFAULT_LLM_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _clamp_confidence(value: Any, fallback: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, numeric))


def _parse_json_object(text: str) -> Dict[str, Any]:
    # 大模型返回可能包裹在 Markdown fence 或 box 标签中，先抽出 JSON 主体再解析。
    content = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()
    boxed = re.match(r"^<\|begin_of_box\|>\s*(.*?)\s*<\|end_of_box\|>$", content, re.DOTALL)
    if boxed:
        content = boxed.group(1).strip()
    if not content.startswith("{"):
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    return json.loads(content)


def _parse_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # 只解析简单 KEY=VALUE，避免把注释和空行误认为配置。
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _env_file_values() -> Dict[str, str]:
    path = Path(os.getenv("LLM_ENV_FILE") or DEFAULT_ENV_PATH)
    return _parse_env_file(path)


def _first_non_empty(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _parse_bool(value: Any, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _local_config_value(name: str, default: Any = None) -> Any:
    """Read optional user-only config from wastekg/local_llm_config.py.

    That file is ignored by git and is intended for a beginner-friendly local API
    key placeholder. Environment variables still take priority.
    """

    try:
        module = importlib.import_module("wastekg.local_llm_config")
    except ModuleNotFoundError:
        return default
    return getattr(module, name, default)


@dataclass(slots=True)
class LLMReviewerConfig:
    provider_name: str = "openai_compatible"
    api_key: Optional[str] = None
    base_url: str = DEFAULT_LLM_BASE_URL
    model: str = DEFAULT_LLM_MODEL
    timeout: int = 30
    temperature: float = 0.0
    max_tokens: int = 400
    response_format_json: bool = True
    disable_thinking: bool = True

    @classmethod
    def from_environment(cls, *, prefix: str = "LLM", provider_name: str = "openai_compatible") -> "LLMReviewerConfig":
        # 配置优先级：环境变量 > .env > 本地忽略文件 > 默认值。
        env_file = _env_file_values()
        return cls(
            provider_name=provider_name,
            api_key=_first_non_empty(
                os.getenv(f"{prefix}_API_KEY"),
                os.getenv("LLM_API_KEY"),
                env_file.get(f"{prefix}_API_KEY"),
                env_file.get("LLM_API_KEY"),
                _local_config_value("API_KEY"),
            ),
            base_url=_first_non_empty(
                os.getenv(f"{prefix}_BASE_URL")
                or os.getenv("LLM_BASE_URL"),
                env_file.get(f"{prefix}_BASE_URL"),
                env_file.get("LLM_BASE_URL"),
                _local_config_value("BASE_URL"),
                default=DEFAULT_LLM_BASE_URL,
            ).rstrip("/"),
            model=_first_non_empty(
                os.getenv(f"{prefix}_MODEL"),
                os.getenv("LLM_MODEL"),
                env_file.get(f"{prefix}_MODEL"),
                env_file.get("LLM_MODEL"),
                _local_config_value("MODEL"),
                default=DEFAULT_LLM_MODEL,
            ),
            timeout=int(
                _first_non_empty(
                    os.getenv(f"{prefix}_TIMEOUT"),
                    os.getenv("LLM_TIMEOUT"),
                    env_file.get(f"{prefix}_TIMEOUT"),
                    env_file.get("LLM_TIMEOUT"),
                    _local_config_value("TIMEOUT", 30),
                )
            ),
            temperature=float(
                _first_non_empty(
                    os.getenv(f"{prefix}_TEMPERATURE"),
                    os.getenv("LLM_TEMPERATURE"),
                    env_file.get(f"{prefix}_TEMPERATURE"),
                    env_file.get("LLM_TEMPERATURE"),
                    _local_config_value("TEMPERATURE", 0.0),
                )
            ),
            max_tokens=int(
                _first_non_empty(
                    os.getenv(f"{prefix}_MAX_TOKENS"),
                    os.getenv("LLM_MAX_TOKENS"),
                    env_file.get(f"{prefix}_MAX_TOKENS"),
                    env_file.get("LLM_MAX_TOKENS"),
                    _local_config_value("MAX_TOKENS", 400),
                )
            ),
            response_format_json=_parse_bool(
                _first_non_empty(
                    os.getenv(f"{prefix}_RESPONSE_FORMAT_JSON"),
                    os.getenv("LLM_RESPONSE_FORMAT_JSON"),
                    env_file.get(f"{prefix}_RESPONSE_FORMAT_JSON"),
                    env_file.get("LLM_RESPONSE_FORMAT_JSON"),
                    _local_config_value("RESPONSE_FORMAT_JSON", True),
                ),
                default=True,
            ),
        )


@dataclass(slots=True)
class OpenAICompatibleReviewer:
    """通用 OpenAI-compatible 大模型复核器。

    只要服务商提供 `/chat/completions` 兼容接口，就可以通过更换
    `base_url`、`model`、`api_key` 来复用，不需要改 YOLO 或知识图谱逻辑。
    """

    config: Optional[LLMReviewerConfig] = None

    def __post_init__(self) -> None:
        self.config = self.config or LLMReviewerConfig.from_environment()

    def review(
        self,
        crop_or_image_ref: Any,
        *,
        yolo_class_name: str,
        yolo_confidence: float,
        allowed_classes: List[str],
    ) -> ReviewResult:
        if self.config is None or not self.config.api_key:
            raise RuntimeError(
                "缺少大模型 API key。请设置 LLM_API_KEY 环境变量，"
                "或在 wastekg/local_llm_config.py 中填写 API_KEY。"
            )

        payload = self._build_payload(
            crop_or_image_ref,
            yolo_class_name=yolo_class_name,
            yolo_confidence=yolo_confidence,
            allowed_classes=allowed_classes,
        )
        response = self._post_chat_completion(payload)
        return self._review_result_from_response(response, yolo_class_name=yolo_class_name, allowed_classes=allowed_classes)

    def _build_payload(
        self,
        crop_or_image_ref: Any,
        *,
        yolo_class_name: str,
        yolo_confidence: float,
        allowed_classes: List[str],
    ) -> Dict[str, Any]:
        assert self.config is not None
        allowed = ", ".join(allowed_classes)
        visual_paths = _visual_evidence_paths(crop_or_image_ref)
        user_prompt = (
            "请复核一个建筑废弃物目标的类别。"
            "你只能从 allowed_classes 中选择 class_name，不能创造新类别。"
            "如果存在未知材料、玻璃碎片、危险板材等安全风险，请保守标记 need_human_review=true。"
            "请只返回 JSON，不要解释。\n\n"
            f"allowed_classes: {allowed}\n"
            f"yolo_class_name: {canonicalize_category_name(yolo_class_name)}\n"
            f"yolo_confidence: {float(yolo_confidence):.4f}\n"
            f"crop_or_image_ref: {crop_or_image_ref!r}\n\n"
            "返回 JSON 格式："
            '{"class_name": "...", "confidence": 0.0, "risk_hint": "low|medium|high|unknown", '
            '"need_human_review": true, "reason": "..."}'
        )
        user_content: Any = user_prompt
        if visual_paths:
            # 有原图/裁剪图/mask 证据时走多模态复核；否则退回纯文本复核。
            visual_prompt = (
                "你是建筑废弃物分拣系统的视觉属性抽取器和一致性校验器。"
                "你将收到同一实例的原始场景图、扩边裁剪图和 mask 高亮图。"
                "不要自由识别物体类别，也不要创造新类别。"
                "请先提取颜色、透明度、光泽、表面纹理、边缘形态、形状线索等结构化视觉属性，"
                "再判断这些属性是否支持 YOLO 的类别假设。"
                "若图像证据不足、属性与 YOLO 类别冲突或存在安全风险，请选择 uncertain 并要求人工复核。请只返回 JSON。\n\n"
                f"allowed_classes: {allowed}\n"
                f"yolo_class_name: {canonicalize_category_name(yolo_class_name)}\n"
                f"yolo_confidence: {float(yolo_confidence):.4f}\n\n"
                "返回 JSON 格式："
                '{"decision": "agree|change|uncertain", "proposed_class": "...", "confidence": 0.0, '
                '"requires_human_review": true, '
                '"visual_attributes": {"color": "...", "transparency": "...", "gloss": "...", '
                '"surface_texture": "...", "edge_shape": "...", "shape_cue": "..."}, '
                '"consistency": "support|conflict|insufficient", "reason": "..."}'
            )
            user_content = [{"type": "text", "text": visual_prompt}]
            user_content.extend(
                {"type": "image_url", "image_url": {"url": _image_data_url(path)}} for path in visual_paths
            )
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是建筑废弃物分拣系统的安全复核器，任务是保守复核 YOLO 的分类结果。",
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.response_format_json:
            payload["response_format"] = {"type": "json_object"}
        if self.config.disable_thinking and _is_siliconflow_base_url(self.config.base_url):
            payload["enable_thinking"] = False
        elif self.config.disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        return payload

    def _post_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        assert self.config is not None
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            hint = ""
            if exc.code == 401:
                # 认证失败通常来自 key/base_url 不匹配，这里给出可操作的排查方向。
                hint = (
                    "\n排查建议：当前 API key 未通过认证。请确认 LLM_API_KEY 是否填错；"
                    "如果使用中转站 token，LLM_BASE_URL 必须填写中转站地址，而不是官方地址；"
                    "如果使用官方 key，LLM_BASE_URL 必须填写官方地址。"
                )
            raise RuntimeError(f"{self.config.provider_name} API 请求失败：HTTP {exc.code} {detail}{hint}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.config.provider_name} API 网络连接失败：{exc.reason}") from exc

    def _review_result_from_response(
        self,
        response: Dict[str, Any],
        *,
        yolo_class_name: str,
        allowed_classes: List[str],
    ) -> ReviewResult:
        content = response["choices"][0]["message"]["content"]
        data = _parse_json_object(content)
        yolo_class = canonicalize_category_name(yolo_class_name)
        allowed = {canonicalize_category_name(item) for item in allowed_classes}

        # The visual-review protocol is deliberately conservative: only an
        # explicit, whitelisted ``change`` may alter the YOLO category.
        if "decision" in data:
            decision = str(data.get("decision", "")).strip().lower()
            reason = str(data.get("reason", ""))
            proposed_class = canonicalize_category_name(str(data.get("proposed_class", "")))
            requires_human_review = bool(data.get("requires_human_review", False))
            if decision == "uncertain":
                # 不确定结果不能覆盖 YOLO，只能降低置信度并转人工复核。
                return ReviewResult(
                    class_name=yolo_class,
                    confidence=0.0,
                    risk_hint="unknown",
                    reason=reason or "Visual evidence is insufficient for a safe category decision.",
                    need_human_review=True,
                    decision="uncertain",
                )
            if decision == "agree":
                return ReviewResult(
                    class_name=yolo_class,
                    confidence=_clamp_confidence(data.get("confidence")),
                    risk_hint="unknown",
                    reason=reason,
                    need_human_review=requires_human_review,
                    decision="agree",
                )
            if decision == "change" and proposed_class in allowed:
                return ReviewResult(
                    class_name=proposed_class,
                    confidence=_clamp_confidence(data.get("confidence")),
                    risk_hint="unknown",
                    reason=reason,
                    need_human_review=requires_human_review,
                    decision="change",
                )
            return ReviewResult(
                class_name=yolo_class,
                confidence=0.0,
                risk_hint="unknown",
                reason=reason or f"Invalid visual review decision or proposed class: {decision}/{proposed_class}",
                need_human_review=True,
                decision="invalid",
            )
        class_name = canonicalize_category_name(str(data.get("class_name", "")))
        if class_name not in set(allowed_classes):
            return ReviewResult(
                class_name=canonicalize_category_name(yolo_class_name),
                confidence=0.0,
                risk_hint="unknown",
                reason=f"大模型返回了不在允许类别中的结果：{class_name}",
                need_human_review=True,
            )
        return ReviewResult(
            class_name=class_name,
            confidence=_clamp_confidence(data.get("confidence")),
            risk_hint=str(data.get("risk_hint", "unknown")),
            reason=str(data.get("reason", "")),
            need_human_review=bool(data.get("need_human_review", False)),
        )


def _is_siliconflow_base_url(base_url: str) -> bool:
    return "api.siliconflow.cn" in base_url.lower()


def _visual_evidence_paths(value: Any) -> list[Path]:
    if not isinstance(value, dict):
        return []
    evidence = value.get("visual_evidence", value)
    if not isinstance(evidence, dict):
        return []
    keys = ("crop_image", "mask_overlay_image")
    if evidence.get("send_original_image", True):
        keys = ("original_image",) + keys
    if not all(evidence.get(key) for key in keys):
        return []
    paths = [Path(str(evidence[key])) for key in keys]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        # 视觉证据缺失时直接失败，避免大模型在无图条件下伪装成视觉复核。
        raise FileNotFoundError(f"视觉复核证据文件不存在：{', '.join(missing)}")
    return paths


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    if not mime_type.startswith("image/"):
        raise ValueError(f"视觉复核证据不是图像文件：{path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
