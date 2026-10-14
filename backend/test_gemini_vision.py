from pathlib import Path

from PIL import Image

from app.model.fruit_scope import fruit_vision_classifier


def main():
    image_path = input("Enter image path: ").strip().strip('"')
    path = Path(image_path)

    if not path.is_file():
        print("ERROR: Image file not found.")
        return

    try:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            jpeg_path = Path(directory) / "image.jpg"
            with Image.open(path) as image:
                image.convert("RGB").save(jpeg_path, format="JPEG")
            result = fruit_vision_classifier.classify(jpeg_path)
        print("Gemini fruit and quality:", result)
    except Exception as exc:
        print("Image classification failed:", str(exc))


if __name__ == "__main__":
    main()