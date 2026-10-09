#!/usr/bin/env python3
"""OMLX-driven tool-using agent (M23 FT-11), with a deterministic fallback.

Runs inside the recorder container, emits real hook frames for every tool call,
and uses a local OMLX (OpenAI-compatible) endpoint for reasoning. If OMLX is
unreachable, it falls back to a fixed action list so the recorder path is still
exercised (the case reports ``llm: fallback``).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/work/packages/python-sdk/src")
from agentwatch.hook import build_message, default_socket_path, send  # noqa: E402

ALLOWED = {"echo", "ls", "cat", "pwd"}
SCRIPTED = [
    ("run_shell", {"command": "echo hello"}),
    ("read_file", {"path": "/etc/hostname"}),
    ("run_shell", {"command": "ls -la /data/agentwatch"}),
]
TOOLS = [
    {
        "type": "function",
        "function": {"name": "run_shell", "description": "Run an allow-listed shell command",
                     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}},
    },
    {
        "type": "function",
        "function": {"name": "read_file", "description": "Read a file",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
    },
]


def _call_tool(name: str, args: dict) -> str:
    if name == "run_shell":
        command = str(args.get("command", ""))
        first = command.strip().split(" ", 1)[0]
        if first not in ALLOWED:
            return f"DENIED: {first} not allow-listed"
        try:
            return subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5,
                                  check=False).stdout[:2000]  # noqa: S602
        except (OSError, subprocess.SubprocessError) as exc:
            return f"error: {exc}"
    if name == "read_file":
        try:
            return open(str(args.get("path")), encoding="utf-8").read()[:2000]  # noqa: SIM115
        except OSError as exc:
            return f"error: {exc}"
    return f"unknown tool {name}"


def _chat_url(base_url: str) -> str:
    """Normalize an OpenAI-compatible base URL to its chat-completions path.

    Accepts either a root (``http://host:8000``) or a versioned base
    (``http://host:8000/v1``); OMLX is the versioned form.
    """
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return base + "/chat/completions"


def _llm_log(entry: dict) -> None:
    """Append one LLM interaction to the capture file (for the case artifacts).

    Path from ``FT_LLM_IO`` (default ``/data/agentwatch/test-llm-io.jsonl``, which
    the harness copies into the case artifacts). Never raises.
    """
    path = os.environ.get("FT_LLM_IO", "/data/agentwatch/test-llm-io.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass


def _omlx_actions(base_url: str, model: str) -> list[tuple[str, dict]]:
    prompt = "Use one tool to list the current directory. Reply as a tool call."
    request_body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "tools": TOOLS,
        "temperature": 0,
        # Match the predecessor's validation setup: JSON mode, no reasoning.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    body = json.dumps(request_body).encode()
    request = urllib.request.Request(  # noqa: S310
        _chat_url(base_url),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _llm_log({"url": _chat_url(base_url), "request": request_body, "error": str(exc)})
        raise
    _llm_log({"url": _chat_url(base_url), "request": request_body, "response": payload})
    calls = payload["choices"][0]["message"].get("tool_calls") or []
    actions: list[tuple[str, dict]] = []
    for call in calls:
        fn = call["function"]
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        actions.append((fn["name"], args))
    return actions or SCRIPTED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default="ft-llm")
    parser.add_argument("--socket", default=os.environ.get("AGENTWATCH_SOCKET") or default_socket_path())
    args = parser.parse_args(argv)

    base_url = os.environ.get("OMLX_BASE_URL", "http://host.docker.internal:8000/v1")
    model = os.environ.get("OMLX_MODEL", "Qwen3-4B-Instruct-2507-4bit")
    mode = "scripted"
    actions = SCRIPTED
    if base_url and model:
        try:
            actions = _omlx_actions(base_url, model)
            mode = "omlx"
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            mode = "scripted"
            _llm_log({"url": _chat_url(base_url), "model": model, "error": str(exc), "fallback": True})

    delivered = 0
    tool_io: list[dict] = []
    for index, (name, tool_args) in enumerate(actions):
        call = f"{args.session}-{index}"
        send(build_message("pre", {"session_id": args.session, "tool_name": name,
                                   "tool_use_id": call, "tool_input": tool_args}), socket_path=args.socket)
        result = _call_tool(name, tool_args)
        ok = send(build_message("post", {"session_id": args.session, "tool_name": name,
                                         "tool_use_id": call, "tool_response": {"result": result},
                                         "duration_ms": 1}), socket_path=args.socket)
        delivered += int(ok)
        tool_io.append({"call": call, "tool": name, "args": tool_args, "result": result,
                        "delivered": bool(ok)})
    _llm_log({"mode": mode, "actions": tool_io})

    print(f"drive-agent: mode={mode} calls={len(actions)} delivered={delivered}")
    return 0 if delivered == len(actions) else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
