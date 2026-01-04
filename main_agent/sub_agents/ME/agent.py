

import os

from google.adk.agents import Agent
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag
from dotenv import load_dotenv

from . import prompt

load_dotenv()

me_course_retrieval = VertexAiRagRetrieval(
    name='retrieve_me_course_info',
    description=(
        'Use this tool to retrieve course information, prerequisites, and degree requirements for ME courses from the RAG corpus.'
    ),
    rag_resources=[
        rag.RagResource(

            rag_corpus=os.environ.get("ME_CORPUS")
        )
    ],
    similarity_top_k=20,
    vector_distance_threshold=0.6,
)

me_agent = Agent(
    model='gemini-2.5-pro',
    name='ME_agent',
    instruction=prompt.ME_PROMPT,
    tools=[
        me_course_retrieval,
    ]
)
