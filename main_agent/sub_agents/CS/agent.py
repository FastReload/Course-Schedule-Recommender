# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CS scheduling agent using RAG for course information."""

import os

from google.adk.agents import Agent
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag
from dotenv import load_dotenv

from . import prompt

load_dotenv()

cs_course_retrieval = VertexAiRagRetrieval(
    name='retrieve_cs_course_info',
    description=(
        'Use this tool to retrieve course information, prerequisites, and degree requirements for CS courses from the RAG corpus.'
    ),
    rag_resources=[
        rag.RagResource(
            # please fill in your own rag corpus
            # here is a sample rag corpus for testing purpose
            # e.g. projects/123/locations/us-central1/ragCorpora/456
            rag_corpus=os.environ.get("CS_CORPUS")
        )
    ],
    similarity_top_k=20,
    vector_distance_threshold=0.6,
)

cs_agent = Agent(
    model='gemini-2.5-pro',
    name='CS_agent',
    instruction=prompt.CS_PROMPT,
    tools=[
        cs_course_retrieval,
    ]
)
