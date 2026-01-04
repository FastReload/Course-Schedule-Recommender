

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-pro"

online_agent = Agent(
    model=MODEL,
    name="online_agent",
    instruction=prompt.ONLINE_PROMPT,
    output_key="online question_output",
    tools=[google_search],
)
