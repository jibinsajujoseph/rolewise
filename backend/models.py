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

class ResumeContent(BaseModel):
    contact: Contact
    summary: Optional[str] = None
    skills: List[str]
    experience: List[Experience]
    education: List[Education]
    projects: List[Project]
    certifications: List[str]

class Keyword(BaseModel):
    keyword: str
    importance: Literal["required", "preferred"]

class TailoredResumeResponse(BaseModel):
    tailored_resume: ResumeContent
    jd_required_keywords: List[Keyword]

class OptimizeResponse(BaseModel):
    tailored_resume_text: str
    original_match_score: int
    new_match_score: int
    missing_keywords: List[str]
    added_keywords: List[str]

class ErrorResponse(BaseModel):
    error: str
