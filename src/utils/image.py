from io import BytesIO
from PIL import Image

def resize(image: bytes, size: tuple[int, int] = (150, 150)) -> BytesIO:
    buffer = BytesIO(image)
    img = Image.open(BytesIO(image))
    img = img.resize(size)
    # Save image to buffer
    img.save(buffer, format='png')
    # Move cursor to start
    buffer.seek(0)
    return buffer