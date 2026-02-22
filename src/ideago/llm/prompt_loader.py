"""Prompt template loader — reads .txt templates and fills placeholders.

Prompt 模板加载器，从文件读取模板并替换占位符。
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt template by name and substitute {key} placeholders.

    Args:
        name: Template file name without extension (e.g. "intent_parser").
        **kwargs: Key-value pairs for placeholder substitution.

    Returns:
        The rendered prompt string.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    template = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", value)
    return template
