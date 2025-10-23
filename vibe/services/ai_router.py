"""AI router moved to `vibe.services`.

Provides a streaming generator that abstracts over multiple LLM backends.
"""
from typing import Callable, Generator, Optional


def stream_response(
    final_input: str,
    *,
    model: str = "openai/gpt-oss-20b",
    gemini_func: Optional[Callable[[str], str]] = None,
    groq_client=None,
    groq_available: bool = False,
    backend_callback: Optional[Callable[[str], None]] = None,
) -> Generator[str, None, None]:
    if gemini_func is not None:
        try:
            text = gemini_func(final_input)
            if text:
                if backend_callback:
                    try:
                        backend_callback('gemini')
                    except Exception:
                        pass
                yield text
                return
        except Exception:
            pass

    if groq_available and groq_client is not None:
        if backend_callback:
            try:
                backend_callback('groq')
            except Exception:
                pass
        gen = groq_client.responses.create(model=model, input=final_input, stream=True)
        for chunk in gen:
            try:
                piece = chunk.choices[0].delta.content or ""
            except Exception:
                piece = str(chunk)
            yield piece
        return

    raise RuntimeError("No LLM backend available: gemini_func not provided and groq not available")
