from __future__ import annotations

import os
import re
import textwrap
import uuid
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from frontend.adk_runtime import run_turn


APP_NAME = "schedule_recommender_ui"


STEP_ID = "id"
STEP_MAJOR = "major"
STEP_TERM = "term"
STEP_COURSES = "courses"
STEP_CHAT = "chat"


def _init_state() -> None:
    if "chat" not in st.session_state:
        st.session_state.chat = []  # [{role, content, ts}]

    if "student_id" not in st.session_state:
        st.session_state.student_id = ""

    if "verified" not in st.session_state:
        st.session_state.verified = False

    if "verified_majors" not in st.session_state:
        st.session_state.verified_majors = []

    if "verification_message" not in st.session_state:
        st.session_state.verification_message = ""

    if "major" not in st.session_state:
        st.session_state.major = ""

    if "quarter" not in st.session_state:
        st.session_state.quarter = ""

    if "year" not in st.session_state:
        st.session_state.year = ""

    if "courses" not in st.session_state:
        st.session_state.courses = ""

    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = STEP_ID

    if "adk_user_id" not in st.session_state:
        st.session_state.adk_user_id = "local_user"

    if "adk_session_id" not in st.session_state:
        st.session_state.adk_session_id = f"ui-{uuid.uuid4().hex}"

    if "debug" not in st.session_state:
        st.session_state.debug = {
            "events": [],
            "tool_calls": [],
            "tool_responses": [],
        }


@st.cache_resource
def _get_runner():
    # Delay imports so the UI can render helpful errors if deps are missing.
    try:
        from google.adk.runners import InMemoryRunner
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing ADK dependency. Install with `poetry install` or `pip install google-adk`."
        ) from e

    try:
        from main_agent.agent import root_agent
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Could not import the ADK root agent. Expected `main_agent.agent.root_agent`."
        ) from e

    return InMemoryRunner(agent=root_agent, app_name=APP_NAME)


