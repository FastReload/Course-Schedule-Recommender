from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass
class TurnResult:
    final_text: str
    events: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    tool_responses: list[dict[str, Any]]


def _safe_model_dump(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass

    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # pydantic v1
        except Exception:
            pass

    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"repr": repr(obj)}


def _extract_text_from_event(event: Any) -> str:
    # Event extends LlmResponse; best-effort text extraction.
    for attr in ("text", "output_text", "content"):
        value = getattr(event, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    parts = getattr(event, "parts", None)
    if parts:
        chunks: list[str] = []
        for part in parts:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text:
                chunks.append(text)
        if chunks:
            return "".join(chunks).strip()

    # Last resort
    dumped = _safe_model_dump(event)
    for key in ("text", "output_text"):
        value = dumped.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def run_turn(*, runner: Any, user_id: str, session_id: str, message: str) -> TurnResult:
    """Run one user message through ADK Runner.

    Uses runner.run(...) (sync generator). Collects events and extracts the final
    assistant text for the turn.
    """

    events_dump: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    tool_responses: list[dict[str, Any]] = []

    final_text: Optional[str] = None
    last_assistant_text: Optional[str] = None

    for event in runner.run(user_id=user_id, session_id=session_id, new_message=message):
        events_dump.append(_safe_model_dump(event))

        # Tool call/response extraction (best effort)
        try:
            for fc in event.get_function_calls() or []:
                tool_calls.append(_safe_model_dump(fc))
        except Exception:
            pass

        try:
            for fr in event.get_function_responses() or []:
                tool_responses.append(_safe_model_dump(fr))
        except Exception:
            pass

        author = getattr(event, "author", None)
        if author and author != "user":
            text = _extract_text_from_event(event)
            if text:
                last_assistant_text = text

            try:
                is_final = bool(event.is_final_response())
            except Exception:
                is_final = False

            if is_final and text:
                final_text = text

    if not final_text:
        final_text = last_assistant_text or ""

    return TurnResult(
        final_text=final_text,
        events=events_dump,
        tool_calls=tool_calls,
        tool_responses=tool_responses,
    )
