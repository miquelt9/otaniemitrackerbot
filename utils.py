import logging
import string
import re
from typing import Optional


_translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))


def remove_punctuation(input_string: str) -> str:
    return input_string.translate(_translator)


def extract_word(input_string: str) -> Optional[str]:
    pattern = r"'([^']+)'|\"([^\"]+)\"|(\w+)"
    match = re.search(pattern, input_string)
    if match:
        return (match.group(1) or match.group(2) or match.group(3)).lower()
    return None


def safe_preview(text: str, limit: int = 100) -> str:
    return (text or '')[:limit]