def _get_or_create_session_id(runner, user_id: str, session_id: str) -> str:
    session = runner.session_service.get_session_sync(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        session = runner.session_service.create_session_sync(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )
    return session.id


def _export_markdown(chat: list[dict]) -> str:
    lines = [f"# Schedule Recommender Chat Export\n\nExported: {datetime.now().isoformat()}\n"]
    for msg in chat:
        role = msg.get("role", "")
        content = msg.get("content", "")
        ts = msg.get("ts", "")
        lines.append(f"## {role.capitalize()} ({ts})\n\n{content}\n")
    return "\n".join(lines)


def _env_status():
    keys = [
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "CS_CORPUS",
        "ME_CORPUS",
        "BIGQUERY_STUDENT_INFO_TABLE",
    ]
    rows = []
    for k in keys:
        v = os.getenv(k)
        ok = bool(v)
        rows.append({"env": k, "set": "yes" if ok else "no", "value_preview": (v[:6] + "…") if v else ""})
    return rows


def _reset_onboarding(*, keep_student_id: bool = True) -> None:
    sid = st.session_state.student_id if keep_student_id else ""
    st.session_state.chat = []
    st.session_state.debug = {"events": [], "tool_calls": [], "tool_responses": []}

    st.session_state.student_id = sid
    st.session_state.verified = False
    st.session_state.verified_majors = []
    st.session_state.verification_message = ""

    st.session_state.major = ""
    st.session_state.quarter = ""
    st.session_state.year = ""
    st.session_state.courses = ""

    st.session_state.adk_user_id = "local_user"
    st.session_state.adk_session_id = f"ui-{uuid.uuid4().hex}"
    st.session_state.onboarding_step = STEP_ID


def _parse_majors_from_tool_text(text: str) -> list[str]:
    majors: list[str] = []
    for label in ("First Major", "Second Major"):
        m = re.search(rf"{re.escape(label)}:\s*(.+)", text)
        if m:
            val = m.group(1).strip()
            # Strip any trailing artifacts.
            val = val.splitlines()[0].strip()
            if val and val.lower() not in {"none", "null"}:
                majors.append(val)
    # Dedupe while preserving order.
    seen = set()
    out = []
    for maj in majors:
        if maj not in seen:
            seen.add(maj)
            out.append(maj)
    return out


def _tool_text_from_turn(result) -> str:
    # Best-effort extraction of the BigQuery tool output.
    chunks: list[str] = []
    for item in (result.tool_responses or []):
        # The structure varies; try common shapes.
        if isinstance(item, dict):
            for key in ("content", "result", "response", "output"):
                val = item.get(key)
                if isinstance(val, str) and val.strip():
                    chunks.append(val.strip())
        else:
            s = str(item)
            if s.strip():
                chunks.append(s.strip())
    return "\n".join(chunks).strip()


def _verify_student_id_with_adk(*, runner, student_id: str) -> tuple[bool, list[str], str, str]:
    # Returns: (verified, majors, user_facing_message, tool_text)
    verify_msg = (
        "Please verify my student ID using the student_data_tool and tell me whether you found a record. "
        "Then summarize my major(s). My student ID is: "
        f"{student_id}"
    )

    sid = _get_or_create_session_id(
        runner,
        user_id=student_id,
        session_id=st.session_state.adk_session_id,
    )

    result = run_turn(
        runner=runner,
        user_id=student_id,
        session_id=sid,
        message=verify_msg,
    )

    tool_text = _tool_text_from_turn(result)
    majors = _parse_majors_from_tool_text(tool_text)

    combined = "\n".join([tool_text, result.final_text or ""]).lower()
    if "bigquery table id" in combined and "not configured" in combined:
        return False, [], "Student verification is not configured (missing BIGQUERY_STUDENT_INFO_TABLE).", tool_text

    if "no student information found" in combined:
        return False, [], "No student record found for that Student ID.", tool_text

    if "error retrieving student information" in combined:
        return False, [], "Could not verify Student ID due to a BigQuery error.", tool_text

    # If we got majors, treat that as a successful verification.
    if majors:
        return True, majors, "Student ID verified.", tool_text

    # Otherwise, fall back to ADK's response.
    return True, [], "Student ID verified (record found).", tool_text


def _send_system_context_message(*, runner, user_id: str, message: str) -> None:
    sid = _get_or_create_session_id(
        runner,
        user_id=user_id,
        session_id=st.session_state.adk_session_id,
    )
    result = run_turn(
        runner=runner,
        user_id=user_id,
        session_id=sid,
        message=message,
    )

    answer = result.final_text.strip() or "(No text response produced.)"
    st.session_state.chat.append({"role": "user", "content": message, "ts": datetime.now().strftime("%H:%M:%S")})
    st.session_state.chat.append(
        {"role": "assistant", "content": answer, "ts": datetime.now().strftime("%H:%M:%S")}
    )
    st.session_state.debug["events"].append(result.events)
    st.session_state.debug["tool_calls"].append(result.tool_calls)
    st.session_state.debug["tool_responses"].append(result.tool_responses)


def main() -> None:
    load_dotenv()
    _init_state()

    st.set_page_config(page_title="Schedule Recommender", page_icon="📅", layout="wide")

    st.title("Schedule Recommender")
    st.caption("Plan your next quarter with an ADK-powered assistant")

    with st.sidebar:
        st.subheader("Student")

        st.progress(
            {STEP_ID: 0.2, STEP_MAJOR: 0.4, STEP_TERM: 0.6, STEP_COURSES: 0.8, STEP_CHAT: 1.0}.get(
                st.session_state.onboarding_step,
                0.2,
            )
        )

        # Step 1: Student ID + verification
        if st.session_state.onboarding_step == STEP_ID:
            st.session_state.student_id = st.text_input(
                "Student ID",
                value=st.session_state.student_id,
                placeholder="Enter your student ID",
            )

            can_verify = bool((st.session_state.student_id or "").strip())
            if st.button("Verify Student ID", type="primary", use_container_width=True, disabled=not can_verify):
                st.session_state.verification_message = ""
                st.session_state.verified_majors = []
                st.session_state.verified = False
                st.session_state.adk_user_id = (st.session_state.student_id or "").strip()
                st.session_state.adk_session_id = f"ui-{uuid.uuid4().hex}"

                try:
                    runner = _get_runner()
                    with st.spinner("Verifying…"):
                        ok, majors, msg, tool_text = _verify_student_id_with_adk(
                            runner=runner,
                            student_id=st.session_state.adk_user_id,
                        )
                    st.session_state.verified = ok
                    st.session_state.verified_majors = majors
                    st.session_state.verification_message = msg

                    if ok:
                        st.session_state.onboarding_step = STEP_MAJOR
                except Exception as e:
                    st.session_state.verification_message = str(e)

                st.rerun()

            if st.session_state.verification_message:
                if st.session_state.verified:
                    st.success(st.session_state.verification_message)
                else:
                    st.error(st.session_state.verification_message)

        # Step 2: Confirm major (and route)
        elif st.session_state.onboarding_step == STEP_MAJOR:
            majors = st.session_state.verified_majors or []
            options = majors + (["Other"] if majors else ["Other"])
            selection = st.selectbox("Major", options=options, index=0)
            if selection == "Other":
                st.session_state.major = st.text_input("Enter major", value=st.session_state.major, placeholder="e.g., CS")
            else:
                st.session_state.major = selection

            can_continue = bool((st.session_state.major or "").strip())
            if st.button("Confirm major", type="primary", use_container_width=True, disabled=not can_continue):
                try:
                    runner = _get_runner()
                    msg = (
                        f"I confirm my major is {st.session_state.major.strip()}. "
                        "Please route me to the appropriate scheduling subagent for my major."
                    )
                    with st.spinner("Routing…"):
                        _send_system_context_message(
                            runner=runner,
                            user_id=st.session_state.adk_user_id,
                            message=msg,
                        )
                    st.session_state.onboarding_step = STEP_TERM
                except Exception as e:
                    st.error(str(e))
                st.rerun()

        # Step 3: Term
        elif st.session_state.onboarding_step == STEP_TERM:
            col_q, col_y = st.columns(2)
            with col_q:
                st.session_state.quarter = st.selectbox(
                    "Quarter",
                    options=["", "Fall", "Winter", "Spring", "Summer"],
                    index=["", "Fall", "Winter", "Spring", "Summer"].index(
                        st.session_state.quarter if st.session_state.quarter in ["", "Fall", "Winter", "Spring", "Summer"] else ""
                    ),
                )
            with col_y:
                st.session_state.year = st.text_input("Year", value=st.session_state.year, placeholder="2026")

            can_continue = bool((st.session_state.quarter or "").strip()) and bool((st.session_state.year or "").strip())
            if st.button("Continue", type="primary", use_container_width=True, disabled=not can_continue):
                st.session_state.onboarding_step = STEP_COURSES
                st.rerun()

        # Step 4: Desired courses
        elif st.session_state.onboarding_step == STEP_COURSES:
            st.session_state.courses = st.text_area(
                "Courses (comma-separated)",
                value=st.session_state.courses,
                placeholder="CS010C, CS111, MATH010B",
                height=90,
            )

            can_start = bool((st.session_state.courses or "").strip())
            if st.button("Start chat", type="primary", use_container_width=True, disabled=not can_start):
                try:
                    runner = _get_runner()
                    term = f"{st.session_state.quarter.strip()} {st.session_state.year.strip()}".strip()
                    starter = (
                        f"My student ID is {st.session_state.adk_user_id}. "
                        f"My major is {st.session_state.major.strip()}. "
                        f"I am planning for {term}. "
                        f"I want to take (or I’m interested in): {st.session_state.courses.strip()}. "
                        "Please propose a realistic schedule and explain prerequisites/tradeoffs."
                    )
                    with st.spinner("Starting…"):
                        _send_system_context_message(
                            runner=runner,
                            user_id=st.session_state.adk_user_id,
                            message=starter,
                        )
                    st.session_state.onboarding_step = STEP_CHAT
                except Exception as e:
                    st.error(str(e))
                st.rerun()

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("New chat", use_container_width=True):
                # Keep onboarding context but clear the conversation.
                st.session_state.chat = []
                st.session_state.debug = {"events": [], "tool_calls": [], "tool_responses": []}
                st.session_state.adk_session_id = f"ui-{uuid.uuid4().hex}"
                st.rerun()

        with col_b:
            export = _export_markdown(st.session_state.chat)
            st.download_button(
                "Export",
                data=export,
                file_name="schedule_recommender_chat.md",
                mime="text/markdown",
                use_container_width=True,
            )

        if st.button("Reset onboarding", use_container_width=True):
            _reset_onboarding(keep_student_id=True)
            st.rerun()

        st.divider()
        with st.expander("Environment", expanded=False):
            st.dataframe(_env_status(), use_container_width=True, hide_index=True)
            st.caption("Put these in a .env file at repo root.")

        show_debug = st.toggle("Show debug panel", value=False)

    left, right = st.columns([2, 1], gap="large")

    with left:
        if st.session_state.onboarding_step != STEP_CHAT:
            st.info(
                {
                    STEP_ID: "Step 1: Verify your Student ID.",
                    STEP_MAJOR: "Step 2: Confirm your major (we’ll route to the right agent).",
                    STEP_TERM: "Step 3: Enter the quarter and year you’re planning for.",
                    STEP_COURSES: "Step 4: Enter the courses you want, then start the chat.",
                }.get(st.session_state.onboarding_step, "Complete onboarding to begin chatting.")
            )

        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = None
        if st.session_state.onboarding_step == STEP_CHAT:
            prompt = st.chat_input("Ask for schedule recommendations…")
        if prompt:
            st.session_state.chat.append(
                {"role": "user", "content": prompt, "ts": datetime.now().strftime("%H:%M:%S")}
            )

            with st.chat_message("assistant"):
                try:
                    runner = _get_runner()
                    sid = _get_or_create_session_id(
                        runner,
                        user_id=st.session_state.adk_user_id,
                        session_id=st.session_state.adk_session_id,
                    )

                    with st.spinner("Thinking…"):
                        result = run_turn(
                            runner=runner,
                            user_id=st.session_state.adk_user_id,
                            session_id=sid,
                            message=prompt,
                        )

                    answer = result.final_text.strip() or "(No text response produced.)"
                    st.markdown(answer)

                    st.session_state.chat.append(
                        {"role": "assistant", "content": answer, "ts": datetime.now().strftime("%H:%M:%S")}
                    )
                    st.session_state.debug["events"].append(result.events)
                    st.session_state.debug["tool_calls"].append(result.tool_calls)
                    st.session_state.debug["tool_responses"].append(result.tool_responses)

                except Exception as e:
                    st.error(str(e))
                    st.info(
                        textwrap.dedent(
                            """
                            Common fixes:
                            - Use Python 3.11 (this repo’s `pyproject.toml` requires it).
                            - Run `poetry install`.
                            - Ensure your `.env` has the required Google/Vertex credentials.
                            """
                        ).strip()
                    )

    with right:
        if show_debug:
            st.subheader("Debug")
            st.caption("Raw events + tool calls for the latest turns.")

            st.write("**Turns captured:**", len(st.session_state.debug.get("events", [])))

            if st.session_state.debug.get("events"):
                idx = st.number_input(
                    "Turn #", min_value=1, max_value=len(st.session_state.debug["events"]), value=len(st.session_state.debug["events"])
                )
                turn_i = int(idx) - 1

                st.markdown("**Tool calls**")
                st.json(st.session_state.debug["tool_calls"][turn_i] if turn_i < len(st.session_state.debug["tool_calls"]) else [])

                st.markdown("**Tool responses**")
                st.json(
                    st.session_state.debug["tool_responses"][turn_i]
                    if turn_i < len(st.session_state.debug["tool_responses"]) else []
                )

                st.markdown("**Events**")
                st.json(st.session_state.debug["events"][turn_i])


if __name__ == "__main__":
    main()
