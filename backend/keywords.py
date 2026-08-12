def compute_missing_keywords(jd_required_keywords: list[dict], original_resume_text: str) -> list[str]:
    """
    Deterministically computes missing keywords by checking if they appear
    in the original resume text (case-insensitive substring match).
    """
    resume_lower = original_resume_text.lower()
    missing = []
    for kw_dict in jd_required_keywords:
        kw = kw_dict["keyword"]
        if kw.lower() not in resume_lower:
            missing.append(kw)
    return missing

def compute_match_score(keywords: list[dict], resume_text: str) -> int:
    if not keywords:
        return 100
    resume_lower = resume_text.lower()
    weight = {"required": 2, "preferred": 1}
    earned = sum(weight[kw["importance"]] for kw in keywords if kw["keyword"].lower() in resume_lower)
    total = sum(weight[kw["importance"]] for kw in keywords)
    return round(100 * earned / total)
