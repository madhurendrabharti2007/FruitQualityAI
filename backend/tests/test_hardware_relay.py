from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from jose import jwt
from PIL import Image

from app import main
from app.routers import auth, predict


def jpeg_bytes() -> bytes:
    image = Image.new("RGB", (64, 64), (220, 30, 20))
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


class FakeDatabase:
    def add(self, _record) -> None:
        pass

    def commit(self) -> None:
        pass

    def get(self, _model, user_id: int):
        return type("AuthenticatedUser", (), {"id": user_id})()


class HardwareRelayTests(unittest.TestCase):
    def setUp(self) -> None:
        with predict.hardware_state_lock:
            predict.last_command = None
            predict.last_ir.update({"object_detected": False, "updated_at": None})
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.client.close()
        main.app.dependency_overrides.clear()

    def test_hardware_prediction_publishes_accept_and_reject_commands(self) -> None:
        predictions = [
            ("Apple", "fresh", 95.0, False, "", []),
            (None, "not_recognized", 79.0, False, "unclear", []),
            ("Orange", "fresh", 79.0, False, "", []),
        ]

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"HARDWARE_DEVICE_KEY": "test-device-key"}),
            patch.object(predict, "UPLOADS", Path(directory)),
            patch.object(predict.predictor, "predict", side_effect=predictions),
            patch.object(predict, "_ripeness", return_value=("ripe", "2-4 days")),
        ):
            headers = {"X-Device-Key": "test-device-key"}
            expected_commands = (
                (1, "accept", "Apple", "fresh"),
                (2, "reject", "", "unknown"),
                (3, "reject", "Orange", "fresh"),
            )
            for expected_id, expected_action, fruit_name, quality in expected_commands:
                response = self.client.post(
                    "/api/hardware-predict",
                    headers=headers,
                    files={"file": ("fruit.jpg", jpeg_bytes(), "image/jpeg")},
                )
                self.assertEqual(response.status_code, 200)
                command = self.client.get("/api/hardware/command", headers=headers)
                self.assertEqual(
                    command.json(),
                    {
                        "id": expected_id,
                        "action": expected_action,
                        "fruit_name": fruit_name,
                        "quality": quality,
                    },
                )

    def test_device_auth_rejects_missing_placeholder_and_wrong_keys(self) -> None:
        for environment, supplied_key, expected_status in (
            ({}, "anything", 503),
            ({"HARDWARE_DEVICE_KEY": "esp32-cam-default-key"}, "esp32-cam-default-key", 503),
            ({"HARDWARE_DEVICE_KEY": "real-secret"}, "wrong-secret", 401),
        ):
            with self.subTest(expected_status=expected_status), patch.dict(
                os.environ, environment, clear=True
            ):
                response = self.client.get(
                    "/api/hardware/command",
                    headers={"X-Device-Key": supplied_key},
                )
            self.assertEqual(response.status_code, expected_status)

    def test_signed_in_prediction_publishes_a_command(self) -> None:
        main.app.dependency_overrides[predict.get_db] = lambda: FakeDatabase()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"HARDWARE_DEVICE_KEY": "test-device-key"}),
            patch.object(predict, "UPLOADS", Path(directory)),
            patch.object(predict, "current_user", return_value=SimpleNamespace(id=7)),
            patch.object(predict.predictor, "predict", return_value=("Banana", "fresh", 92.0, False, "", [])),
            patch.object(predict, "_ripeness", return_value=("ripe", "2-4 days")),
            patch.object(predict, "_info", return_value={"title": "Fresh Banana", "points": [], "disposal_tip": None}),
        ):
            response = self.client.post(
                "/api/predict",
                files={"file": ("fruit.jpg", jpeg_bytes(), "image/jpeg")},
            )
            command = self.client.get(
                "/api/hardware/command",
                headers={"X-Device-Key": "test-device-key"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            command.json(),
            {"id": 1, "action": "accept", "fruit_name": "Banana", "quality": "fresh"},
        )

    def test_failed_hardware_prediction_does_not_publish_a_command(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"HARDWARE_DEVICE_KEY": "test-device-key"}),
            patch.object(predict, "UPLOADS", Path(directory)),
            patch.object(predict.predictor, "predict", side_effect=RuntimeError("classifier failed")),
        ):
            response = self.client.post(
                "/api/hardware-predict",
                headers={"X-Device-Key": "test-device-key"},
                files={"file": ("fruit.jpg", jpeg_bytes(), "image/jpeg")},
            )
            command = self.client.get(
                "/api/hardware/command",
                headers={"X-Device-Key": "test-device-key"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(command.json(), {"id": 0, "action": "none"})

    def test_ir_update_and_logged_in_status_support_bearer_without_cookies(self) -> None:
        device_headers = {"X-Device-Key": "test-device-key"}
        with patch.dict(os.environ, {"HARDWARE_DEVICE_KEY": "test-device-key"}):
            update = self.client.post(
                "/api/hardware/ir",
                headers=device_headers,
                json={"object_detected": True},
            )
            invalid_update = self.client.post(
                "/api/hardware/ir",
                headers=device_headers,
                json={"object_detected": "true"},
            )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(invalid_update.status_code, 422)

        token = jwt.encode(
            {"sub": "7", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            auth.SECRET_KEY,
            algorithm=auth.ALGORITHM,
        )
        main.app.dependency_overrides[auth.get_db] = lambda: FakeDatabase()
        status = self.client.get(
            "/api/hardware/ir-status",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["object_detected"], True)
        self.assertIsInstance(status.json()["seconds_since_update"], (int, float))

    def test_command_starts_empty_and_device_cors_allows_key_header(self) -> None:
        with patch.dict(os.environ, {"HARDWARE_DEVICE_KEY": "test-device-key"}):
            command = self.client.get(
                "/api/hardware/command",
                headers={"X-Device-Key": "test-device-key"},
            )
        self.assertEqual(command.json(), {"id": 0, "action": "none"})

        preflight = self.client.options(
            "/api/hardware/command",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-device-key",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertIn("x-device-key", preflight.headers["access-control-allow-headers"])


if __name__ == "__main__":
    unittest.main()
