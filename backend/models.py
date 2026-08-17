from pydantic import BaseModel
from typing import List, Optional, Literal

class Contact(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str]

class Experience(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str
    location: Optional[str] = None
    bullets: List[str]

class Education(BaseModel):
    institution: str
    degree: str
    date: Optional[str] = None

class Project(BaseModel):
    name: str
    date: Optional[str] = None
    link: Optional[str] = None
    bullets: List[str]

class SkillCategory(BaseModel):
    category: str
    items: List[str]

class ResumeContent(BaseModel):
    contact: Contact
    summary: Optional[str] = None
    skills: List[SkillCategory]
    experience: List[Experience]
    education: List[Education]
    projects: List[Project]
    certifications: List[str]
    remaining_calls: Optional[int] = None
    limit: Optional[int] = None

class KeywordSuggestion(BaseModel):
    keyword: str
    importance: Literal["required", "preferred"]
    present: bool  # already in original resume (deterministic check)
    suggestion: str  # concrete, copiable guidance on where/how to add it

class SummarySuggestion(BaseModel):
    original: Optional[str] = None
    suggested: str
    rationale: str
    needs_review: Optional[bool] = False

class BulletSuggestion(BaseModel):
    section: str          # e.g. "Experience: AI Engineer at Akumen" or "Project: InboxIQ"
    original_bullet: str
    suggested_bullet: str
    reason: str           # e.g. "Adds quantifiable metric", "Surfaces required keyword 'RAG'"
    needs_review: Optional[bool] = False

class StructureSuggestion(BaseModel):
    title: str
    detail: str

class SuggestionsResponse(BaseModel):
    summary_suggestion: Optional[SummarySuggestion] = None
    keyword_suggestions: List[KeywordSuggestion]
    bullet_suggestions: List[BulletSuggestion]
    structure_suggestions: List[StructureSuggestion]

class SuggestResponse(BaseModel):
    match_score: int
    summary_suggestion: Optional[SummarySuggestion] = None
    keyword_suggestions: List[KeywordSuggestion]
    bullet_suggestions: List[BulletSuggestion]
    structure_suggestions: List[StructureSuggestion]
    remaining_calls: Optional[int] = None
    limit: Optional[int] = None

class OptimizeResponse(BaseModel):
    extracted_resume: ResumeContent
    match_score: int
    summary_suggestion: Optional[SummarySuggestion] = None
    keyword_suggestions: List[KeywordSuggestion]
    bullet_suggestions: List[BulletSuggestion]
    structure_suggestions: List[StructureSuggestion]
    remaining_calls: Optional[int] = None
    limit: Optional[int] = None

class SuggestRequest(BaseModel):
    resume: ResumeContent
    jd_text: str

class CoverLetterRequest(BaseModel):
    resume: ResumeContent
    jd_text: str

class CoverLetterResponse(BaseModel):
    cover_letter_concise: str
    cover_letter_detailed: str

class ErrorResponse(BaseModel):
    error: str
    remaining_calls: Optional[int] = None
    limit: Optional[int] = None

class BuildResumeRequest(BaseModel):
    resume: ResumeContent
    accepted_summary: Optional[str] = None
    accepted_bullets: dict[str, str] = {}
