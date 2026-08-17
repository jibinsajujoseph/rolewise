import string
import re

def _get_variants(text: str) -> set[str]:
    text = text.lower().strip()
    if not text:
        return set()
        
    variants = {text}
    
    # De-punctuated
    no_punct = text.translate(str.maketrans('', '', string.punctuation))
    if no_punct:
        variants.add(no_punct)
        
    # De-hyphenated (replace punctuation with spaces)
    spaced = text
    for p in string.punctuation:
        spaced = spaced.replace(p, ' ')
    spaced = ' '.join(spaced.split())
    if spaced:
        variants.add(spaced)
        
    # Simple singular/plural
    if text.endswith('s') and len(text) > 3:
        variants.add(text[:-1])
    else:
        variants.add(text + 's')
        
    # Acronym for multi-word phrases (e.g., "machine learning" -> "ml")
    words = spaced.split()
    if 1 < len(words) <= 4:
        acronym = "".join(w[0] for w in words if w)
        if len(acronym) >= 4:
            variants.add(acronym)
            variants.add(acronym + 's')
            
    return variants

def compute_missing_keywords(jd_required_keywords: list[dict], original_resume_text: str) -> list[str]:
    """
    Deterministically computes missing keywords by checking if they appear
    in the original resume text (case-insensitive substring match).
    Uses simple normalization to handle trivial variants.
    """
    resume_lower = original_resume_text.lower()
    resume_no_punct = resume_lower.translate(str.maketrans('', '', string.punctuation))
    
    resume_spaced = resume_lower
    for p in string.punctuation:
        resume_spaced = resume_spaced.replace(p, ' ')
    resume_spaced = ' '.join(resume_spaced.split())
    
    resume_variants = [resume_lower, resume_no_punct, resume_spaced]
    
    missing = []
    for kw_dict in jd_required_keywords:
        kw = kw_dict["keyword"]
        kw_variants = _get_variants(kw)
        
        found = False
        for variant in kw_variants:
            if any(re.search(rf'\b{re.escape(variant)}\b', rv) for rv in resume_variants):
                found = True
                break
                
        if not found:
            missing.append(kw)
            
    return missing
