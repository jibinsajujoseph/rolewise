import json
import asyncio
from google import genai
from google.genai import errors as genai_errors
from pydantic import BaseModel
from typing import Type, Dict, Any

# Prompts
EXTRACTION_SYSTEM_PROMPT = """You are a resume parsing engine. Extract the structured content of the resume text into JSON exactly as specified by the schema. Do not summarize, infer, embellish, or add anything not explicitly present in the text. Preserve exact wording of bullets, titles, and dates as written. If a field is not present in the source, omit it or use null — never guess a value."""

EXTRACTION_USER_PROMPT_TEMPLATE = """Resume text:

{resume_text}

Extract this into the JSON schema exactly as specified. Use only information present in the text above."""

TAILORING_SYSTEM_PROMPT = """You are an expert resume editor. You will be given a candidate's resume as structured JSON (this is ground truth — the complete and only source of facts about the candidate) and a target job description. Produce a tailored version of the resume that improves its match to the job description and its readability by an Applicant Tracking System, while making zero factual changes to the candidate's history.

Hard rules, no exceptions:
1. Do not invent, add, or imply any employer, job title, tool, technology, certification, metric, date, or responsibility that is not already present in the source resume JSON.
2. You may reword, reorder, reprioritize, and consolidate existing bullets and the summary to surface skills and terminology that are already true of the candidate and relevant to the job description.
3. You may adopt the job description's terminology only when it is an accurate description of something the candidate already did — never to describe something absent from the source. For example, rewording a bullet to say "continuous integration and deployment pipelines" is fine if the source already mentions Jenkins or GitHub Actions; it is not fine if the source has no CI/CD tooling at all.
4. If a skill or requirement in the job description has no basis anywhere in the source resume, do not add it to the resume in any form. It should only appear in jd_required_keywords.
5. For jd_required_keywords, classify each keyword's importance: "required" for anything phrased as a hard requirement (e.g., "must have," "required," "X+ years of experience"), and "preferred" for anything phrased as a bonus (e.g., "nice to have," "preferred," "familiarity with").
6. Preserve all dates, employer names, and job titles exactly as given in the source — these are never rewritten.
7. Output only the JSON specified. No commentary, no markdown formatting, no explanation."""

TAILORING_USER_PROMPT_TEMPLATE = """Source resume (ground truth JSON):
{resume_json}

Target job description:
{jd_text}

Produce the tailored resume and the job description's required keyword list (with importance classification), following the rules above exactly."""

MODEL_NAME = "gemini-3.5-flash"

async def call_llm(
    provider: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    response_schema: Type[BaseModel],
) -> Dict[str, Any]:
    """
    Adapter function to call an LLM (currently Gemini only) with retries.
    """
    if provider != "gemini":
        raise ValueError(f"Unsupported provider: {provider}")

    client = genai.Client(api_key=api_key)

    retries = [1, 2, 4]

    for i in range(len(retries) + 1):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "response_schema": response_schema,
                    "temperature": 0.1,
                },
            )
            # The response text should be valid JSON as requested by response_schema
            return json.loads(response.text)
        except genai_errors.ClientError as e:
            if e.code == 429 and i < len(retries):
                await asyncio.sleep(retries[i])
            elif e.code == 429:
                raise Exception("Gemini rate limit hit — wait a moment and try again.")
            else:
                raise Exception(f"Failed to call LLM: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to call LLM: {str(e)}")
