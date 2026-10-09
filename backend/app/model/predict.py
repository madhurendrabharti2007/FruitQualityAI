"""Inference service with quality checks, blur rejection, and fruit detection.

Two paths are supported based on what's available in saved_model/:

A) TensorFlow model loaded from saved_model/fruit_quality.keras + labels.json
   - Input size: 224x224 RGB (MobileNetV2 backbone)
   - The model graph includes MobileNetV2 preprocessing, so inference must pass
     raw [0,255] RGB pixels rather than preprocessing them a second time.
   - Labels format (EITHER layout is accepted, detected automatically):
       * 14 classes, "FruitName_status"  e.g. ["Apple_fresh","Apple_rotten",...]
         -> fruit + status read directly from the label string
       * 7 classes, just fruit names e.g. ["Apple","Banana",...]
         -> fruit read from the label, status detected from image blemishes
   - Class order is determined by tf.keras.utils.image_dataset_from_directory
     (alphabetical sorted directory order) which matches what labels.json stores.

B) Demo mode (heuristic classifier _classify_demo) used when no model is present.
   - Runs hue-based signature matching but with correct per-fruit hue ranges.
   - Previous bugs that caused the reported symptoms:
       * catch-all fallback to "Apple" -> removed, replaced by "not_recognized"
       * hue 70-105 wrongly chose Grapes when dim -> now Green Grapes / Mango disambiguation
       * hue 105-175 wrongly mapped to Papaya -> now mapped to "not recognized" (ambiguous)
       * red/orange overlap (Apple/Tomato/Orange 0-38deg) -> saturation/brightness
         disambiguation with proper centroid comparison to seeded catalog names only.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
from PIL import Image

MODEL_DIR = Path(__file__).resolve().parent / "saved_model"
LABELS_PATH = MODEL_DIR / "labels.json"
MODEL_PATH = MODEL_DIR / "fruit_quality.keras"

# Minimum confidence to accept a TensorFlow model's top prediction.
MIN_MODEL_CONFIDENCE = 0.60
# Minimum gap between top-1 and top-2 to accept a model prediction.
MIN_MODEL_MARGIN = 0.10

# Demo mode: minimum "consensus" score from the classifier to emit a fruit.
# Below this, we honestly say "not recognized" instead of guessing Apple.
MIN_DEMO_SCORE = 0.18
# Minimum margin (winner_score - runnerup_score) below which we still accept
# a winner IF its absolute score is high enough; avoids rejecting the obvious
# winners in synthetic tests where two prototypes both happen to score >= 1.0
# due to saturation.
MIN_DEMO_MARGIN = 0.015
# Absolute winner score that bypasses the margin check.
MIN_DEMO_ABS_ACCEPT = 0.55
# Demo-mode "confidence" ceiling (heuristic scores are capped).
DEMO_MAX_CONF = 90.0

NOT_RECOGNIZED_MESSAGE = (
    "Unable to confidently identify this fruit. Please upload a clearer, "
    "well-lit photo of a single fruit."
)
BLURRY_MESSAGE = "This image is too blurry. Please upload a clearer photo."

# Exact fruit names that the DB/notebook is seeded with (see seed_data.py DATA dict).
# The classifier MUST only return names from this set, so that _info() and _ripeness()
# in routers/predict.py always find a DB row.
SEEDED_FRUITS = {"Apple", "Banana", "Mango", "Orange", "Grapes", "Tomato", "Papaya", "Pomegranate"}
SEEDED_FRUITS_LIST = ["Apple", "Banana", "Mango", "Orange", "Grapes", "Tomato", "Papaya", "Pomegranate"]

logger = logging.getLogger(__name__)


class FruitPredictor:
    def __init__(self) -> None:
        self.model = None
        self.labels: list[str] = []
        # Do labels contain an underscore status suffix?  ("Fruit_status")
        self.labels_have_status = False
        # Fruit-per-label (parallel list to labels). Same length as labels.
        # If labels HAVE status suffix: same as labels.rsplit("_",1)[0].title()
        # If labels are fruit-only: same as labels[c].title()
        self.label_fruits: list[str] = []

        if MODEL_PATH.exists() and LABELS_PATH.exists():
            try:
                import tensorflow as tf  # noqa: F401
                self.model = tf.keras.models.load_model(MODEL_PATH)
                raw_labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
                self.labels = list(raw_labels)
                # Auto-detect whether labels carry the status suffix.
                # If >= half contain an underscore we trust the format.
                underscores = sum(1 for x in self.labels if "_" in str(x))
                self.labels_have_status = underscores >= max(1, len(self.labels) // 2)
                for lab in self.labels:
                    s = str(lab)
                    if self.labels_have_status and "_" in s:
                        fruit = s.rsplit("_", 1)[0].replace("_", " ").title().strip()
                    else:
                        fruit = s.replace("_", " ").title().strip()
                    # Normalize common casing/separators ("green_grapes" -> "Grapes" etc.)
                    if "grape" in fruit.lower():
                        fruit = "Grapes"
                    self.label_fruits.append(fruit)
                logger.info(
                    "Loaded trained model %s with %d classes (status_in_label=%s). fruits=%s",
                    MODEL_PATH,
                    len(self.labels),
                    self.labels_have_status,
                    list(dict.fromkeys(self.label_fruits)),
                )
            except Exception as exc:
                logger.warning("Failed to load trained model: %s. Using demo mode.", exc, exc_info=True)
                self.model = None
                self.labels = []
                self.label_fruits = []
                self.labels_have_status = False
        else:
            logger.info(
                "No trained model at %s or %s. Falling back to heuristic demo classifier.",
                MODEL_PATH,
                LABELS_PATH,
            )

    # ------------------------------------------------------------------ blur
    def _compute_laplacian_variance(self, image: Image.Image) -> float:
        gray = np.array(image.convert("L"), dtype="float32")
        if gray.shape[0] < 3 or gray.shape[1] < 3:
            return 0.0
        lap = (
            gray[1:-1, :-2] + gray[1:-1, 2:] + gray[:-2, 1:-1] + gray[2:, 1:-1]
            - 4 * gray[1:-1, 1:-1]
        )
        return float(np.var(lap))

    # ------------------------------------------------------------- quality
    def _check_image_quality_and_relevance(self, image: Image.Image) -> tuple[bool, str]:
        try:
            laplacian_var = self._compute_laplacian_variance(image)
            logger.info("Image quality check - Laplacian variance: %.2f (blur threshold: 25.0)", laplacian_var)
            if laplacian_var < 25.0:
                logger.warning("Image rejected as blurry (variance: %.2f < 25.0)", laplacian_var)
                return False, BLURRY_MESSAGE

            gray = np.array(image.convert("L"), dtype="float32")
            ptp = float(np.ptp(gray))
            std = float(np.std(gray))
            if ptp < 40 or std < 9:
                logger.warning("Image rejected due to low contrast/variation (ptp=%.1f, std=%.1f)", ptp, std)
                return False, NOT_RECOGNIZED_MESSAGE

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
            y0, y1 = h // 5, 4 * h // 5
            x0, x1 = w // 5, 4 * w // 5
            c_sat = sat[y0:y1, x0:x1]
            c_hue = hue[y0:y1, x0:x1]
            c_r = r[y0:y1, x0:x1]
            c_g = g[y0:y1, x0:x1]
            c_b = b[y0:y1, x0:x1]

            mean_c_sat = float(np.mean(c_sat))
            low_color_ratio = float(np.mean(c_sat < 0.12))

            if mean_c_sat < 0.12 or low_color_ratio > 0.80:
                logger.warning("Image rejected as monochrome/document: mean_sat=%.2f, low_color_ratio=%.2f", mean_c_sat, low_color_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            fruit_pixels = (
                (((c_hue <= 175) | (c_hue >= 335)) | ((c_hue >= 265) & (c_hue <= 315)))
                & (c_sat > 0.12)
            )
            fruit_ratio = float(np.mean(fruit_pixels))

            cool_pixels = (c_hue >= 185) & (c_hue < 265) & (c_sat > 0.25)
            cool_ratio = float(np.mean(cool_pixels))
            if cool_ratio > 0.35 and fruit_ratio < 0.25:
                logger.warning("Image rejected as non-fruit object: cool_ratio=%.2f, fruit_ratio=%.2f", cool_ratio, fruit_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            skin_mask = (
                (c_hue >= 10) & (c_hue <= 35)
                & (c_sat >= 0.18) & (c_sat <= 0.65)
                & (c_r > c_g) & (c_g > c_b)
                & ((c_r - c_g) >= 0.08) & ((c_r - c_g) <= 0.35)
            )
            skin_ratio = float(np.mean(skin_mask))
            clothing_or_hair_pixels = (c_b > c_r) | (cmax[y0:y1, x0:x1] < 0.25)
            if skin_ratio > 0.35 and np.mean(clothing_or_hair_pixels) > 0.15 and mean_c_sat < 0.50:
                logger.warning("Image rejected as portrait/person: skin_ratio=%.2f", skin_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            if fruit_ratio < 0.10:
                logger.warning("Image rejected for lack of fruit color signals: fruit_ratio=%.2f", fruit_ratio)
                return False, NOT_RECOGNIZED_MESSAGE

            return True, ""
        except Exception as exc:
            logger.error("Error in image quality check: %s", exc, exc_info=True)
            return False, NOT_RECOGNIZED_MESSAGE

    # ------------------------------------------------------ status from img
    def _status_from_image(self, image: Image.Image) -> tuple[str, float]:
        """Detect freshness status from blemishes/brightness histogram.

        Returns (status, rotten_confidence 0..1). The caller maps 0..1 into
        the overall confidence display value.
        """
        thumb = image.convert("RGB").resize((64, 64))
        rgb = np.array(thumb, dtype="float32") / 255.0
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        delta = cmax - cmin
        sat = np.zeros_like(cmax)
        nz = cmax > 0.05
        sat[nz] = delta[nz] / cmax[nz]
        # Central crop
        h, w = cmax.shape
        y0, y1 = h // 5, 4 * h // 5
        x0, x1 = w // 5, 4 * w // 5
        c_bright = cmax[y0:y1, x0:x1]
        c_sat = sat[y0:y1, x0:x1]

        dark_blemishes = float(np.mean(c_bright < 0.35))
        p10 = float(np.percentile(c_bright, 10))
        b_std = float(np.std(c_bright))
        gray_rot = float(np.mean((c_bright < 0.45) & (c_sat < 0.25)))
        mean_bright = float(np.mean(c_bright))
        # Per-feature rotten score 0..1
        s_blem = np.clip(dark_blemishes / 0.22, 0.0, 1.0)
        s_dark = np.clip((0.35 - p10) / 0.25, 0.0, 1.0) if p10 < 0.35 else 0.0
        s_std = np.clip((b_std - 0.15) / 0.20, 0.0, 1.0) if p10 < 0.35 else 0.0
        s_gray = np.clip(gray_rot / 0.30, 0.0, 1.0)
        s_brt = np.clip((0.50 - mean_bright) / 0.30, 0.0, 1.0) if mean_bright < 0.50 else 0.0
        rot = float(max(s_blem, s_gray, 0.4 * s_dark + 0.3 * s_std + 0.3 * s_brt))
        if rot >= 0.45:
            return "rotten", rot
        return "fresh", 1.0 - rot

    # ------------------------------------------------------ demo classifier
    def _classify_demo(
        self, image: Image.Image
    ) -> tuple[str | None, str, float, list[tuple[str, float]]]:
        """Heuristic hue-based classifier.

        Returns (fruit, status, confidence, top_predictions).
        top_predictions is a sorted list of (fruit, score 0..1) best-first.
        """
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
        y0, y1 = h // 5, 4 * h // 5
        x0, x1 = w // 5, 4 * w // 5
        c_sat = sat[y0:y1, x0:x1]
        c_hue = hue[y0:y1, x0:x1]
        c_bright = cmax[y0:y1, x0:x1]
        c_r = r[y0:y1, x0:x1]
        c_g = g[y0:y1, x0:x1]
        c_b = b[y0:y1, x0:x1]

        fruit_mask = (
            (((c_hue <= 175) | (c_hue >= 335)) | ((c_hue >= 260) & (c_hue <= 320)))
            & (c_sat > 0.10)
        )
        # --- status detection (same method for demo and ML-fruit-only) ----
        status, _ = self._status_from_image(image)
        # ------------------------------------------------------------------

        if not np.any(fruit_mask):
            # No colored fruit pixels at all? Go by overall tint, VERY cautiously.
            # Weight by brightness so dark pixels don't dominate.
            wsum = float(np.sum(c_bright)) + 1e-8
            mean_r = float(np.sum(c_bright * c_r)) / wsum
            mean_g = float(np.sum(c_bright * c_g)) / wsum
            mean_b = float(np.sum(c_bright * c_b)) / wsum
            mx = max(mean_r, mean_g, mean_b, 1e-8)
            rn, gn, bn = mean_r / mx, mean_g / mx, mean_b / mx
            scores: dict[str, float] = {}
            if rn > 0.85 and gn < 0.80 and bn < 0.80:
                # red-ish: Apple vs Tomato (Apple: slightly darker / less bright)
                if gn > 0.55 and bn > 0.40:
                    scores["Apple"] = 0.35
                else:
                    scores["Tomato"] = 0.35
            if rn > 0.75 and gn > 0.75 and bn < 0.55:
                scores["Banana"] = 0.40
            if rn > 0.75 and 0.55 <= gn < 0.85 and bn < 0.50:
                scores["Orange"] = 0.40
            if 0.65 <= rn <= 0.95 and 0.65 <= gn <= 0.92 and bn < 0.70:
                scores["Mango"] = max(scores.get("Mango", 0.0), 0.38)
            if (rn < 0.70 and gn > 0.55 and bn > 0.55 and abs(gn - bn) < 0.20) or (rn < 0.70 and gn < 0.40 and bn < 0.40):
                scores["Papaya"] = 0.30
            # Purple tint -> Grapes (even under low fruit_mask ratio)
            if bn > 0.70 and rn > 0.45 and gn < 0.70:
                scores["Grapes"] = 0.55
            if not scores:
                logger.info("demo: no colored fruit pixels and no tint match -> not_recognized (was default Apple before fix)")
                return None, "not_recognized", 0.0, []
            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            fruit, score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            if score < MIN_DEMO_SCORE or (score - second_score) < 0.08:
                logger.info("demo: tint-only scores too low/ambiguous -> not_recognized. scores=%s", ranked)
                return None, "not_recognized", 0.0, ranked
            confidence = float(np.clip(78.0 + score * 20.0, 78.0, DEMO_MAX_CONF))
            logger.info("demo tint branch: %s (score=%.2f) -> %s %s (conf=%.1f)", ranked, score, fruit, status, confidence)
            return fruit, status, round(confidence, 1), ranked

        f_hues = c_hue[fruit_mask]
        f_sats = c_sat[fruit_mask]
        f_bright = c_bright[fruit_mask]

        purple_mask = (f_hues >= 260) & (f_hues <= 320)
        purple_ratio = float(np.mean(purple_mask)) if len(f_hues) else 0.0
        purple_sat = float(np.mean(f_sats[purple_mask])) if np.any(purple_mask) else 0.0

        # Hue ratio buckets. Each bucket is the fraction of fruit pixels whose
        # hue falls in that band. We compare these fractions against per-fruit
        # prototype masks to compute a centroid-style score for each seeded fruit.
        def hue_in(h, lo, hi):
            if lo <= hi:
                return (h >= lo) & (h < hi)
            # wrapped around 0° (e.g. 340..20 means 340..360 and 0..20)
            return (h >= lo) | (h < hi)

        n_fruit = len(f_hues) if len(f_hues) else 1
        # Prototypes: name -> (hue_lo, hue_hi, ideal_sat_min, ideal_bright_min,
        #                       bonus_rgb_conditions, penalty_conditions)
        prototypes: list[tuple[str, tuple, float, float]] = [
            # name   hue_lo hue_hi  sat bright
            ("Grapes", (260, 320), 0.20, 0.15),   # Purple grapes
            ("Grapes", (85, 120),  0.15, 0.30),   # Green grapes (yellow-green band)
            ("Banana", (42, 68),   0.35, 0.55),   # Bright yellow
            ("Orange", (18, 40),   0.55, 0.45),   # Orange (typical)
            ("Mango",  (30, 75),   0.30, 0.40),   # Orange-yellow-ripe + greenish-ripe
            ("Tomato", (340, 15),  0.55, 0.55),   # Bright pure red (wraparound)
            ("Apple",  (345, 20),  0.30, 0.35),   # Red; also handles blush green apples below
            ("Papaya", (22, 55),   0.35, 0.45),   # Orange-yellow-pink
        ]
        # Apple also accepts green-yellow (Granny Smith) tones, but with lower
        # sat than mango/grapes; we score that separately.
        apple_green_hue = (95, 150)
        apple_green_sat_lo = 0.12
        apple_green_sat_hi = 0.50

        raw_scores: dict[str, float] = {}
        for name, (hlo, hhi), sat_lo, brt_lo in prototypes:
            band = hue_in(f_hues, hlo, hhi)
            ratio = float(np.mean(band)) if len(f_hues) else 0.0
            if ratio <= 0.02:
                continue
            in_band_sat = float(np.mean(f_sats[band])) if np.any(band) else 0.0
            in_band_brt = float(np.mean(f_bright[band])) if np.any(band) else 0.0
            # Match quality: need saturation and brightness above prototype floor.
            quality = 1.0
            if in_band_sat < sat_lo:
                quality *= 0.35 + 0.65 * max(0.0, in_band_sat / max(sat_lo, 1e-4))
            if in_band_brt < brt_lo:
                quality *= 0.35 + 0.65 * max(0.0, in_band_brt / max(brt_lo, 1e-4))
            score = ratio * quality
            raw_scores[name] = raw_scores.get(name, 0.0) + score

        # Apple (Granny Smith) green-band score
        band = hue_in(f_hues, *apple_green_hue)
        ratio = float(np.mean(band)) if len(f_hues) else 0.0
        if ratio > 0.02:
            in_band_sat = float(np.mean(f_sats[band])) if np.any(band) else 0.0
            in_band_brt = float(np.mean(f_bright[band])) if np.any(band) else 0.0
            if apple_green_sat_lo <= in_band_sat <= apple_green_sat_hi and in_band_brt > 0.30:
                raw_scores["Apple"] = raw_scores.get("Apple", 0.0) + ratio * 0.85

        # Purple dominance: if >30% pixels are 260-320 and reasonably saturated,
        # strongly favor Grapes.
        if purple_ratio >= 0.30 and purple_sat >= 0.20:
            raw_scores["Grapes"] = max(raw_scores.get("Grapes", 0.0), 0.55 + purple_ratio * 0.2)

        # Green-grapes disambiguation: hue 85-120 yellow-green band.
        # This band is shared between pale green grapes and richly-colored
        # unripe green mango / green apple. We pick Grapes ONLY when:
        #   - the wide Mango band (30-75°) doesn't already have a strong score,
        #   - the saturation is truly pale / low (0.15 - 0.42),
        #   - NO strong contribution from purple (260-320) grape pixels either.
        # Otherwise unripe green mangos get mislabeled as Grapes (the 90° bug).
        band_gg = hue_in(f_hues, 85, 120)
        ratio_gg = float(np.mean(band_gg)) if len(f_hues) else 0.0
        band_mango_wide = hue_in(f_hues, 30, 85)
        ratio_mango_wide = float(np.mean(band_mango_wide)) if len(f_hues) else 0.0
        band_yellow = hue_in(f_hues, 42, 68)
        ratio_yellow = float(np.mean(band_yellow)) if len(f_hues) else 0.0
        gg_sat = float(np.mean(f_sats[band_gg])) if np.any(band_gg) else 0.0
        gg_brt = float(np.mean(f_bright[band_gg])) if np.any(band_gg) else 0.0
        is_pale_green_grape = (
            ratio_gg >= 0.25
            and 0.15 <= gg_sat <= 0.42   # pale, not a richly colored unripe mango
            and gg_brt >= 0.40            # bright, not shadowed
            and ratio_mango_wide < 0.25   # not also heavy in the mango 30-85 range
            and purple_ratio < 0.08       # no purple grape contribution yet
        )
        if is_pale_green_grape:
            raw_scores["Grapes"] = max(raw_scores.get("Grapes", 0.0), ratio_gg * 0.75)
        else:
            # Hue 85-120 with sat > 0.42 and/or mango overlap: lean to unripe Mango
            # (or possibly Apple/Granny Smith via the green-apple rule above). We
            # do NOT favor Grapes here.
            if ratio_gg >= 0.20 and gg_sat > 0.42:
                # Richly-colored in the yellow-green band: it's an unripe mango or
                # similar; suppress any incidental Grapes score so it can't win.
                raw_scores["Grapes"] = raw_scores.get("Grapes", 0.0) * 0.25
                # Give a Mango boost proportional to the share.
                adj = ratio_gg * 0.55
                if ratio_mango_wide > 0:
                    adj = max(adj, (ratio_gg + ratio_mango_wide) * 0.50)
                raw_scores["Mango"] = max(raw_scores.get("Mango", 0.0), adj)

        # Ambiguous green-cyan (120-175 deg): never map to Papaya directly.
        # Keep only if another prototype already lifted it; else discard.
        # We also never allow Papaya to win just on its orange prototype alone
        # when Mango/Orange also score highly (avoids the hue-30 misclassify).
        ambig = hue_in(f_hues, 120, 175)
        ambig_ratio = float(np.mean(ambig)) if len(f_hues) else 0.0
        if ambig_ratio > 0.40:
            # Mostly green/teal pixels. This is extremely unlikely to be any
            # of our 7 fruits (only Granny Smith apples & green grapes could
            # plausibly reach here, and both are handled above).
            logger.info("demo: %.0f%% pixels are green-cyan ambiguous -> rejecting.", ambig_ratio * 100)
            return None, "not_recognized", 0.0, sorted(raw_scores.items(), key=lambda kv: kv[1], reverse=True)

        # Only keep fruits that exist in the seeded catalog.
        raw_scores = {k: v for k, v in raw_scores.items() if k in SEEDED_FRUITS}

        if not raw_scores:
            logger.info("demo: no prototype matched any seeded fruit -> not_recognized (was Apple fallback)")
            return None, "not_recognized", 0.0, []

        ranked = sorted(raw_scores.items(), key=lambda kv: kv[1], reverse=True)
        fruit, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = top_score - second_score

        logger.info(
            "demo prototype scores: %s  (winner=%s score=%.3f margin=%.3f)",
            ranked, fruit, top_score, margin,
        )

        # Banana vs Mango disambiguation: a bright, yellow-dominant fruit with
        # very little orange or green should be Banana, not Mango.
        yellow_band = hue_in(f_hues, 42, 68)
        yellow_ratio = float(np.mean(yellow_band)) if len(f_hues) else 0.0
        yellow_sat = float(np.mean(f_sats[yellow_band])) if np.any(yellow_band) else 0.0
        yellow_brt = float(np.mean(f_bright[yellow_band])) if np.any(yellow_band) else 0.0
        orange_ratio = float(np.mean(hue_in(f_hues, 18, 42))) if len(f_hues) else 0.0
        green_ratio = float(np.mean(hue_in(f_hues, 85, 150))) if len(f_hues) else 0.0
        if yellow_ratio >= 0.30 and yellow_brt >= 0.52 and orange_ratio <= 0.25 and green_ratio <= 0.18:
            raw_scores["Banana"] = max(raw_scores.get("Banana", 0.0), yellow_ratio * 0.90 + yellow_sat * 0.35)
            if "Mango" in raw_scores:
                raw_scores["Mango"] *= 0.35
            ranked = sorted(raw_scores.items(), key=lambda kv: kv[1], reverse=True)
            fruit, top_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            margin = top_score - second_score
            logger.info(
                "demo banana-vs-mango override: yellow=%.2f orange=%.2f green=%.2f sat=%.2f brt=%.2f ranked=%s",
                yellow_ratio, orange_ratio, green_ratio, yellow_sat, yellow_brt, ranked,
            )

        # --- accept/reject gate ------------------------------------------
        absolute_ok = top_score >= MIN_DEMO_ABS_ACCEPT
        relative_ok = margin >= MIN_DEMO_MARGIN
        score_ok = top_score >= MIN_DEMO_SCORE
        if not score_ok or (not absolute_ok and not relative_ok):
            logger.info(
                "demo: reject score=%.3f(>=%s?%s) margin=%.3f(>=%s?%s) abs=%.3f(>=%s?%s) -> not_recognized",
                top_score, MIN_DEMO_SCORE, score_ok,
                margin, MIN_DEMO_MARGIN, relative_ok,
                top_score, MIN_DEMO_ABS_ACCEPT, absolute_ok,
            )
            return None, "not_recognized", 0.0, ranked

        # Red fruits: Tomato = higher saturation and brightness (glossy skin),
        # Apple = slightly lower saturation due to blush/skin variation and
        # a lower R-minus-G difference when compared at equal brightness.
        if fruit in ("Apple", "Tomato"):
            red_band = hue_in(f_hues, 340, 20)
            if np.any(red_band):
                rsat = float(np.mean(f_sats[red_band]))
                rbrt = float(np.mean(f_bright[red_band]))
                rr = float(np.mean(c_r[fruit_mask][red_band[0: min(len(f_hues), len(c_r))]])) if False else float(np.mean(f_sats[red_band]))  # noqa: E501
                # Use weighted R,G,B means on RED pixels.
                rmask_red = (c_hue >= 340) | (c_hue < 20) & (c_sat > 0.3)
                if np.any(rmask_red):
                    rr_ = float(np.mean(c_r[rmask_red]))
                    rg_ = float(np.mean(c_g[rmask_red]))
                    rb_ = float(np.mean(c_b[rmask_red]))
                    # A raw red-blue and red-green spread bigger = Tomato skin.
                    spread = (rr_ - rb_) + (rr_ - rg_)
                    if spread > 0.70 and rsat >= 0.60 and rbrt >= 0.55:
                        if fruit != "Tomato" and "Tomato" in raw_scores:
                            logger.info("demo red-band disambiguation: spread=%.2f -> override %s->Tomato", spread, fruit)
                            fruit = "Tomato"
                    elif spread < 0.60 and rsat < 0.60:
                        if fruit != "Apple" and "Apple" in raw_scores:
                            logger.info("demo red-band disambiguation: spread=%.2f -> override %s->Apple", spread, fruit)
                            fruit = "Apple"

        # Orange vs Papaya vs Mango:
        #   - Orange: concentrated in 18-42 with moderate-to-high saturation.
        #     Real Indian Kinnow/Santra oranges can have sat=0.40-0.60, not just
        #     the >0.60 of a bright neon orange. Often blended with green skin
        #     tone in 85-150 so the combined orange+green band can be huge.
        #   - Papaya: pinker/redder blush mixed with orange (so a noticeable
        #     share of 340-20 red pixels, AND a wider 10-60 spread).
        #   - Mango: wider yellow-ripe range (30-85 with strong 42-70 yellow
        #     band), usually less concentrated pure orange than a Santra.
        if fruit in ("Orange", "Papaya", "Mango"):
            orange_core = hue_in(f_hues, 18, 42)
            ratio_oc = float(np.mean(orange_core)) if len(f_hues) else 0.0
            orange_wide = hue_in(f_hues, 10, 55)
            ratio_ow = float(np.mean(orange_wide)) if len(f_hues) else 0.0
            orange_green_skin = hue_in(f_hues, 85, 150)
            ratio_og = float(np.mean(orange_green_skin)) if len(f_hues) else 0.0
            red_blush = hue_in(f_hues, 340, 20)
            ratio_red = float(np.mean(red_blush)) if len(f_hues) else 0.0
            mango_banana_yellow = hue_in(f_hues, 42, 85)
            ratio_mb = float(np.mean(mango_banana_yellow)) if len(f_hues) else 0.0

            orange_sat = float(np.mean(f_sats[orange_core])) if np.any(orange_core) else 0.0
            orange_brt = float(np.mean(f_bright[orange_core])) if np.any(orange_core) else 0.0

            # Rule 1: Strong concentrated orange core (>=40%) with sat>=0.45 -> Orange.
            # Real-world Kinnow/Santra at 20-40° can have sat around 0.45-0.55
            # (e.g. user-uploaded orange had sat=0.51, ratio_oc=0.83).
            oc_promote = (
                ratio_oc >= 0.40
                and orange_sat >= 0.45
                and orange_brt >= 0.35
                # Papaya typically shows red blush (>8%) which orange doesn't.
                and ratio_red < 0.15
            )
            # Rule 2: Wide orange band + green skin blend (typical green Kinnow
            # or unripe orange with green patches on the right/top of the fruit).
            # Combined (orange_core OR green skin) must dominate; AND Mango's
            # pure yellow-ripe band (42-85°) must be smaller than orange share.
            blend_promote = (
                (ratio_oc + ratio_og) >= 0.50
                and ratio_oc >= 0.10
                and orange_sat >= 0.40
                and ratio_mb <= max(0.40, ratio_oc * 1.2 + 0.15)
                and ratio_red < 0.15
            )
            if oc_promote or blend_promote:
                if fruit != "Orange" and "Orange" in raw_scores:
                    logger.info(
                        "demo: orange-promote oc=%.2f og=%.2f mb=%.2f sat=%.2f "
                        "red=%.2f -> override %s->Orange (rule: %s)",
                        ratio_oc, ratio_og, ratio_mb, orange_sat, ratio_red,
                        fruit, "oc" if oc_promote else "blend",
                    )
                    fruit = "Orange"

            # Papaya-confirm: need both substantial orange-yellow AND either
            # red-blush (>10%) OR very wide 10-60 coverage (pinker skin blend).
            # Without this, a concentrated pure orange at 22-50° can accidentally
            # reach higher Papaya score than Orange (since Papaya prototype band
            # 22-55 is wider than Orange 18-40).
            if fruit == "Papaya" and not (
                (ratio_red >= 0.10) or (ratio_ow >= 0.80 and ratio_mb >= 0.15)
            ):
                if "Orange" in raw_scores and ratio_oc >= 0.25:
                    logger.info(
                        "demo: Papaya lacks red-blush (%.2f) or wide coverage "
                        "(ow=%.2f mb=%.2f) -> downgrade to Orange",
                        ratio_red, ratio_ow, ratio_mb,
                    )
                    fruit = "Orange"

        confidence = float(np.clip(78.0 + top_score * 18.0 + margin * 10.0, 78.0, DEMO_MAX_CONF))
        logger.info("demo final: %s %s (conf=%.1f) margin=%.3f", fruit, status, confidence, margin)
        return fruit, status, round(confidence, 1), ranked

    # -------------------------------------------------------------- predict
    def predict(
        self, image_path: Path
    ) -> tuple[str | None, str, float, bool, str, list[tuple[str, float]]]:
        """Predict fruit and freshness from image.

        Returns:
            (fruit, status, confidence_pct, demo_mode, message, top_predictions)
              top_predictions: list of (fruit, score), best-first.
                               scores are in [0,1] for ML (class probabilities)
                               and in [0,1] for demo (prototype ratios).
        """
        image = Image.open(image_path)

        quality_ok, quality_message = self._check_image_quality_and_relevance(image)
        if not quality_ok:
            is_demo = self.model is None
            logger.info("Image rejected before inference: message=%s, demo=%s", quality_message, is_demo)
            return None, "not_recognized", 0.0, is_demo, quality_message, []

        if self.model is not None:
            resized = image.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
            arr = np.asarray(resized, dtype="float32")
            batch = np.expand_dims(arr, 0)
            scores = self.model.predict(batch, verbose=0)[0]

            ranked = list(np.argsort(scores))
            k = min(len(ranked), 5)
            top_idx = ranked[-k:]
            top_idx_desc = list(reversed(top_idx))
            top_scores: list[tuple[str, float]] = []
            for i in top_idx_desc:
                label = self.labels[int(i)] if int(i) < len(self.labels) else f"class_{i}"
                name = self.label_fruits[int(i)] if int(i) < len(self.label_fruits) else label
                top_scores.append((name, float(scores[i])))
            logger.info("model raw top-5: %s", top_scores)

            idx = int(ranked[-1])
            confidence = float(scores[idx])
            second_confidence = float(scores[ranked[-2]]) if len(scores) > 1 else 0.0
            margin = confidence - second_confidence

            if confidence < MIN_MODEL_CONFIDENCE or margin < MIN_MODEL_MARGIN:
                logger.warning(
                    "Model prediction rejected: confidence=%.2f < %.2f or margin=%.2f < %.2f. Falling back to demo classifier. top_scores=%s",
                    confidence, MIN_MODEL_CONFIDENCE, margin, MIN_MODEL_MARGIN, top_scores,
                )
                fruit_demo, status_demo, confidence_demo, top_demo = self._classify_demo(image)
                if fruit_demo is not None and status_demo != "not_recognized" and confidence_demo >= 78.0:
                    logger.info(
                        "Using demo classifier after low-confidence model result: %s %s conf=%.1f top=%s",
                        fruit_demo, status_demo, confidence_demo, top_demo[:3],
                    )
                    return fruit_demo, status_demo, confidence_demo, True, "", top_demo
                return None, "not_recognized", 0.0, False, NOT_RECOGNIZED_MESSAGE, top_scores

            label_name = str(self.labels[idx]) if idx < len(self.labels) else ""
            if "_" in label_name:
                fruit_part, status_part = label_name.rsplit("_", 1)
                fruit = fruit_part.replace("_", " ").title().strip()
                status = status_part.lower()
                if fruit == "Pomegranate":
                    fruit = "Pomegranate"
                if "grape" in fruit.lower():
                    fruit = "Grapes"
                if status not in {"good", "bad", "fresh", "rotten"}:
                    status, _stat_conf = self._status_from_image(image)
                else:
                    status = "fresh" if status.lower() in {"good", "fresh"} else "rotten"
            else:
                fruit = self.label_fruits[idx] if idx < len(self.label_fruits) else None
                if fruit and "grape" in fruit.lower():
                    fruit = "Grapes"
                status, _stat_conf = self._status_from_image(image)

            if fruit not in SEEDED_FRUITS:
                logger.warning(
                    "Model predicted fruit=%r not in seeded catalog %s; rejecting.",
                    fruit, SEEDED_FRUITS,
                )
                return None, "not_recognized", 0.0, False, NOT_RECOGNIZED_MESSAGE, top_scores

            confidence_pct = round(confidence * 100.0, 1)
            return fruit, status, confidence_pct, False, "", top_scores

        # -------------------------------------------------------------------
        # Demo / heuristic mode.
        # -------------------------------------------------------------------
        fruit, status, confidence, top_scores = self._classify_demo(image)
        if fruit is None or status == "not_recognized":
            logger.info("demo classifier chose not_recognized. top_scores=%s", top_scores)
            return None, "not_recognized", 0.0, True, NOT_RECOGNIZED_MESSAGE, top_scores
        if confidence < 78.0:
            logger.warning("demo confidence %.1f < 78 -> not_recognized", confidence)
            return None, "not_recognized", 0.0, True, NOT_RECOGNIZED_MESSAGE, top_scores
        logger.info("demo mode result: fruit=%s status=%s confidence=%.1f top=%s", fruit, status, confidence, top_scores[:3])
        return fruit, status, confidence, True, "", top_scores


predictor = FruitPredictor()
