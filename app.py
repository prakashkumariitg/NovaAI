"""Streamlit frontend for the AI-powered meeting assistant."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

import streamlit as st
from dotenv import load_dotenv

from audio_processing import transcribe_audio
from llm_chains import generate_meeting_record, refine_transcript

load_dotenv()

st.set_page_config(page_title="AI Meeting Assistant",
                   page_icon="🎙️", layout="wide")


def save_uploaded_file(uploaded_file: Any) -> Path:
    """Persist an uploaded file to a temporary location and return its path."""
    if uploaded_file is None:
        raise ValueError("No audio file was uploaded.")

    suffix = Path(uploaded_file.name).suffix or ".wav"
    temp_dir = Path(tempfile.mkdtemp(prefix="meeting_assistant_"))
    temp_path = temp_dir / f"uploaded_audio{suffix}"
    with temp_path.open("wb") as output_file:
        while True:
            chunk = uploaded_file.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)
    return temp_path


def build_human_readable_record(record: Dict[str, Any]) -> str:
    """Format the meeting record as a readable Markdown document."""
    lines: list[str] = []
    lines.append("# Meeting Record")
    lines.append("")
    lines.append("## Summary")
    lines.append(str(record.get("summary", "")).strip())
    lines.append("")
    lines.append("## Minutes")
    for idx, item in enumerate(record.get("minutes", []), start=1):
        topic = item.get("topic", "Untitled") if isinstance(
            item, dict) else str(item)
        details = item.get("details", "") if isinstance(item, dict) else ""
        time_value = item.get("time", "Unspecified") if isinstance(
            item, dict) else "Unspecified"
        lines.append(f"{idx}. **{time_value}** - {topic}")
        if details:
            lines.append(f"   - {details}")
    lines.append("")
    lines.append("## Decisions")
    decisions = record.get("decisions", [])
    if not decisions:
        lines.append("- None recorded.")
    else:
        for idx, decision in enumerate(decisions, start=1):
            lines.append(f"{idx}. {decision}")
    lines.append("")
    lines.append("## Action Items")
    tasks = record.get("tasks", [])
    if not tasks:
        lines.append("- No action items identified.")
    else:
        for idx, task in enumerate(tasks, start=1):
            if isinstance(task, dict):
                lines.append(
                    f"{idx}. **Task:** {task.get('task', 'Unspecified')} | "
                    f"**Owner:** {task.get('owner', 'Unspecified')} | "
                    f"**Deadline:** {task.get('deadline', 'Unspecified')}"
                )
            else:
                lines.append(f"{idx}. {task}")
    return "\n".join(lines) + "\n"


def render_process_results(processed_data: Dict[str, Any]) -> None:
    """Display the transcripts and generated record in the app UI."""
    raw_transcript = processed_data["raw_transcript"]
    refined_transcript = processed_data["refined_transcript"]
    meeting_record = processed_data["meeting_record"]

    st.success("Processing complete. Results are ready.")

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Raw Transcript")
        st.text_area(
            "Raw transcript",
            raw_transcript,
            height=300,
            disabled=True,
            label_visibility="collapsed",
        )
    with col_right:
        st.subheader("Refined Transcript")
        st.text_area(
            "Refined transcript",
            refined_transcript,
            height=300,
            disabled=True,
            label_visibility="collapsed",
        )

    st.subheader("Structured Meeting Record")
    st.markdown(f"**Summary:** {meeting_record.get('summary', '')}")

    tab_minutes, tab_decisions, tab_tasks = st.tabs(
        ["Minutes", "Decisions", "Action Items"])

    with tab_minutes:
        minutes = meeting_record.get("minutes", [])
        if not minutes:
            st.info("No minutes were found in the transcript.")
        else:
            for minute in minutes:
                if isinstance(minute, dict):
                    st.markdown(
                        f"**{minute.get('time', 'Unspecified')}** — **{minute.get('topic', 'Untitled')}**\n\n"
                        f"{minute.get('details', '')}"
                    )
                else:
                    st.markdown(str(minute))

    with tab_decisions:
        decisions = meeting_record.get("decisions", [])
        if not decisions:
            st.info("No decisions were explicitly stated in the recording.")
        else:
            for decision in decisions:
                st.markdown(f"- {decision}")

    with tab_tasks:
        tasks = meeting_record.get("tasks", [])
        if not tasks:
            st.info("No action items were explicitly identified in the transcript.")
        else:
            for task in tasks:
                if isinstance(task, dict):
                    st.markdown(
                        f"- **Task:** {task.get('task', 'Unspecified')}  "
                        f"**Owner:** {task.get('owner', 'Unspecified')}  "
                        f"**Deadline:** {task.get('deadline', 'Unspecified')}"
                    )
                else:
                    st.markdown(f"- {task}")

    human_readable = build_human_readable_record(meeting_record)
    export_payload = {
        "raw_transcript": raw_transcript,
        "refined_transcript": refined_transcript,
        **meeting_record,
    }
    json_payload = json.dumps(export_payload, indent=2, ensure_ascii=False)

    st.download_button(
        label="Download raw transcript (.txt)",
        data=raw_transcript,
        file_name="raw_transcript.txt",
        mime="text/plain",
    )
    st.download_button(
        label="Download refined transcript (.txt)",
        data=refined_transcript,
        file_name="refined_transcript.txt",
        mime="text/plain",
    )

    st.download_button(
        label="Download meeting record (.md)",
        data=human_readable,
        file_name="meeting_record.md",
        mime="text/markdown",
    )
    st.download_button(
        label="Download structured output (.json)",
        data=json_payload,
        file_name="meeting_record.json",
        mime="application/json",
    )


def main() -> None:
    """Run the Streamlit frontend for the meeting assistant."""
    st.title("AI Meeting Assistant")
    st.caption(
        "Upload a meeting recording to get a raw transcript, refined transcript, and structured output.")

    with st.sidebar:
        st.header("Configuration")
        configured_api_key = (
            os.getenv("API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or ""
        )
        api_key = st.text_input(
            "Provider API key",
            value=st.session_state.get("provider_api_key", configured_api_key),
            type="password",
            key="provider_api_key",
            help="Used only for this Streamlit session and is not written to disk.",
        )

        base_url = st.text_input(
            "OpenAI-compatible base URL (optional)",
            value=os.getenv("OPENAI_BASE_URL", ""),
            placeholder="https://api.openai.com/v1",
            key="provider_base_url",
        )

        refinement_model = st.text_input(
            "Refinement model",
            value=os.getenv("REFINEMENT_MODEL", "gpt-4o-mini"),
            key="refinement_model",
        )

        documentation_model = st.text_input(
            "Documentation model",
            value=os.getenv("DOCUMENTATION_MODEL", "gpt-4o"),
            key="documentation_model",
        )

        st.write("Expected environment variables:")
        st.code(
            "API_KEY\nREFINEMENT_MODEL=gpt-4o-mini\nDOCUMENTATION_MODEL=gpt-4o\nWHISPER_MODEL=base.en")
        st.caption(
            "Set OPENAI_BASE_URL if you are using a compatible provider other than OpenAI.")
        if not api_key:
            st.warning("Enter a provider API key before processing audio.")

    uploaded_file = st.file_uploader(
        "Upload an English meeting audio file",
        type=["wav", "mp3", "m4a", "aac", "flac", "ogg", "webm"],
        accept_multiple_files=False,
    )

    if not uploaded_file:
        st.info("Please upload an audio file to begin processing.")
        return

    upload_id = (
        getattr(uploaded_file, "file_id", None),
        uploaded_file.name,
        uploaded_file.size,
    )
    if st.session_state.get("processed_upload_id") != upload_id:
        st.session_state.pop("processed_data", None)
        st.session_state["processed_upload_id"] = upload_id

    if st.button("Process audio", type="primary", disabled=not bool(api_key)):
        temp_audio_path = None
        try:
            temp_audio_path = save_uploaded_file(uploaded_file)
            with st.status("Processing meeting audio...", expanded=True) as processing_status:
                processing_status.write("Validating audio and transcribing...")
                raw_transcript = transcribe_audio(temp_audio_path)

                processing_status.write("Refining the transcript...")
                refined_result = refine_transcript(
                    raw_transcript,
                    refinement_model,
                    api_key=api_key,
                    base_url=base_url,
                )
                refined_transcript = refined_result["refined_transcript"]

                processing_status.write("Generating minutes, decisions, and action items...")
                meeting_record = generate_meeting_record(
                    refined_transcript,
                    documentation_model,
                    api_key=api_key,
                    base_url=base_url,
                )
                processing_status.update(
                    label="Processing complete",
                    state="complete",
                    expanded=False,
                )

            processed_data = {
                "raw_transcript": raw_transcript,
                "refined_transcript": refined_transcript,
                "meeting_record": meeting_record,
            }

            st.session_state["processed_data"] = processed_data
            render_process_results(processed_data)
            return

        except Exception as exc:
            st.error(f"Processing failed: {exc}")
            st.markdown(
                "Please ensure the file is a valid, non-empty audio recording and that your API key and model configuration are set correctly."
            )
            return
        finally:
            if temp_audio_path is not None:
                shutil.rmtree(temp_audio_path.parent, ignore_errors=True)

    if "processed_data" in st.session_state:
        render_process_results(st.session_state["processed_data"])


if __name__ == "__main__":
    main()
