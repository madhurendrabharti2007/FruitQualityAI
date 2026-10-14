from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import config


class BackendConfigTests(unittest.TestCase):
    def test_loads_key_from_configured_env_file_without_logging_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("GEMINI_API_KEY=unit-test-value\n", encoding="utf-8")
            with (
                patch.object(config, "BACKEND_ENV_PATH", env_path),
                patch.dict(os.environ, {}, clear=True),
            ):
                config.load_backend_env()
                self.assertTrue(os.getenv("GEMINI_API_KEY"))


if __name__ == "__main__":
    unittest.main()
