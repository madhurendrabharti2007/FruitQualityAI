"""Inference service with quality checks, blur rejection, and fruit detection."""
import json
import logging
from pathlib import Path
import numpy as np
from PIL import Image

MODEL_DIR = Path(__file__).resolve().parent / "saved_model"
LABELS_PATH = MODEL_DIR / "labels.json"
MODEL_PATH = MODEL_DIR / "fruit_quality.keras"
MIN_MODEL_CONFIDENCE = 0.70
MIN_MODEL_MARGIN = 0.15
NOT_RECOGNIZED_MESSAGE = "We couldn't detect a fruit in this image. Please upload a clear photo of a single fruit."
BLURRY_MESSAGE = "This image is too blurry. Please upload a clearer photo."
logger = logging.getLogger(__name__)

class FruitPredictor:
    def __init__(self) -> None:
        self.model = None
        self.labels: list[str] = []
        if MODEL_PATH.exists() and LABELS_PATH.exists():
            try:
                import tensorflow as tf
                self.model = tf.keras.models.load_model(MODEL_PATH)
                self.labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
                logger.info("Loaded trained model from %s with %d labels", MODEL_PATH, len(self.labels))
            except Exception as exc:
                logger.warning("Failed to load trained model: %s. Using demo mode.", exc)
                self.model = None
        else:
            logger.info("No trained model found at %s. Using demo mode.", MODEL_PATH)

    def _compute_laplacian_variance(self, image: Image.Image) -> float:
        """Compute discrete Laplacian variance as a blur detection metric."""
        gray = np.array(image.convert("L"), dtype="float32")
        if gray.shape[0] < 3 or gray.shape[1] < 3:
            return 0.0
        lap = gray[1:-1, :-2] + gray[1:-1, 2:] + gray[:-2, 1:-1] + gray[2:, 1:-1] - 4 * gray[1:-1, 1:-1]
        return float(np.var(lap))

    def _check_image_quality_and_relevance(self, image: Image.Image) -> tuple[bool, str]:
        """Pre-model check: Rejects blurry images and non-fruit objects/people."""
        try:
            # 1. Blur check via true discrete Laplacian variance
            laplacian_var = self._compute_laplacian_variance(image)
            logger.info("Image quality check - Laplacian variance: %.2f (blur threshold: 25.0)", laplacian_var)
            if laplacian_var < 25.0:
                logger.warning("Image rejected as blurry (variance: %.2f < 25.0)", laplacian_var)
                return False, BLURRY_MESSAGE

            # 2. Contrast and detail variation
            gray = np.array(image.convert("L"), dtype="float32")
            ptp = float(np.ptp(gray))
            std = float(np.std(gray))
            if ptp < 40 or std < 12:
                logger.warning("Image rejected due to low contrast/variation (ptp=%.1f, std=%.1f)", ptp, std)
                return False, NOT_RECOGNIZED_MESSAGE

            # 3. Color & Content Analysis on normalized thumbnail
            thumb = image.convert("RGB").resize((64, 64))
            rgb = np.array(thumb, dtype="float32") / 255.0
            r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
            cmax = np.maximum(np.maximum(r, g), b)
            cmin = np.minimum(np.minimum(r, g), b)
            delta = cmax - cmin

            sat = np.zeros_like(cmax)
            nz = cmax > 0.05
            sat[nz] = delta[nz] / cmax[nz]

            hue = np.zeros_like(cmax)
            mr = (cmax == r) & (delta > 0.01)
            hue[mr] = ((g[mr] - b[mr]) / delta[mr]) % 6.0
            mg = (cmax == g) & (delta > 0.01)
            hue[mg] = ((b[mg] - r[mg]) / delta[mg]) + 2.0
            mb = (cmax == b) & (delta > 0.01)
            hue[mb] = ((r[mb] - g[mb]) / delta[mb]) + 4.0
            hue = hue * 60.0

            # Target focal center region
            h, w = cmax.shape
            c_sat = sat[h // 5:4 * h // 5, w // 5:4 * w // 5]
            c_hue = hue[h // 5:4 * h // 5, w // 5:4 * w // 5]
            c_r = r[h // 5:4 * h // 5, w // 5:4 * w // 5]
            c_g = g[h // 5:4 * h // 5, w // 5:4 * w // 5]
            c_b = b[h // 5:4 * h // 5, w // 5:4 * w // 5]
            c_max = cmax[h // 5:4 * h // 5, w // 5:4 * w // 5]

            mean_c_sat = float(np.mean(c_sat))
            low_color_ratio = float(np.mean(c_sat < 0.12))

            # Reject monochrome / documents / white walls / metals
            if mean_c_sat < 0.12 or low_color_ratio > 0.80:
                logger.warning("Image rejected as monochrome/document: mean_sat=%.2f, low_color_ratio=%.2f", mean_c_sat, low_color_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            # Organic fruit hues: Reds, Oranges, Yellows, Greens
            fruit_pixels = ((c_hue <= 165) | (c_hue >= 340)) & (c_sat > 0.15)
            fruit_ratio = float(np.mean(fruit_pixels))

            # Cool artificial hues (pure blues, cyans, cold purples: 185 to 320)
            cool_pixels = (c_hue >= 185) & (c_hue <= 320) & (c_sat > 0.25)
            cool_ratio = float(np.mean(cool_pixels))
            if cool_ratio > 0.35 and fruit_ratio < 0.30:
                logger.warning("Image rejected as non-fruit object: cool_ratio=%.2f, fruit_ratio=%.2f", cool_ratio, fruit_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            # Human portrait / skin check
            skin_mask = (c_hue >= 10) & (c_hue <= 35) & (c_sat >= 0.18) & (c_sat <= 0.65) & (c_r > c_g) & (c_g > c_b) & ((c_r - c_g) >= 0.08) & ((c_r - c_g) <= 0.35)
            skin_ratio = float(np.mean(skin_mask))
            clothing_or_hair_pixels = ((c_b > c_r) | (c_max < 0.25))
            if skin_ratio > 0.35 and np.mean(clothing_or_hair_pixels) > 0.15 and mean_c_sat < 0.50:
                logger.warning("Image rejected as portrait/person: skin_ratio=%.2f", skin_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            if fruit_ratio < 0.15:
                logger.warning("Image rejected for lack of fruit color signals: fruit_ratio=%.2f", fruit_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            return True, ""

        except Exception as exc:
            logger.error("Error in image quality check: %s", exc, exc_info=True)
            return False, NOT_RECOGNIZED_MESSAGE

    def _classify_demo(self, image: Image.Image) -> tuple[str, str, float]:
        """Classify fruit type and freshness based on visual signatures in demo mode."""
        thumb = image.convert("RGB").resize((64, 64))
        rgb = np.array(thumb, dtype="float32") / 255.0
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        delta = cmax - cmin

        sat = np.zeros_like(cmax)
        nz = cmax > 0.05
        sat[nz] = delta[nz] / cmax[nz]

        hue = np.zeros_like(cmax)
        mr = (cmax == r) & (delta > 0.01)
        hue[mr] = ((g[mr] - b[mr]) / delta[mr]) % 6.0
        mg = (cmax == g) & (delta > 0.01)
        hue[mg] = ((b[mg] - r[mg]) / delta[mg]) + 2.0
        mb = (cmax == b) & (delta > 0.01)
        hue[mb] = ((r[mb] - g[mb]) / delta[mb]) + 4.0
        hue = hue * 60.0

        h, w = cmax.shape
        c_sat = sat[h // 5:4 * h // 5, w // 5:4 * w // 5]
        c_hue = hue[h // 5:4 * h // 5, w // 5:4 * w // 5]
        c_bright = cmax[h // 5:4 * h // 5, w // 5:4 * w // 5]

        fruit_mask = ((c_hue <= 165) | (c_hue >= 340)) & (c_sat > 0.15)
        if not np.any(fruit_mask):
            return "Apple", "fresh", 85.0

        f_hues = c_hue[fruit_mask]
        f_sats = c_sat[fruit_mask]
        f_bright = c_bright[fruit_mask]

        rads = np.deg2rad(f_hues)
        avg_rad = np.arctan2(np.mean(np.sin(rads)), np.mean(np.cos(rads)))
        avg_hue = float((np.rad2deg(avg_rad)) % 360.0)

        # Distinguish fruit type by hue
        if 20 <= avg_hue < 42:
            fruit = "Orange"
        elif 42 <= avg_hue < 68:
            fruit = "Banana"
        elif 68 <= avg_hue <= 100:
            fruit = "Mango"
        elif 100 < avg_hue <= 160:
            fruit = "Papaya" if np.mean(f_bright) < 0.55 else "Grapes"
        elif 160 < avg_hue <= 190:
            fruit = "Tomato"
        else:
            fruit = "Apple"

        # Distinguish freshness by discoloration / dark necrotic blemishes / variance
        dark_blemishes = float(np.mean(c_bright < 0.35))
        p10 = float(np.percentile(c_bright, 10))
        b_std = float(np.std(c_bright))
        gray_rot = float(np.mean((c_bright < 0.45) & (c_sat < 0.25)))
        is_rotten = (dark_blemishes > 0.15) or (p10 < 0.30 and b_std > 0.15) or (gray_rot > 0.20) or (float(np.mean(f_bright)) < 0.38)
        status = "rotten" if is_rotten else "fresh"
        confidence = float(np.clip(84.0 + np.mean(f_sats) * 12.0, 82.0, 96.0))

        return fruit, status, round(confidence, 1)

    def predict(self, image_path: Path) -> tuple[str | None, str, float, bool, str]:
        """Predict fruit and freshness from image.
        
        Returns:
            (fruit, status, confidence, demo_mode, message)
        """
        image = Image.open(image_path)

        # Pre-model quality & relevance check runs for EVERY request
        quality_ok, quality_message = self._check_image_quality_and_relevance(image)
        if not quality_ok:
            is_demo = self.model is None
            logger.info("Image rejected before inference: message=%s, demo=%s", quality_message, is_demo)
            return None, "not_recognized", 0.0, is_demo, quality_message

        # If a trained TensorFlow model is loaded:
        if self.model is not None:
            import numpy as np
            resized_image = image.convert("RGB").resize((224, 224))
            scores = self.model.predict(np.expand_dims(np.asarray(resized_image, dtype="float32") / 255, 0), verbose=0)[0]
            ranked = np.argsort(scores)
            index = int(ranked[-1])
            confidence = float(scores[index])
            second_confidence = float(scores[ranked[-2]]) if len(scores) > 1 else 0.0

            logger.info("Model prediction raw - top_class: %d, confidence: %.2f, second_confidence: %.2f, margin: %.2f",
                        index, confidence, second_confidence, confidence - second_confidence)

            if confidence < MIN_MODEL_CONFIDENCE or confidence - second_confidence < MIN_MODEL_MARGIN:
                logger.warning("Model prediction rejected: confidence %.2f < %.2f or margin %.2f < %.2f",
                               confidence, MIN_MODEL_CONFIDENCE, confidence - second_confidence, MIN_MODEL_MARGIN)
                return None, "not_recognized", 0.0, False, NOT_RECOGNIZED_MESSAGE

            fruit, status = self.labels[index].rsplit("_", 1)
            return fruit.title(), status, round(confidence * 100, 1), False, ""

        # Demo mode prediction
        fruit, status, confidence = self._classify_demo(image)
        logger.info("Demo mode raw output - fruit: %s, status: %s, confidence: %.1f", fruit, status, confidence)
        return fruit, status, confidence, True, ""

predictor = FruitPredictor()
