import json
import asyncio
from google import genai
from google.genai import errors as genai_errors
from pydantic import BaseModel
from typing import Type, Dict, Any, List, Optional

# Prompts
EXTRACTION_SYSTEM_PROMPT = """You are a resume parsing engine. Extract the structured content of the resume text into JSON exactly as specified by the schema. Do not summarize, infer, embellish, or add anything not explicitly present in the text. Preserve exact wording of bullets, titles, and dates as written. If a field is not present in the source, omit it or use null — never guess a value. Preserve any existing skill category labels verbatim. If the source resume's skills aren't grouped under any label, use a single category (e.g. "Skills") — don't force fabricated categories."""

EXTRACTION_USER_PROMPT_TEMPLATE = """Resume text:

{resume_text}

Extract this into the JSON schema exactly as specified. Use only information present in the text above. Preserve any existing skill category labels verbatim. If ungrouped, use a single sensible category."""

SUGGESTIONS_SYSTEM_PROMPT = """You are an expert resume reviewer and ATS specialist. You are given a candidate's
resume as structured JSON (ground truth — the complete and only source of facts about the candidate) and a target
job description. Instead of rewriting the resume, produce concrete, individually-actionable suggestions the
candidate can review and paste in themselves.

Hard rules, no exceptions:
1. Never invent or imply any employer, title, tool, technology, certification, date, or responsibility not already
   present in the source resume JSON.
2. Every suggested_bullet or suggested summary must remain 100% factually grounded in the source — you may reword,
   reorder, consolidate, and surface relevant terminology, never add unverified claims. suggested_bullet text must
   not add adjectives, scale claims, or architecture descriptors (e.g. "multi-agent", "intelligent", "enterprise-grade")
   that aren't directly stated or clearly implied by the source resume JSON.
3. If a bullet would be stronger with a quantified metric but no number exists in the source, DO NOT invent one.
   Write the bullet with a bracketed placeholder like "[X%]" or "[add number]" and say so in the reason field.
4. For each keyword in jd_required_keywords, write a `suggestion` that is concrete and copiable — name the exact
   resume section and, where the keyword is already true of the candidate, exact phrasing to add. If the candidate
   has no real basis for a required/preferred keyword, say so plainly instead of suggesting they fabricate it.
5. Each keyword MUST be a short, atomic term or tool/skill name (1-4 words), matching how a real ATS parses resumes.
   Never use a paraphrased sentence or multi-clause phrase from the JD.
   GOOD: "Machine Learning", "Predictive Modeling", "React.js"
   BAD: "Machine learning, language modelling, data mining, and predictive modeling"
   BAD: "Ability to lead cross-functional teams"
6. structure_suggestions are for section ordering, formatting, length, or ATS-parsability advice — not content
   rewrites (those belong in summary_suggestion / bullet_suggestions). Before writing any structure_suggestion,
   check it against the actual current structure in the source resume JSON and never suggest something the candidate
   has already done.
7. Only include bullet_suggestions for bullets that meaningfully improve — do not suggest cosmetic-only changes.
8. If a suggested rewrite removes a specific, differentiating detail from the original (a named project, an unusual
   skill combination, a concrete outcome), the rationale fields (summary_suggestion.rationale, bullet_suggestion.reason)
   must say so plainly. You should generally prefer preserving distinctive details over swapping them for generic
   JD-matching phrases when both can't fit.
9. Output only the JSON specified. No commentary, no markdown formatting."""

SUGGESTIONS_USER_PROMPT_TEMPLATE = """Source resume (ground truth JSON):
{resume_json}

Target job description:
{jd_text}

Produce: a summary_suggestion (omit if the existing summary is already strong), keyword_suggestions covering every
required/preferred keyword in the job description, bullet_suggestions for the highest-impact improvable bullets
across experience and projects, and structure_suggestions for any formatting/ordering issues. Follow the rules
above exactly."""

COVER_LETTER_SYSTEM_PROMPT = """You are an expert cover letter writer. You are given a candidate's resume as
structured JSON (ground truth) and a target job description. Write two variants of a cover letter that connect the candidate's real, existing experience to the role:
1. "detailed": A substantial cover letter (3-4 short paragraphs, under ~320 words).
2. "concise": A short, punchy cover letter (2 short paragraphs, ~150-200 words).
Never invent employers, titles, tools, or achievements not present in the source JSON. Do not use generic filler
("I am writing to express my interest..."); open with something specific to the role or the candidate's most
relevant work. Output only the finished cover letter text variants in the JSON response — no subject line, no commentary, no markdown."""

COVER_LETTER_USER_PROMPT_TEMPLATE = """Candidate resume (ground truth JSON):
{resume_json}

Target job description:
{jd_text}

Write the cover letter."""

MODEL_NAME = "gemini-3.5-flash-lite"

async def call_llm(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    response_schema: Type[BaseModel],
    model: str = MODEL_NAME,
) -> Dict[str, Any]:
    """
    Adapter function to call an LLM (currently Gemini only) with retries.
    """
    client = genai.Client(api_key=api_key)

    retries = [1, 2, 4]

    for i in range(len(retries) + 1):
        try:
            response = await client.aio.models.generate_content(
                model=model,
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

GROUNDING_SYSTEM_PROMPT = """You are a strict fact-checker. You are given a source resume JSON and a list of suggested bullet/summary rewrites.
Your task is to flag any suggested text that contains a claim, tool, qualifier, or detail not directly traceable to the source resume.
Return the indices of the bullet suggestions that contain ungrounded content and a one-line reason for each. Also flag the summary if it is ungrounded."""

GROUNDING_USER_PROMPT_TEMPLATE = """Source Resume JSON:
{source_resume}

Suggested Summary:
{suggested_summary}

Suggested Bullets (with indices):
{suggested_bullets}

Check for ungrounded claims."""

class BulletFlag(BaseModel):
    index: int
    reason: str

class GroundingValidationResponse(BaseModel):
    summary_flag_reason: Optional[str] = None
    bullet_flags: List[BulletFlag]

async def validate_grounding(
    suggestions: Dict[str, Any],
    source_resume: Dict[str, Any],
    api_key: str
) -> Dict[str, Any]:
    summary_sugg = suggestions.get("summary_suggestion")
    bullet_suggs = suggestions.get("bullet_suggestions", [])
    
    if not summary_sugg and not bullet_suggs:
        return suggestions
        
    suggested_summary_text = summary_sugg.get("suggested", "None") if summary_sugg else "None"
    
    bullets_text = ""
    for idx, b in enumerate(bullet_suggs):
        bullets_text += f"Index {idx}:\nOriginal: {b.get('original_bullet', '')}\nSuggested: {b.get('suggested_bullet', '')}\n\n"

    user_prompt = GROUNDING_USER_PROMPT_TEMPLATE.format(
        source_resume=json.dumps(source_resume, indent=2),
        suggested_summary=suggested_summary_text,
        suggested_bullets=bullets_text
    )

    try:
        validation_result_dict = await call_llm(
            api_key=api_key,
            system_prompt=GROUNDING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=GroundingValidationResponse,
            model="gemini-3.5-flash-lite"
        )
    except Exception as e:
        print(f"Grounding validation failed: {e}")
        return suggestions

    if validation_result_dict.get("summary_flag_reason") and summary_sugg:
        summary_sugg["needs_review"] = True
        
    flags = validation_result_dict.get("bullet_flags", [])
    for flag in flags:
        idx = flag.get("index")
        if idx is not None and 0 <= idx < len(bullet_suggs):
            bullet_suggs[idx]["needs_review"] = True

    return suggestions
