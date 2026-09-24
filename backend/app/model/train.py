"""Train a single multi-class fresh/rotten fruit classifier.

Dataset layout:
    dataset/<fruit_name>/fresh/*.jpg
    dataset/<fruit_name>/rotten/*.jpg

The 80/10/10 split is created deterministically from a tf.data pipeline. Images
are augmented for changes in rotation, mirroring, zoom, and lighting. The base
MobileNetV2 is frozen for head training, then the final layers can be unfrozen
for optional low-learning-rate fine tuning.
"""
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

def train() -> None:
    classes = sorted(p.name for p in ROOT.glob("*/*") if p.is_dir())
    if len(classes) < 2:
        raise RuntimeError("Add at least two fruit/status folders under backend/dataset first.")
    train_ds = tf.keras.utils.image_dataset_from_directory(ROOT, validation_split=0.2, subset="training", seed=SEED, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE)
    holdout = tf.keras.utils.image_dataset_from_directory(ROOT, validation_split=0.2, subset="validation", seed=SEED, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE)
    val_batches = max(1, int(tf.data.experimental.cardinality(holdout)) // 2)
    val_ds = holdout.take(val_batches)
    test_ds = holdout.skip(val_batches)
    augment = tf.keras.Sequential([layers.RandomFlip("horizontal"), layers.RandomRotation(0.12), layers.RandomZoom(0.12), layers.RandomContrast(0.15)])
    base = MobileNetV2(input_shape=(*IMAGE_SIZE, 3), include_top=False, weights="imagenet")
    base.trainable = False
    inputs = tf.keras.Input(shape=(*IMAGE_SIZE, 3))
    x = augment(inputs)
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.25)(x)
    outputs = layers.Dense(len(train_ds.class_names), activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(train_ds, validation_data=val_ds, epochs=8)
    base.trainable = True
    for layer in base.layers[:-25]:
        layer.trainable = False
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(train_ds, validation_data=val_ds, epochs=3)
    logger.info("test metrics: %s", model.evaluate(test_ds, verbose=0))
    OUT.mkdir(parents=True, exist_ok=True)
    model.save(OUT / "fruit_quality.keras")
    (OUT / "labels.json").write_text(json.dumps([c.replace(" ", "_") for c in train_ds.class_names]), encoding="utf-8")

if __name__ == "__main__":
    train()
