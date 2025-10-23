"""Audio helpers (moved to vibe.services).

Copy of original audio helper implementations.
"""
import os
import tempfile
from gtts import gTTS


def _import_pygame():
    try:
        import pygame
        return pygame
    except Exception:
        return None


def init_audio() -> bool:
    pygame = _import_pygame()
    if not pygame:
        return False
    try:
        pygame.mixer.init()
        return True
    except Exception:
        return False


def speak_text(text: str, lang: str = "en", filename: str | None = None) -> str:
    if not filename:
        fd, filename = tempfile.mkstemp(prefix="vibemind_", suffix=".mp3")
        os.close(fd)

    tts = gTTS(text=text, lang=lang)
    tts.save(filename)

    pygame = _import_pygame()
    if pygame:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
        except Exception:
            pass

    return filename
