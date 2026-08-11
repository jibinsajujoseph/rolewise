def compute_missing_keywords(jd_required_keywords: list[str], original_resume_text: str) -> list[str]:
    """
    Deterministically computes missing keywords by checking if they appear
    in the original resume text (case-insensitive substring match).
    """
    resume_lower = original_resume_text.lower()
    missing = []
    for kw in jd_required_keywords:
        if kw.lower() not in resume_lower:
            missing.append(kw)
    return missing
