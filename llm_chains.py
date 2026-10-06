"""Two-stage LLM orchestration for transcript refinement and meeting documentation."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from openai import OpenAI

from prompts import MEETING_DOCUMENTATION_SYSTEM_PROMPT, TRANSCRIPT_REFINEMENT_SYSTEM_PROMPT


def _get_setting(name: str) -> str | None:
    """Read a setting from the process environment or Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        return None

    return str(secret_value) if secret_value else None


def _get_api_key() -> str:
    """Return the configured API key for the OpenAI-compatible provider."""
    api_key = (
        _get_setting("API_KEY")
        or _get_setting("OPENAI_API_KEY")
        or _get_setting("GROQ_API_KEY")
    )
    if not api_key:
        raise ValueError(
            "API_KEY is not set. Please export your API key before running the app."
        )
    return api_key


def _build_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    """Create an OpenAI-compatible client using either default or configured endpoints."""
    selected_base_url = base_url or _get_setting("OPENAI_BASE_URL") or _get_setting("API_BASE_URL")
    return OpenAI(api_key=api_key or _get_api_key(), base_url=selected_base_url)


def _select_model(configured_model: str | None) -> str:
    """Return a configured model, migrating retired Groq Llama IDs when needed."""
    selected_model = configured_model or "gpt-4o-mini"
    base_url = (_get_setting("OPENAI_BASE_URL") or _get_setting("API_BASE_URL") or "").lower()
    retired_groq_models = {
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
    }
    if "api.groq.com" in base_url and selected_model in retired_groq_models:
        return "openai/gpt-oss-20b"
    return selected_model


def _extract_json(raw_text: str) -> Dict[str, Any]:
    """Extract a JSON object from a LLM response, even when fenced in markdown."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"The model returned invalid JSON: {raw_text[:400]}")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ValueError(f"The model returned invalid JSON: {raw_text[:400]}") from exc

    if not isinstance(payload, dict):
        raise ValueError("The model response did not contain a JSON object as required.")

    return payload


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """Call an OpenAI-compatible chat completion endpoint and parse the JSON payload."""
    client = _build_client(api_key=api_key, base_url=base_url)
    retry_prompt = (
        f"{user_prompt}\n\nReturn only one complete, valid JSON object. "
        "Do not include markdown fences or commentary."
    )

    for attempt_prompt in (user_prompt, retry_prompt):
        request_options: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": attempt_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if model_name.startswith("openai/gpt-oss"):
            request_options["reasoning_effort"] = "low"

        completion = client.chat.completions.create(**request_options)
        content = completion.choices[0].message.content
        if content is None or not str(content).strip():
            continue
        try:
            return _extract_json(str(content))
        except ValueError:
            continue

    raise ValueError("The model returned invalid or empty JSON after two attempts.")


def refine_transcript(
    raw_transcript: str,
    model_name: str | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Dict[str, str]:
    """Correct transcript noise and domain-specific terminology without altering meaning."""
    if not raw_transcript or not raw_transcript.strip():
        raise ValueError("A valid raw transcript is required for refinement.")

    selected_model = _select_model(
        model_name or _get_setting("REFINEMENT_MODEL") or _get_setting("LLM_MODEL")
    )
    words = raw_transcript.split()
    chunks = [" ".join(words[index:index + 1200]) for index in range(0, len(words), 1200)]
    refined_chunks: list[str] = []
    for chunk in chunks:
        user_prompt = (
            "Correct recognition errors in the transcript while preserving meaning exactly. "
            "Preserve intent, commitments, names, numbers, dates, authorizations, negation, and deadlines.\n\n"
            f"<transcript>\n{chunk}\n</transcript>"
        )
        payload = _call_llm(
            TRANSCRIPT_REFINEMENT_SYSTEM_PROMPT,
            user_prompt,
            selected_model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=6000,
        )
        refined_text = str(payload.get("refined_transcript", "")).strip()
        if not refined_text:
            raise ValueError("Refinement output was missing a non-empty transcript.")
        refined_chunks.append(refined_text)

    return {"refined_transcript": "\n\n".join(refined_chunks)}


def generate_meeting_record(
    refined_transcript: str,
    model_name: str | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Dict[str, Any]:
    """Generate structured meeting minutes, decisions, and tasks from the refined transcript."""
    if not refined_transcript or not refined_transcript.strip():
        raise ValueError("A valid refined transcript is required for meeting documentation.")

    selected_model = _select_model(
        model_name or _get_setting("DOCUMENTATION_MODEL") or _get_setting("LLM_MODEL")
    )
    user_prompt = (
        "Create a factual meeting record from the transcript below. Do not invent missing information. "
        "For every task, set owner and deadline to 'Unspecified' unless explicitly stated in the meeting.\n\n"
        f"<transcript>\n{refined_transcript}\n</transcript>"
    )

    payload = _call_llm(
        MEETING_DOCUMENTATION_SYSTEM_PROMPT,
        user_prompt,
        selected_model,
        api_key=api_key,
        base_url=base_url,
        max_tokens=8000,
    )

    required_keys = {"summary", "minutes", "decisions", "tasks"}
    missing = required_keys.difference(payload.keys())
    if missing:
        raise ValueError(f"Meeting record is missing required keys: {sorted(missing)}")

    record = {
        "summary": str(payload.get("summary", "")).strip(),
        "minutes": payload.get("minutes"),
        "decisions": payload.get("decisions"),
        "tasks": payload.get("tasks"),
    }
    for key in ("minutes", "decisions", "tasks"):
        if not isinstance(record[key], list):
            raise ValueError(f"Meeting record field '{key}' must be a list.")

    for task in record["tasks"]:
        if not isinstance(task, dict):
            continue
        if not str(task.get("owner") or "").strip():
            task["owner"] = "Unspecified"
        if not str(task.get("deadline") or "").strip():
            task["deadline"] = "Unspecified"

    return record
