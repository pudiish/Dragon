"""Top-level package exports for vibe.

Expose `clients`, `utils`, and `services` to make imports shorter and maintain
backwards compatibility during refactors.
"""
from . import clients, utils

__all__ = ["clients", "utils"]
"""VibeMind helper package - lightweight adapters and contracts.

This package intentionally avoids importing heavy optional dependencies at
package-import time (audio, groq, openai) so that the application can be
imported in environments where optional packages are missing. Import the
submodules directly when you need them (for example `from vibe import
config` or `from vibe import rag`).
"""

from .config import settings

__all__ = [
    "settings",
]
