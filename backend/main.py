from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import os
import time
from collections import defaultdict
from dotenv import load_dotenv

from models import (
    ResumeContent, SuggestionsResponse, OptimizeResponse, ErrorResponse,
    CoverLetterRequest, CoverLetterResponse, SuggestRequest, SuggestResponse,
    BuildResumeRequest
)

load_dotenv(override=True)
from parsing import parse_resume_file
from docx_generator import generate_resume_docx
from llm import (
    call_llm, 
    validate_grounding,
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

# Rate limit tracking
analysis_calls = defaultdict(list)
def parse_rate_limit(limit_str):
    if not limit_str: return 10
    return int(limit_str.split('/')[0])

MAX_ANALYSES_PER_HOUR = parse_rate_limit(os.getenv("EXTRACT_RATE_LIMIT", "10/hour"))

def get_remaining_analyses(client_ip: str) -> int:
    current_time = time.time()
    one_hour_ago = current_time - 3600
    analysis_calls[client_ip] = [ts for ts in analysis_calls[client_ip] if ts > one_hour_ago]
    return max(0, MAX_ANALYSES_PER_HOUR - len(analysis_calls[client_ip]))

def record_analysis(client_ip: str):
    analysis_calls[client_ip].append(time.time())

limiter = Limiter(key_func=get_client_ip)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "You've hit the demo's request limit — try again later.", "remaining_calls": 0}
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


async def _extract_internal(resume_file: UploadFile, api_key: str):
    content = await resume_file.read()
    
    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", 5))
    if len(content) > max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds maximum upload size of {max_upload_mb}MB.")

    filename = resume_file.filename or ""
    original_resume_text = parse_resume_file(filename, content)
        
    extraction_user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(resume_text=original_resume_text)
    
    extracted_resume_dict = await call_llm(
        api_key=api_key,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=extraction_user_prompt,
        response_schema=ResumeContent
    )
    return extracted_resume_dict, original_resume_text

async def _suggest_internal(extracted_resume_dict: dict, jd_text: str, api_key: str, original_resume_text: str = None):
    extracted_json_str = json.dumps(extracted_resume_dict, indent=2)
    suggestions_user_prompt = SUGGESTIONS_USER_PROMPT_TEMPLATE.format(
        resume_json=extracted_json_str,
        jd_text=jd_text
    )
    
    suggestions_result_dict = await call_llm(
        api_key=api_key,
        system_prompt=SUGGESTIONS_SYSTEM_PROMPT,
        user_prompt=suggestions_user_prompt,
        response_schema=SuggestionsResponse,
        model="gemini-3.5-flash"
    )
    
    if os.getenv("ENABLE_GROUNDING_CHECK", "true").lower() == "true":
        suggestions_result_dict = await validate_grounding(
            suggestions=suggestions_result_dict,
            source_resume=extracted_resume_dict,
            api_key=api_key
        )
            
    keyword_suggestions = suggestions_result_dict.get("keyword_suggestions", [])
    pseudo_jd_keywords = [{"keyword": kw["keyword"]} for kw in keyword_suggestions]
    
    text_for_keywords = original_resume_text if original_resume_text else extracted_json_str
    missing_keywords = compute_missing_keywords(pseudo_jd_keywords, text_for_keywords)
    
    for kw in keyword_suggestions:
        kw["present"] = kw["keyword"] not in missing_keywords

    total_keywords = len(keyword_suggestions)
    present_keywords = sum(1 for kw in keyword_suggestions if kw["present"])
    match_score = int((present_keywords / total_keywords) * 100) if total_keywords > 0 else 0

    return {
        "match_score": match_score,
        "summary_suggestion": suggestions_result_dict.get("summary_suggestion"),
        "keyword_suggestions": keyword_suggestions,
        "bullet_suggestions": suggestions_result_dict.get("bullet_suggestions", []),
        "structure_suggestions": suggestions_result_dict.get("structure_suggestions", [])
    }

