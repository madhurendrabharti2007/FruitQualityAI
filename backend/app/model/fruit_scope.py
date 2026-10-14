"""Gemini Vision classification for fruit identity and quality."""
from __future__ import annotations

import json
import logging
import os
import re
from io import BytesIO
from pathlib import Path
import time
from typing import Any

from app.config import load_backend_env
from pydantic import BaseModel, ConfigDict, Field, model_validator
from PIL import Image, ImageOps

load_backend_env()

logger = logging.getLogger(__name__)
MIN_CONFIDENCE = 0.8
UNCLEAR_IMAGE_MESSAGE = (
    "This does not look like a fruit / image unclear. Please upload a clear fruit photo."
)
QUALITY_LABELS = {"fresh", "rotten", "unknown"}
DEFAULT_GEMINI_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
)
MAX_TOTAL_SECONDS = 45.0
MAX_REQUEST_TIMEOUT_MS = 20_000
RETRY_DELAY_SECONDS = 1.5
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_fruit": {"type": "BOOLEAN"},
        "fruit_name": {"type": "STRING"},
        "quality": {"type": "STRING", "enum": ["fresh", "rotten", "unknown"]},
        "confidence": {"type": "NUMBER"},
        "reason": {"type": "STRING"},
    },
    "required": ["is_fruit", "fruit_name", "quality", "confidence", "reason"],
}


