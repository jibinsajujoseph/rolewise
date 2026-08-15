from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import os
from dotenv import load_dotenv

from models import (
    ResumeContent, SuggestionsResponse, OptimizeResponse, ErrorResponse,
    CoverLetterRequest, CoverLetterResponse
)

load_dotenv(override=True)
from parsing import parse_resume_file
from llm import (
    call_llm, 
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
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: If deployed behind a reverse proxy (e.g. nginx), get_remote_address 
# might return the proxy's IP. The limiter needs the real client IP from 
# X-Forwarded-For instead of the proxy's IP.
def get_client_ip(request: Request) -> str:
    if os.getenv("TRUST_PROXY", "false").lower() == "true":
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_ip)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "You've hit the demo's request limit — try again later."}
    )

@app.get("/api/config")
async def get_config():
    # If KEY_SOURCE is 'server', the frontend will NOT prompt for an API key.
    # If it's 'byok' (or anything else), the frontend will require it.
    key_source = os.getenv("KEY_SOURCE", "byok").lower()
    return {
        "requires_api_key": key_source != "server",
        "requires_access_code": bool(os.getenv("ACCESS_CODE"))
    }


@app.post("/api/optimize", response_model=OptimizeResponse, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
@limiter.limit(os.getenv("RATE_LIMIT", "10/hour"))
async def optimize_resume(
    request: Request,
    x_gemini_api_key: str = Header(None, description="User's Gemini API key (optional if set on server)"),
    x_access_code: str = Header(None, description="Demo access code (optional)"),
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...)
):
    access_code = os.getenv("ACCESS_CODE")
    if access_code and x_access_code != access_code:
        return JSONResponse(status_code=401, content={"error": "Invalid or missing access code."})

    # Resolve API key: prefer server env var, then fallback to header
    api_key = os.getenv("GEMINI_API_KEY") or x_gemini_api_key
    
    # Validate API key
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing Gemini API key. Please provide it in the UI or configure the server."})
    
    # 1. Read and parse file
    try:
        content = await resume_file.read()
        
        max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", 5))
        if len(content) > max_upload_mb * 1024 * 1024:
            return JSONResponse(
                status_code=413, 
                content={"error": f"File exceeds maximum upload size of {max_upload_mb}MB."}
            )

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
        
    # 3. Call 2 - Generate Suggestions
    try:
        extracted_json_str = json.dumps(extracted_resume_dict, indent=2)
        suggestions_user_prompt = SUGGESTIONS_USER_PROMPT_TEMPLATE.format(
            resume_json=extracted_json_str,
            jd_text=jd_text
        )
        
        suggestions_result_dict = await call_llm(
            provider="gemini",
            api_key=api_key,
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
@limiter.limit(os.getenv("RATE_LIMIT", "10/hour"))
async def generate_cover_letter(
    request: Request,
    req: CoverLetterRequest,
    x_gemini_api_key: str = Header(None),
    x_access_code: str = Header(None),
):
    access_code = os.getenv("ACCESS_CODE")
    if access_code and x_access_code != access_code:
        return JSONResponse(status_code=401, content={"error": "Invalid or missing access code."})

    api_key = os.getenv("GEMINI_API_KEY") or x_gemini_api_key
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "Missing Gemini API key."})
    try:
        prompt = COVER_LETTER_USER_PROMPT_TEMPLATE.format(
            resume_json=json.dumps(req.resume.model_dump(), indent=2),
            jd_text=req.jd_text,
        )
        result = await call_llm(
            provider="gemini",
            api_key=api_key,
            system_prompt=COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=CoverLetterResponse,
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
    return CoverLetterResponse(**result)