def check_auth(x_access_code: str, x_gemini_api_key: str):
    access_code = os.getenv("ACCESS_CODE")
    if access_code and x_access_code != access_code:
        raise HTTPException(status_code=401, detail="Invalid or missing access code.")

    api_key = os.getenv("GEMINI_API_KEY") or x_gemini_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API key. Please provide it in the UI or configure the server.")
    return api_key

@app.post("/api/extract", response_model=ResumeContent, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
@limiter.limit(os.getenv("EXTRACT_RATE_LIMIT", "10/hour"))
async def extract_resume(
    request: Request,
    x_gemini_api_key: str = Header(None, description="User's Gemini API key (optional if set on server)"),
    x_access_code: str = Header(None, description="Demo access code (optional)"),
    resume_file: UploadFile = File(...)
):
    try:
        api_key = check_auth(x_access_code, x_gemini_api_key)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

    try:
        extracted_resume_dict, _ = await _extract_internal(resume_file, api_key)
        extracted_data = extracted_resume_dict
        extracted_data["remaining_calls"] = get_remaining_analyses(get_client_ip(request))
        return ResumeContent(**extracted_data)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})

@app.post("/api/suggest", response_model=SuggestResponse, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
@limiter.limit(os.getenv("SUGGEST_RATE_LIMIT", "20/hour"))
async def suggest_resume(
    request: Request,
    req: SuggestRequest,
    x_gemini_api_key: str = Header(None, description="User's Gemini API key (optional if set on server)"),
    x_access_code: str = Header(None, description="Demo access code (optional)"),
):
    try:
        api_key = check_auth(x_access_code, x_gemini_api_key)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

    client_ip = get_client_ip(request)
    record_analysis(client_ip)
    
    try:
        result = await _suggest_internal(req.resume.model_dump(), req.jd_text, api_key)
        return SuggestResponse(
            match_score=result.get("match_score", 0),
            summary_suggestion=result.get("summary_suggestion"),
            keyword_suggestions=result.get("keyword_suggestions", []),
            bullet_suggestions=result.get("bullet_suggestions", []),
            structure_suggestions=result.get("structure_suggestions", []),
            remaining_calls=get_remaining_analyses(client_ip)
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})

@app.post("/api/optimize", response_model=OptimizeResponse, responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
@limiter.limit(os.getenv("RATE_LIMIT", "10/hour"))
async def optimize_resume(
    request: Request,
    x_gemini_api_key: str = Header(None, description="User's Gemini API key (optional if set on server)"),
    x_access_code: str = Header(None, description="Demo access code (optional)"),
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...)
):
    try:
        api_key = check_auth(x_access_code, x_gemini_api_key)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

    try:
        extracted_resume_dict, original_resume_text = await _extract_internal(resume_file, api_key)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
        
    try:
        suggest_result = await _suggest_internal(extracted_resume_dict, jd_text, api_key, original_resume_text)
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
        
    return OptimizeResponse(
        extracted_resume=extracted_resume_dict,
        **suggest_result
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
        # Upgrading from lite to flash for better prose and strict adherence to no-fabrication rules,
        # accepting a cost/latency tradeoff compared to the extraction step.
        result = await call_llm(
            api_key=api_key,
            system_prompt=COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=CoverLetterResponse,
            model="gemini-3.5-flash"
        )
    except Exception as e:
        error_msg = str(e)
        status_code = 429 if "rate limit hit" in error_msg.lower() else 400
        return JSONResponse(status_code=status_code, content={"error": error_msg})
    return CoverLetterResponse(**result)

@app.post("/api/build-resume", responses={400: {"model": ErrorResponse}})
async def build_resume(
    request: Request,
    req: BuildResumeRequest,
    x_access_code: str = Header(None)
):
    try:
        check_auth(x_access_code, None)
    except HTTPException as e:
        if e.status_code != 400:
            return JSONResponse(status_code=e.status_code, content={"error": e.detail})

    try:
        docx_buffer = generate_resume_docx(
            resume=req.resume,
            accepted_summary=req.accepted_summary,
            accepted_bullets=req.accepted_bullets
        )
        return Response(
            content=docx_buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=Optimized_Resume.docx"}
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
