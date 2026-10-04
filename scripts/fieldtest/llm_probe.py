#!/usr/bin/env python3
"""Probe the analytics LLM client against OMLX (field-test debugging)."""
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

from analytics.llm_client import LLMClient  # noqa: E402


async def main() -> None:
    client = LLMClient()
    result = await client.chat(
        "Reply JSON only: which tool lists files? tools: run_shell, read_file",
        max_tokens=64,
    )
    print("RESULT", repr(result))
    print("RESPONSES", client.responses())


asyncio.run(main())
