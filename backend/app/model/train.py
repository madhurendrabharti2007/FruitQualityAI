"""Train a single multi-class fresh/rotten fruit classifier.

Two dataset layouts are supported (auto-detected).

Layout A — 14 classes (7 fruits × 2 statuses), flat class folders:
    backend/dataset/
      Apple_fresh/*.jpg
      Apple_rotten/*.jpg
      Banana_fresh/*.jpg
      ...
    Each class folder directly contains .jpg images.
    Labels in labels.json become ["Apple_fresh","Apple_rotten",...]
    and inference uses the status part directly from the label.

Layout B — 7 fruit-only classes, nested status subdirs (the "legacy" layout):
    backend/dataset/
      Apple/fresh/*.jpg
      Apple/rotten/*.jpg
      Banana/fresh/*.jpg
      ...
    The trained model is a 7-way fruit classifier only.
    Labels in labels.json become ["Apple","Banana",...].
    Inference reads the fruit from the label, and detects freshness from
    image blemishes via the predictor's _status_from_image() helper.

Class order is determined by `tf.keras.utils.image_dataset_from_directory`
which sorts directory names ALPHABETICALLY. This order is preserved in
labels.json, so inference always knows which index maps to which name.

Training is in two stages: head training with a frozen MobileNetV2 backbone,
then fine-tuning of the last ~25 backbone layers at a low learning rate.
"""
from __future__ import annotations

from pathlib import Path
import json
import logging
import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras.applications import MobileNetV2

ROOT = Path(__file__).resolve().parents[2] / "dataset"
OUT = Path(__file__).resolve().parent / "saved_model"
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42
logger = logging.getLogger(__name__)


def _detect_layout() -> tuple[str, Path]:
    """Return ("flat-14", ROOT) for Layout A or ("nested-7", ROOT) for Layout B.

    Layout A: top-level directories contain underscores and/or "fresh"/"rotten"
              as part of the directory name, and directly contain images.
    Layout B: top-level directories have /fresh and /rotten SUBDIRECTORIES, and
              those SUBDIRECTORIES contain images.
    """
    if not ROOT.exists():
        raise RuntimeError(
            f"Dataset directory {ROOT} does not exist. Create backend/dataset/ "
            "and populate it using Layout A (flat 14-class) or Layout B "
            "(nested 7-class, see docstring)."
        )
    top = sorted([p for p in ROOT.iterdir() if p.is_dir()])
    if not top:
        raise RuntimeError(f"No class folders found inside {ROOT}.")

    has_nested_fresh = any(
        (Path(p) / "fresh").is_dir() or (Path(p) / "rotten").is_dir() for p in top
    )
    has_flat_status = any("_" in p.name for p in top)
    if has_nested_fresh and not has_flat_status:
        return ("nested-7", ROOT)
    return ("flat-14", ROOT)


def train() -> None:
    layout, data_root = _detect_layout()
    logger.info("Dataset layout detected: %s  classes-root: %s", layout, data_root)

    augment = tf.keras.Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.12),
        layers.RandomZoom(0.12),
        layers.RandomContrast(0.15),
    ])

    train_ds = tf.keras.utils.image_dataset_from_directory(
        data_root,
        validation_split=0.2,
        subset="training",
        seed=SEED,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
    )
    holdout = tf.keras.utils.image_dataset_from_directory(
        data_root,
        validation_split=0.2,
        subset="validation",
        seed=SEED,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
    )
    val_batches = max(1, int(tf.data.experimental.cardinality(holdout)) // 2)
    val_ds = holdout.take(val_batches)
    test_ds = holdout.skip(val_batches)

    class_names = train_ds.class_names  # alphabetical sorted order
    if len(class_names) < 2:
        raise RuntimeError("Need at least 2 class folders under backend/dataset.")

    logger.info("Class order (%d classes): %s", len(class_names), class_names)

    base = MobileNetV2(
        input_shape=(*IMAGE_SIZE, 3), include_top=False, weights="imagenet"
    )
    base.trainable = False
    inputs = tf.keras.Input(shape=(*IMAGE_SIZE, 3))
    x = augment(inputs)
    # NOTE: inference must use the SAME normalization:
    # tf.keras.applications.mobilenet_v2.preprocess_input maps [0,255] -> [-1, 1]
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.25)(x)
    outputs = layers.Dense(len(class_names), activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(train_ds, validation_data=val_ds, epochs=8)

    base.trainable = True
    for layer in base.layers[:-25]:
        layer.trainable = False
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-5),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(train_ds, validation_data=val_ds, epochs=3)

    logger.info("test metrics: %s", model.evaluate(test_ds, verbose=0))

    OUT.mkdir(parents=True, exist_ok=True)
    model.save(OUT / "fruit_quality.keras")
    labels_out = [c.replace(" ", "_") for c in class_names]
    (OUT / "labels.json").write_text(json.dumps(labels_out), encoding="utf-8")
    logger.info(
        "Saved %s and labels.json (%d classes, layout=%s): %s",
        OUT / "fruit_quality.keras", len(labels_out), layout, labels_out,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
