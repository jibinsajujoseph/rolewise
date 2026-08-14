from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from dotenv import load_dotenv

from models import (
    ResumeContent, SuggestionsResponse, OptimizeResponse, ErrorResponse,
    CoverLetterRequest, CoverLetterResponse
)

load_dotenv(override=True)
from parsing import parse_resume_file
from providers import PROVIDERS
from llm import (
    EXTRACTION_SYSTEM_PROMPT, 
    EXTRACTION_USER_PROMPT_TEMPLATE, 
    SUGGESTIONS_SYSTEM_PROMPT, 
    SUGGESTIONS_USER_PROMPT_TEMPLATE,
    COVER_LETTER_SYSTEM_PROMPT,
    COVER_LETTER_USER_PROMPT_TEMPLATE
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



@app.get("/api/config")
async def get_config():
    key_source = os.getenv("KEY_SOURCE", "byok").lower()
    providers = []
    for pid, provider in PROVIDERS.items():
        server_key = os.getenv(f"{pid.upper()}_API_KEY")
        if key_source == "server":
            requires_api_key = False
        else:
            requires_api_key = not bool(server_key)
            
        providers.append({
            "id": pid,
            "name": provider.name,
            "requires_api_key": requires_api_key,
        })
    return {"providers": providers}

@app.get("/api/models")
async def get_models(provider: str, x_api_key: str = Header(None)):
    if provider not in PROVIDERS:
        return JSONResponse(status_code=400, content={"error": f"Unknown provider: {provider}"})
    api_key = os.getenv(f"{provider.upper()}_API_KEY") or x_api_key
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing API key for this provider."})
    try:
        models = await PROVIDERS[provider].list_models(api_key)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    return {"models": [m.model_dump() for m in models]}


@app.post("/api/optimize", response_model=OptimizeResponse, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def optimize_resume(
    provider: str = Form(...),
    model: str = Form(...),
    x_api_key: str = Header(None, description="User's API key (optional if set on server)"),
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...)
):
    if provider not in PROVIDERS:
        return JSONResponse(status_code=400, content={"error": f"Unknown provider: {provider}"})

    # Resolve API key: prefer server env var, then fallback to header
    api_key = os.getenv(f"{provider.upper()}_API_KEY") or x_api_key
    
    # Validate API key
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing API key. Please provide it in the UI or configure the server."})
    
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
        
        extracted_resume_dict = await PROVIDERS[provider].generate(
            api_key=api_key,
            model=model,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=extraction_user_prompt,
            response_schema=ResumeContent
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
        
    # 3. Call 2 - Generate Suggestions
    try:
        extracted_json_str = json.dumps(extracted_resume_dict, indent=2)
        suggestions_user_prompt = SUGGESTIONS_USER_PROMPT_TEMPLATE.format(
            resume_json=extracted_json_str,
            jd_text=jd_text
        )
        
        suggestions_result_dict = await PROVIDERS[provider].generate(
            api_key=api_key,
            model=model,
            system_prompt=SUGGESTIONS_SYSTEM_PROMPT,
            user_prompt=suggestions_user_prompt,
            response_schema=SuggestionsResponse
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
        
    # 4. Compute 'present' flag for keyword suggestions
    keyword_suggestions = suggestions_result_dict.get("keyword_suggestions", [])
    # We create a pseudo jd_required_keywords list to reuse compute_missing_keywords
    pseudo_jd_keywords = [{"keyword": kw["keyword"]} for kw in keyword_suggestions]
    missing_keywords = compute_missing_keywords(pseudo_jd_keywords, original_resume_text)
    
    for kw in keyword_suggestions:
        kw["present"] = kw["keyword"] not in missing_keywords

    return OptimizeResponse(
        extracted_resume=extracted_resume_dict,
        summary_suggestion=suggestions_result_dict.get("summary_suggestion"),
        keyword_suggestions=keyword_suggestions,
        bullet_suggestions=suggestions_result_dict.get("bullet_suggestions", []),
        structure_suggestions=suggestions_result_dict.get("structure_suggestions", [])
    )

@app.post("/api/cover-letter", response_model=CoverLetterResponse, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def generate_cover_letter(
    req: CoverLetterRequest,
    x_api_key: str = Header(None),
):
    if req.provider not in PROVIDERS:
        return JSONResponse(status_code=400, content={"error": f"Unknown provider: {req.provider}"})
    api_key = os.getenv(f"{req.provider.upper()}_API_KEY") or x_api_key
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing API key."})
    try:
        prompt = COVER_LETTER_USER_PROMPT_TEMPLATE.format(
            resume_json=json.dumps(req.resume.model_dump(), indent=2),
            jd_text=req.jd_text,
        )
        result = await PROVIDERS[req.provider].generate(
            api_key=api_key,
            model=req.model,
            system_prompt=COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=CoverLetterResponse,
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
    return CoverLetterResponse(**result)
