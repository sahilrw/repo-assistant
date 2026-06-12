"""Thin wrapper around the model API so the rest of the app never touches the SDK directly."""

import anthropic
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic()

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 4096

def ask(system: str, messages: list) -> str:
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=system,
        messages=messages,
    )

    return next(block.text for block in response.content if block.type == "text")

def stream(system: str, messages: list):
    with client.messages.stream(
        model=DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=system,
        messages=messages,
    ) as s:
        for text in s.text_stream:
            yield text