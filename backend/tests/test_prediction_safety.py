from __future__ import annotations

import asyncio
from io import BytesIO
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, UploadFile
from PIL import Image

from app.model import fruit_scope, predict as predict_module
from app.model.fruit_scope import FruitScopeUnavailable, FruitVisionClassifier
from app.routers.image_uploads import save_validated_image


def jpeg_bytes(size: tuple[int, int] = (64, 64)) -> bytes:
    image = Image.new("RGB", size, (220, 30, 20))
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def fruit_payload(**overrides):
    payload = {
        "is_fruit": True,
        "fruit_name": "Apple",
        "quality": "fresh",
        "confidence": 0.95,
        "reason": "An apple is clearly visible.",
    }
    payload.update(overrides)
    return payload


class ImageUploadValidationTests(unittest.TestCase):
    def test_accepts_real_jpeg_even_with_wrong_mime_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "upload.jpg"
            upload = UploadFile(
                filename="not-an-image.txt",
                file=BytesIO(jpeg_bytes()),
                headers={"content-type": "text/plain"},
            )
            asyncio.run(save_validated_image(upload, target))
            with Image.open(target) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (64, 64))

    def test_rejects_corrupt_unsupported_and_tiny_uploads(self) -> None:
        bmp = BytesIO()
        Image.new("RGB", (64, 64)).save(bmp, format="BMP")
        cases = [
            (b"", 400),
            (b"not an image", 400),
            (b"\x89PNG\r\n\x1a\nnot a complete png", 400),
            (bmp.getvalue(), 415),
            (jpeg_bytes((16, 16)), 400),
        ]
        for content, expected_status in cases:
            with self.subTest(expected_status=expected_status, length=len(content)):
                with tempfile.TemporaryDirectory() as directory:
                    upload = UploadFile(filename="upload.jpg", file=BytesIO(content))
                    with self.assertRaises(HTTPException) as error:
                        asyncio.run(save_validated_image(upload, Path(directory) / "upload.jpg"))
                self.assertEqual(error.exception.status_code, expected_status)

    def test_rejects_uploads_larger_than_8_mib(self) -> None:
        upload = UploadFile(filename="large.jpg", file=BytesIO(b"x" * (8 * 1024 * 1024 + 1)))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(save_validated_image(upload, Path(directory) / "large.jpg"))
        self.assertEqual(error.exception.status_code, 413)


