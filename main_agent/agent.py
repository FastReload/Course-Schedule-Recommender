from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from . import prompt
from .sub_agents.CS import cs_agent
from .sub_agents.ME import me_agent
from .sub_agents.ONLINE import online_agent
from .sub_agents.Student import student_agent


MODEL = "gemini-2.5-pro"


schedule_recommender = LlmAgent(
    name="Schedule_Recommender",
    model=MODEL,
    description=(
        "Guide students to the appropriate scheduler agent once they "
        "confirm their major or student ID. This main recommender agent helps students "
        "navigate the scheduling process by directing them to a specialized "
        "agent tailored to their academic field."
    ),
    instruction=prompt.MAIN_PROMPT,
    output_key="schedule_recommender_output",
    tools=[
        AgentTool(agent=cs_agent),
        AgentTool(agent=me_agent),
        AgentTool(agent=online_agent),
        AgentTool(agent=student_agent)
    ]
)

root_agent = schedule_recommender