"""Predict fruit identity and visible quality with one Gemini Vision call."""
from __future__ import annotations

from pathlib import Path

from app.model.fruit_scope import (
    MIN_CONFIDENCE,
    UNCLEAR_IMAGE_MESSAGE,
    fruit_vision_classifier,
)

NOT_RECOGNIZED_MESSAGE = UNCLEAR_IMAGE_MESSAGE
BLURRY_MESSAGE = UNCLEAR_IMAGE_MESSAGE


class FruitPredictor:
    def predict(
        self, image_path: Path
    ) -> tuple[str | None, str, float, bool, str, list[tuple[str, float]]]:
        """Return fruit, quality, confidence percent, demo flag, message, and alternatives."""
        result = fruit_vision_classifier.classify(image_path)
        confidence = result["confidence"]
        if not result["is_fruit"] or confidence < MIN_CONFIDENCE:
            return None, "not_recognized", round(confidence * 100, 1), False, NOT_RECOGNIZED_MESSAGE, []

        return (
            result["fruit_name"],
            result["quality"],
            round(confidence * 100, 1),
            False,
            "",
            [],
        )


predictor = FruitPredictor()