def _sanitized_exception_message(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    message = re.sub(
        r"(?i)(\b(?:api[_ -]?key|key)\s*[:=]\s*)[^\s,;&]+",
        r"\1[REDACTED]",
        message,
    )
    message = re.sub(r"(?i)([?&](?:api_key|key)=)[^&\s]+", r"\1[REDACTED]", message)
    message = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", message)
    message = re.sub(r"\bAIza[^\s,;&\"'<>]+", "[REDACTED]", message)
    return message[:300] or "<empty exception message>"


class FruitScopeUnavailable(RuntimeError):
    """Raised when Gemini classification cannot be performed."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    is_fruit: bool
    fruit_name: str = Field(max_length=80)
    quality: str = Field(pattern=r"^(fresh|rotten|unknown)$")
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_classification(self) -> ClassificationResponse:
        if self.is_fruit and not self.fruit_name.strip():
            raise ValueError("Gemini response did not include a valid fruit name.")
        if not self.reason.strip():
            raise ValueError("Gemini response did not include a reason.")
        return self


class FruitVisionClassifier:
    @staticmethod
    def _supports_thinking_level(model: str) -> bool:
        return model.casefold().startswith("gemini-3")

    @staticmethod
    def _prepare_image(image_path: str | Path) -> bytes:
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=85)
        return output.getvalue()

    @staticmethod
    def _models() -> tuple[str, ...]:
        configured = tuple(
            dict.fromkeys(
                model.strip()
                for model in os.getenv("GEMINI_MODELS", "").split(",")
                if model.strip()
            )
        )
        return configured or DEFAULT_GEMINI_MODELS

    @staticmethod
    def _api_key_or_raise() -> str:
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key or api_key.casefold().startswith(("your-", "change-this", "replace-me")):
            logger.error("Gemini configuration error: missing_or_placeholder_setting=GEMINI_API_KEY")
            raise FruitScopeUnavailable(
                "Supported-fruit validation is unavailable because GEMINI_API_KEY is not configured."
            )
        return api_key

    @staticmethod
    def _invalid_setting(exc: Exception, upstream_status: int | None) -> str | None:
        if upstream_status in {401, 403}:
            return "GEMINI_API_KEY"
        return None

    def _gemini_response_to_dict(self, response: Any) -> dict[str, Any]:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, dict):
            return parsed
        if hasattr(parsed, "model_dump"):
            parsed = parsed.model_dump()
            if isinstance(parsed, dict):
                return parsed
        text = getattr(response, "text", None)
        if text:
            payload = json.loads(str(text))
            if isinstance(payload, dict):
                return payload
        raise ValueError("Gemini returned an empty or invalid JSON response.")

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
        parsed = ClassificationResponse.model_validate(payload)
        return {
            "is_fruit": parsed.is_fruit,
            "fruit_name": parsed.fruit_name.strip().title() if parsed.is_fruit else "",
            "quality": parsed.quality if parsed.is_fruit else "unknown",
            "confidence": parsed.confidence,
            "reason": parsed.reason.strip(),
        }

    def _generate_content(
        self, image_bytes: bytes, prompt: str, model: str, timeout_ms: int
    ) -> Any:
        from google import genai
        from google.genai import types

        api_key = self._api_key_or_raise()
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        config = {
            "response_mime_type": "application/json",
            "response_schema": RESPONSE_SCHEMA,
        }
        if self._supports_thinking_level(model):
            config["thinking_config"] = types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            )
        return client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(**config),
        )

    @staticmethod
    def _upstream_status(exc: Exception) -> int | None:
        candidates = (
            getattr(exc, "status_code", None),
            getattr(getattr(exc, "response", None), "status_code", None),
            getattr(exc, "code", None),
        )
        for raw_status in candidates:
            try:
                return int(raw_status)
            except (TypeError, ValueError):
                continue
        match = re.search(r"\b(400|401|403|408|429|503|504)\b", str(exc))
        return int(match.group(1)) if match else None

    @classmethod
    def _is_retryable(cls, exc: Exception) -> bool:
        status = cls._upstream_status(exc)
        if status in {400, 401, 403}:
            return False
        if status in {408, 429, 503, 504}:
            return True
        text = f"{type(exc).__name__} {exc}".casefold()
        return any(marker in text for marker in ("timeout", "timed out", "deadline"))

    def classify(self, image_path: str | Path) -> dict[str, Any]:
        self._api_key_or_raise()

        prompt = (
            "Inspect the image and return exactly the requested JSON fields. Decide whether the main "
            "visible subject is a fruit, identify its common fruit name, and assess visible quality "
            "as fresh, rotten, or unknown. Use unknown when quality cannot be judged. Confidence is "
            "your overall confidence from 0 to 1. If the image is not a fruit, set is_fruit=false, "
            "fruit_name to an empty string, and quality to unknown. Keep reason short."
        )
        last_error: Exception | None = None
        deadline = time.monotonic() + MAX_TOTAL_SECONDS
        image_bytes = self._prepare_image(image_path)
        try:
            for model in self._models():
                for attempt in range(2):
                    if attempt:
                        remaining = deadline - time.monotonic()
                        if remaining <= RETRY_DELAY_SECONDS:
                            break
                        time.sleep(RETRY_DELAY_SECONDS)

                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    timeout_ms = max(
                        1,
                        min(MAX_REQUEST_TIMEOUT_MS, int(remaining * 1000)),
                    )
                    attempt_started = time.monotonic()
                    try:
                        response = self._generate_content(
                            image_bytes, prompt, model, timeout_ms
                        )
                        result = self._validate_payload(
                            self._gemini_response_to_dict(response)
                        )
                        logger.info(
                            "Gemini prediction succeeded: model=%s attempt=%s seconds=%.2f",
                            model,
                            attempt + 1,
                            time.monotonic() - attempt_started,
                        )
                        return result
                    except FruitScopeUnavailable:
                        raise
                    except Exception as exc:
                        last_error = exc
                        retryable = self._is_retryable(exc)
                        logger.warning(
                            "Gemini attempt failed: model=%s attempt=%s seconds=%.2f "
                            "status=%s retryable=%s exception_type=%s message=%s",
                            model,
                            attempt + 1,
                            time.monotonic() - attempt_started,
                            self._upstream_status(exc) or "unknown",
                            retryable,
                            type(exc).__name__,
                            _sanitized_exception_message(exc),
                        )
                        if not retryable:
                            raise

            if last_error is not None:
                raise last_error
            raise TimeoutError("Gemini classification exceeded its 45-second time budget.")
        except FruitScopeUnavailable:
            raise
        except Exception as exc:
            upstream_status = self._upstream_status(exc)
            logger.error(
                "Gemini upstream error: status=%s exception_type=%s message=%s",
                upstream_status if upstream_status is not None else "unknown",
                type(exc).__name__,
                _sanitized_exception_message(exc),
            )
            invalid_setting = self._invalid_setting(exc, upstream_status)
            if invalid_setting:
                logger.error(
                    "Gemini configuration error: invalid_setting=%s upstream_status=%s",
                    invalid_setting,
                    upstream_status,
                )
            if upstream_status == 429:
                message, status_code = (
                    "The image validation service is busy. Please wait a moment and retry.", 429
                )
            elif upstream_status in {408, 504} or "timeout" in type(exc).__name__.casefold() or "deadline" in str(exc).casefold():
                message, status_code = "Image validation timed out. Please try again shortly.", 504
            elif upstream_status in {401, 403}:
                message, status_code = (
                    "Image validation is misconfigured on the server. Please contact the administrator.",
                    503,
                )
            elif upstream_status == 400:
                message, status_code = (
                    "Gemini rejected the image request. Please try another image or try again later.",
                    503,
                )
            elif (upstream_status is not None and upstream_status >= 500) or any(
                marker in type(exc).__name__.casefold()
                for marker in ("connect", "network", "transport")
            ):
                message, status_code = (
                    "The image validation service is temporarily unavailable. Please try again shortly.",
                    503,
                )
            else:
                message, status_code = (
                    "Supported-fruit validation failed. Please upload a clearer image or try again later.",
                    503,
                )
            raise FruitScopeUnavailable(message, status_code=status_code) from exc


fruit_vision_classifier = FruitVisionClassifier()