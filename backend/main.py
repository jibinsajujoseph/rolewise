from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from dotenv import load_dotenv

from models import ResumeContent, TailoredResumeResponse, OptimizeResponse, ErrorResponse

load_dotenv(override=True)
from parsing import parse_resume_file
from llm import (
    call_llm, 
    EXTRACTION_SYSTEM_PROMPT, 
    EXTRACTION_USER_PROMPT_TEMPLATE, 
    TAILORING_SYSTEM_PROMPT, 
    TAILORING_USER_PROMPT_TEMPLATE
)
from keywords import compute_missing_keywords

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For MVP, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def render_resume_to_text(resume: dict) -> str:
    """
    Renders the tailored resume JSON into a clean plain text format.
    """
    lines = []
    
    # Contact
    contact = resume.get("contact", {})
    name = contact.get("name", "")
    if name:
        lines.append(name.upper())
    
    contact_info = []
    if contact.get("email"): contact_info.append(contact["email"])
    if contact.get("phone"): contact_info.append(contact["phone"])
    if contact.get("location"): contact_info.append(contact["location"])
    if contact.get("links"):
        contact_info.extend(contact["links"])
    
    if contact_info:
        lines.append(" | ".join(contact_info))
    
    lines.append("")
    
    # Summary
    if resume.get("summary"):
        lines.append("SUMMARY")
        lines.append("-" * 10)
        lines.append(resume["summary"])
        lines.append("")
        
    # Skills
    if resume.get("skills"):
        lines.append("SKILLS")
        lines.append("-" * 10)
        lines.append(", ".join(resume["skills"]))
        lines.append("")
        
    # Experience
    if resume.get("experience"):
        lines.append("EXPERIENCE")
        lines.append("-" * 10)
        for exp in resume["experience"]:
            header = f"{exp.get('title', '')} at {exp.get('company', '')}"
            
            dates_loc = []
            if exp.get("start_date") or exp.get("end_date"):
                dates = f"{exp.get('start_date', '')} - {exp.get('end_date', 'Present')}"
                dates_loc.append(dates)
            if exp.get("location"):
                dates_loc.append(exp["location"])
                
            if dates_loc:
                header += f" ({', '.join(dates_loc)})"
                
            lines.append(header)
            
            for bullet in exp.get("bullets", []):
                lines.append(f"• {bullet}")
            lines.append("")
            
    # Projects
    if resume.get("projects"):
        lines.append("PROJECTS")
        lines.append("-" * 10)
        for proj in resume["projects"]:
            header = proj.get("name", "")
            if proj.get("date"):
                header += f" ({proj['date']})"
            if proj.get("link"):
                header += f" - {proj['link']}"
            lines.append(header)
            
            for bullet in proj.get("bullets", []):
                lines.append(f"• {bullet}")
            lines.append("")

    # Education
    if resume.get("education"):
        lines.append("EDUCATION")
        lines.append("-" * 10)
        for edu in resume["education"]:
            edu_line = f"{edu.get('degree', '')}, {edu.get('institution', '')}"
            if edu.get("date"):
                edu_line += f" ({edu['date']})"
            lines.append(edu_line)
        lines.append("")
            
    # Certifications
    if resume.get("certifications"):
        lines.append("CERTIFICATIONS")
        lines.append("-" * 10)
        for cert in resume["certifications"]:
            lines.append(cert)
        lines.append("")

    return "\n".join(lines).strip()

@app.get("/api/config")
async def get_config():
    # If KEY_SOURCE is 'server', the frontend will NOT prompt for an API key.
    # If it's 'byok' (or anything else), the frontend will require it.
    key_source = os.getenv("KEY_SOURCE", "byok").lower()
    return {"requires_api_key": key_source != "server"}


@app.post("/api/optimize", response_model=OptimizeResponse, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def optimize_resume(
    x_gemini_api_key: str = Header(None, description="User's Gemini API key (optional if set on server)"),
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...)
):
    # Resolve API key: prefer server env var, then fallback to header
    api_key = os.getenv("GEMINI_API_KEY") or x_gemini_api_key
    
    # Validate API key
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing Gemini API key. Please provide it in the UI or configure the server."})
    
    # 1. Read and parse file
    try:
        content = await resume_file.read()
        filename = resume_file.filename or ""
        original_resume_text = parse_resume_file(filename, content)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Failed to read file: {str(e)}"})
        
    # 2. Call 1 - Extract structured JSON
    try:
        extraction_user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(resume_text=original_resume_text)
        
        extracted_resume_dict = await call_llm(
            provider="gemini",
            api_key=api_key,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=extraction_user_prompt,
            response_schema=ResumeContent
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
        
    # 3. Call 2 - Tailor resume against JD
    try:
        extracted_json_str = json.dumps(extracted_resume_dict, indent=2)
        tailoring_user_prompt = TAILORING_USER_PROMPT_TEMPLATE.format(
            resume_json=extracted_json_str,
            jd_text=jd_text
        )
        
        tailored_result_dict = await call_llm(
            provider="gemini",
            api_key=api_key,
            system_prompt=TAILORING_SYSTEM_PROMPT,
            user_prompt=tailoring_user_prompt,
            response_schema=TailoredResumeResponse
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
        
    # 4. Compute missing keywords
    jd_required_keywords = tailored_result_dict.get("jd_required_keywords", [])
    missing_keywords = compute_missing_keywords(jd_required_keywords, original_resume_text)
    
    # 5. Render tailored resume to text
    tailored_resume_text = render_resume_to_text(tailored_result_dict.get("tailored_resume", {}))
    
    return OptimizeResponse(
        tailored_resume_text=tailored_resume_text,
        missing_keywords=missing_keywords
    )
