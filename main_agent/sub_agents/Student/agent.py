"""Student data collecting agent using BigQuery for course information."""

import os

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.cloud import bigquery
from dotenv import load_dotenv
from . import prompt

load_dotenv()

client = bigquery.Client()

def student_data_retrieval(student_id: str) -> str:
    """
    Retrieves student information from BigQuery based on student ID.

    Args:
        student_id: The ID of the student to search for.

    Returns:
        A formatted string containing the student information, or a message if not found.
    """
    
    table_id = os.environ.get("BIGQUERY_STUDENT_INFO_TABLE", "")
    if not table_id:
        return "Error: BigQuery table ID for student data not configured. Please set BIGQUERY_STUDENT_INFO_TABLE in your .env file."

    student_info_query = f"""
        SELECT Student_UID, PROGRAM_LEVEL_DESC, FIRST_MAJOR_CODE, SECOND_MAJOR_CODE
        FROM `{table_id}`
        WHERE Student_UID = FROM_BASE64('{student_id}')
        LIMIT 1
    """
    
    student_class_query = f"""
        SELECT Student_UID, CATALOG_TERM_CODE, COURSE_ID, COURSE_CREDITS, FINAL_GRADE
        FROM `{table_id}`
        WHERE Student_UID = FROM_BASE64('{student_id}')
        LIMIT 200
    """
    
    try:
        query_job = client.query(student_info_query)
        results = query_job.result()
        
        if results.total_rows == 0:
            return f"No student information found for student ID: {student_id}."
        
        output = []
        for row in results:
            output.append(f"Student ID: {row.Student_UID}\n"
                          f"Program Level: {row.PROGRAM_LEVEL_DESC}\n"
                          f"First Major: {row.FIRST_MAJOR_CODE}\n"
                          f"Second Major: {row.SECOND_MAJOR_CODE}\n")
            
        class_query_job = client.query(student_class_query)
        class_results = class_query_job.result()

        if class_results.total_rows == 0:
            output.append("No class information found for the specified student ID.")
        else:
            for row in class_results:
                output.append(f"Class ID: {row.COURSE_ID}\n"
                              f"Credits: {row.COURSE_CREDITS}\n"
                              f"Final Grade: {row.FINAL_GRADE}\n"
                              f"Catalog Term Code: {row.CATALOG_TERM_CODE}\n")

    except Exception as e:
        return f"Error retrieving student information: {e}"
    
    return "Found the following student information:\n" + "\n".join(output)


student_data_tool = FunctionTool(func=student_data_retrieval)

student_agent = Agent(
    model='gemini-2.5-pro',
    name='student_agent',
    instruction=prompt.STUDENT_PROMPT,
    tools=[
        student_data_tool,
    ]
)
    