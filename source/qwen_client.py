"""
qwen_client.py
--------------
Thin wrapper around the Qwen API (OpenAI-compatible endpoint via Alibaba Cloud
DashScope).  Reads credentials from environment variables:

    QWEN_API_KEY   — required
    QWEN_BASE_URL  — default: https://dashscope.aliyuncs.com/compatible-mode/v1
    QWEN_MODEL     — default: qwen-plus  (change to flash variant as needed)
"""

import os
from openai import OpenAI
from source.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen-plus"


def _get_client() -> OpenAI:
    api_key = os.environ.get("QWEN_API_KEY")
    if not api_key:
        raise EnvironmentError("QWEN_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key, base_url=_BASE_URL)


def _get_model() -> str:
    return os.environ.get("QWEN_MODEL_ID", _DEFAULT_MODEL)


def chat(system_prompt: str, user_message: str) -> str:
    """
    Send a chat completion request to the Qwen API.

    Args:
        system_prompt: Instruction context for the model.
        user_message:  The user-facing message / document content.

    Returns:
        The model's reply as a plain string.

    Raises:
        EnvironmentError: If QWEN_API_KEY is missing.
        openai.OpenAIError: On API-level failures.
    """
    client = _get_client()
    model = _get_model()

    logger.debug("Calling Qwen model '%s' with %d user chars.", model, len(user_message))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    reply = response.choices[0].message.content or ""
    logger.debug("Qwen response: %d chars received.", len(reply))
    return reply