class GeminiPredictionTests(unittest.TestCase):
    def test_predictor_makes_one_gemini_request_and_returns_fruit_quality(self) -> None:
        classifier = FruitVisionClassifier()
        predictor = predict_module.FruitPredictor()
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "input.jpg"
            image_path.write_bytes(jpeg_bytes())
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
                patch.object(
                    classifier,
                    "_generate_content",
                    return_value=SimpleNamespace(parsed=fruit_payload()),
                ) as generate,
                patch.object(predict_module, "fruit_vision_classifier", classifier),
            ):
                result = predictor.predict(image_path)

        self.assertEqual(result[:4], ("Apple", "fresh", 95.0, False))
        self.assertEqual(generate.call_count, 1)

    def test_gemini_request_uses_json_schema_model_and_timeout(self) -> None:
        classifier = FruitVisionClassifier()
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(return_value="response")))
        client_factory = Mock(return_value=client)
        options_factory = Mock(return_value="http-options")
        config_factory = Mock(return_value="generation-config")
        thinking_config_factory = Mock(return_value="thinking-config")
        parts = SimpleNamespace(from_bytes=Mock(return_value="image-part"), from_text=Mock(return_value="prompt-part"))
        genai_module = ModuleType("google.genai")
        genai_module.Client = client_factory
        types_module = ModuleType("google.genai.types")
        types_module.HttpOptions = options_factory
        types_module.GenerateContentConfig = config_factory
        types_module.ThinkingConfig = thinking_config_factory
        types_module.ThinkingLevel = SimpleNamespace(MINIMAL="MINIMAL")
        types_module.Part = parts
        google_module = ModuleType("google")
        google_module.genai = genai_module

        with (
            patch.dict(
                sys.modules,
                {
                    "google": google_module,
                    "google.genai": genai_module,
                    "google.genai.types": types_module,
                },
            ),
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
        ):
            response = classifier._generate_content(
                b"jpeg-bytes", "inspect this", "gemini-3.6-flash", 20_000
            )

        self.assertEqual(response, "response")
        options_factory.assert_called_once_with(timeout=20_000)
        thinking_config_factory.assert_called_once_with(thinking_level="MINIMAL")
        config_factory.assert_called_once_with(
            response_mime_type="application/json",
            response_schema=fruit_scope.RESPONSE_SCHEMA,
            thinking_config="thinking-config",
        )
        def contains_additional_properties(value):
            if isinstance(value, dict):
                return any(
                    key in {"additionalProperties", "additional_properties"}
                    or contains_additional_properties(child)
                    for key, child in value.items()
                )
            if isinstance(value, list):
                return any(contains_additional_properties(child) for child in value)
            return False

        self.assertFalse(contains_additional_properties(config_factory.call_args.kwargs["response_schema"]))
        client_factory.assert_called_once_with(api_key="test-key", http_options="http-options")
        client.models.generate_content.assert_called_once_with(
            model="gemini-3.6-flash",
            contents=["image-part", "prompt-part"],
            config="generation-config",
        )

    def test_unsupported_model_skips_thinking_config(self) -> None:
        classifier = FruitVisionClassifier()
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(return_value="response")))
        config_factory = Mock(return_value="generation-config")
        genai_module = ModuleType("google.genai")
        genai_module.Client = Mock(return_value=client)
        types_module = ModuleType("google.genai.types")
        types_module.HttpOptions = Mock(return_value="http-options")
        types_module.GenerateContentConfig = config_factory
        types_module.Part = SimpleNamespace(
            from_bytes=Mock(return_value="image-part"),
            from_text=Mock(return_value="prompt-part"),
        )
        google_module = ModuleType("google")
        google_module.genai = genai_module

        with (
            patch.dict(
                sys.modules,
                {
                    "google": google_module,
                    "google.genai": genai_module,
                    "google.genai.types": types_module,
                },
            ),
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
        ):
            classifier._generate_content(b"jpeg-bytes", "inspect this", "gemini-flash-latest", 20_000)

        self.assertEqual(
            set(config_factory.call_args.kwargs),
            {"response_mime_type", "response_schema"},
        )

    def test_outbound_image_is_resized_and_reencoded_as_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "large.png"
            Image.new("RGB", (1600, 800), (120, 40, 20)).save(source_path, format="PNG")
            encoded = FruitVisionClassifier._prepare_image(source_path)

        with Image.open(BytesIO(encoded)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (1024, 512))

    def test_request_and_total_time_budgets(self) -> None:
        self.assertEqual(fruit_scope.MAX_REQUEST_TIMEOUT_MS, 20_000)
        self.assertEqual(fruit_scope.MAX_TOTAL_SECONDS, 45.0)

    def test_nonfruit_and_low_confidence_never_return_a_fruit_name(self) -> None:
        predictor = predict_module.FruitPredictor()
        for payload in (
            fruit_payload(is_fruit=False, fruit_name="", quality="unknown"),
            fruit_payload(confidence=0.79),
        ):
            with self.subTest(payload=payload), patch.object(
                predict_module.fruit_vision_classifier, "classify", return_value=payload
            ):
                result = predictor.predict(Path("unused.jpg"))
            self.assertIsNone(result[0])
            self.assertEqual(result[1], "not_recognized")
            self.assertIn("This does not look like a fruit / image unclear", result[4])

    def test_confidence_boundary_and_unknown_quality_are_preserved(self) -> None:
        predictor = predict_module.FruitPredictor()
        payload = fruit_payload(confidence=0.8, quality="unknown")
        with patch.object(predict_module.fruit_vision_classifier, "classify", return_value=payload):
            result = predictor.predict(Path("unused.jpg"))
        self.assertEqual(result[:3], ("Apple", "unknown", 80.0))

    def test_nonfruit_payload_is_normalized_to_an_empty_fruit_name(self) -> None:
        result = FruitVisionClassifier._validate_payload(
            fruit_payload(is_fruit=False, fruit_name="Banana", quality="fresh")
        )
        self.assertEqual(result["fruit_name"], "")
        self.assertEqual(result["quality"], "unknown")

    def test_rejects_invalid_or_non_strict_payloads(self) -> None:
        for payload in (
            fruit_payload(confidence=True),
            fruit_payload(confidence=1.1),
            fruit_payload(quality="moldy"),
            fruit_payload(extra="not allowed"),
            fruit_payload(reason=""),
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                FruitVisionClassifier._validate_payload(payload)

    def test_gemini_rate_limit_maps_to_429(self) -> None:
        class RateLimitError(RuntimeError):
            code = 429

        classifier = FruitVisionClassifier()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch.object(classifier, "_models", return_value=("test-model",)),
            patch.object(classifier, "_generate_content", side_effect=RateLimitError("quota")),
            patch.object(fruit_scope.time, "sleep"),
            self.assertLogs("app.model.fruit_scope", level="ERROR"),
            self.assertRaises(FruitScopeUnavailable) as raised,
        ):
            with tempfile.TemporaryDirectory() as directory:
                image_path = Path(directory) / "input.jpg"
                image_path.write_bytes(jpeg_bytes())
                classifier.classify(image_path)
        self.assertEqual(raised.exception.status_code, 429)

    def test_gemini_deadline_maps_to_504(self) -> None:
        class DeadlineError(RuntimeError):
            code = 504

        classifier = FruitVisionClassifier()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch.object(classifier, "_models", return_value=("test-model",)),
            patch.object(classifier, "_generate_content", side_effect=DeadlineError("deadline")),
            patch.object(fruit_scope.time, "sleep"),
            self.assertLogs("app.model.fruit_scope", level="ERROR"),
            self.assertRaises(FruitScopeUnavailable) as raised,
        ):
            with tempfile.TemporaryDirectory() as directory:
                image_path = Path(directory) / "input.jpg"
                image_path.write_bytes(jpeg_bytes())
                classifier.classify(image_path)
        self.assertEqual(raised.exception.status_code, 504)

    def test_missing_api_key_fails_closed(self) -> None:
        classifier = FruitVisionClassifier()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": ""}),
            self.assertLogs("app.model.fruit_scope", level="ERROR") as logs,
            self.assertRaises(FruitScopeUnavailable),
        ):
            classifier.classify(Path("unused.jpg"))
        self.assertIn("missing_or_placeholder_setting=GEMINI_API_KEY", "\n".join(logs.output))

    def test_invalid_api_key_logs_setting_name_without_secret(self) -> None:
        class InvalidKeyError(RuntimeError):
            code = 401

        secret = "private-test-api-key"
        classifier = FruitVisionClassifier()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": secret}),
            patch.object(classifier, "_generate_content", side_effect=InvalidKeyError("API key not valid")),
            self.assertLogs("app.model.fruit_scope", level="ERROR") as logs,
            self.assertRaises(FruitScopeUnavailable),
        ):
            with tempfile.TemporaryDirectory() as directory:
                image_path = Path(directory) / "input.jpg"
                image_path.write_bytes(jpeg_bytes())
                classifier.classify(image_path)

        joined_logs = "\n".join(logs.output)
        self.assertIn("invalid_setting=GEMINI_API_KEY", joined_logs)
        self.assertNotIn(secret, joined_logs)

    def test_bad_request_logs_real_status_and_message_without_setting_label(self) -> None:
        class InvalidArgumentError(RuntimeError):
            code = 400

        classifier = FruitVisionClassifier()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch.object(
                classifier,
                "_generate_content",
                side_effect=InvalidArgumentError('Unknown name "additional_properties"'),
            ),
            self.assertLogs("app.model.fruit_scope", level="ERROR") as logs,
            self.assertRaisesRegex(FruitScopeUnavailable, "Gemini rejected the image request"),
        ):
            with tempfile.TemporaryDirectory() as directory:
                image_path = Path(directory) / "input.jpg"
                image_path.write_bytes(jpeg_bytes())
                classifier.classify(image_path)

        joined_logs = "\n".join(logs.output)
        self.assertIn("status=400", joined_logs)
        self.assertIn("additional_properties", joined_logs)
        self.assertNotIn("invalid_setting=GEMINI_MODEL", joined_logs)

    def test_google_api_key_token_is_redacted_from_upstream_message(self) -> None:
        token = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWX-123456"
        with patch.dict(os.environ, {"GEMINI_API_KEY": "configured-key"}):
            message = fruit_scope._sanitized_exception_message(
                RuntimeError(f"Request rejected for {token}")
            )
        self.assertNotIn(token, message)
        self.assertIn("[REDACTED]", message)

    def test_only_401_and_403_are_mapped_to_api_key_setting(self) -> None:
        classifier = FruitVisionClassifier()
        self.assertEqual(classifier._invalid_setting(RuntimeError("anything"), 401), "GEMINI_API_KEY")
        self.assertEqual(classifier._invalid_setting(RuntimeError("anything"), 403), "GEMINI_API_KEY")
        self.assertIsNone(classifier._invalid_setting(RuntimeError("model not found"), 400))
        for status in (400, 401, 403):
            error = RuntimeError("request failed")
            error.code = status
            self.assertFalse(classifier._is_retryable(error))
        unavailable = RuntimeError("503 UNAVAILABLE: high demand")
        unavailable.code = "UNAVAILABLE"
        self.assertEqual(classifier._upstream_status(unavailable), 503)
        self.assertTrue(classifier._is_retryable(unavailable))

    def test_model_list_reads_ordered_environment_values(self) -> None:
        with patch.dict(os.environ, {"GEMINI_MODELS": " first-model,second-model, first-model "}):
            self.assertEqual(FruitVisionClassifier._models(), ("first-model", "second-model"))
        with patch.dict(os.environ, {"GEMINI_MODELS": ""}):
            self.assertEqual(
                FruitVisionClassifier._models(),
                ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"),
            )

    def test_503_retries_first_model_and_logs_successful_model(self) -> None:
        class ServiceUnavailable(RuntimeError):
            code = 503

        classifier = FruitVisionClassifier()
        response = SimpleNamespace(parsed=fruit_payload())
        calls = []

        def generate(_image_bytes, _prompt, model, timeout_ms):
            calls.append((model, timeout_ms))
            if len(calls) == 1:
                raise ServiceUnavailable("high demand")
            return response

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "input.jpg"
            image_path.write_bytes(jpeg_bytes())
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
                patch.object(classifier, "_models", return_value=("primary-model", "fallback-model")),
                patch.object(classifier, "_generate_content", side_effect=generate),
                patch.object(fruit_scope.time, "sleep") as sleep,
                self.assertLogs("app.model.fruit_scope", level="INFO") as logs,
            ):
                result = classifier.classify(image_path)

        self.assertEqual(result["fruit_name"], "Apple")
        self.assertEqual([model for model, _ in calls], ["primary-model", "primary-model"])
        self.assertTrue(all(0 < timeout_ms <= fruit_scope.MAX_REQUEST_TIMEOUT_MS for _, timeout_ms in calls))
        sleep.assert_called_once_with(1.5)
        self.assertIn("model=primary-model", "\n".join(logs.output))
        self.assertIn("seconds=", "\n".join(logs.output))

    def test_falls_back_after_same_model_retry_fails(self) -> None:
        class ServiceUnavailable(RuntimeError):
            code = 503

        classifier = FruitVisionClassifier()
        calls = []

        def generate(_image_bytes, _prompt, model, _timeout_ms):
            calls.append(model)
            if model == "primary-model":
                raise ServiceUnavailable("high demand")
            return SimpleNamespace(parsed=fruit_payload())

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "input.jpg"
            image_path.write_bytes(jpeg_bytes())
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
                patch.object(classifier, "_models", return_value=("primary-model", "fallback-model")),
                patch.object(classifier, "_generate_content", side_effect=generate),
                patch.object(fruit_scope.time, "sleep"),
            ):
                result = classifier.classify(image_path)

        self.assertEqual(result["fruit_name"], "Apple")
        self.assertEqual(calls, ["primary-model", "primary-model", "fallback-model"])


if __name__ == "__main__":
    unittest.main()