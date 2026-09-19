import hashlib
from typing import Union

def sha256(content: Union[str, bytes]) -> str:
    if isinstance(content, str):
        content = content.encode()
    hashed = hashlib.sha256(content)
    digest = hashed.hexdigest()
    return digest