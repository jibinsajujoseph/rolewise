import pdfplumber
import docx
from io import BytesIO

def parse_resume_file(filename: str, content: bytes) -> str:
    """
    Parses a PDF or DOCX file to extract born-digital text.
    Raises ValueError if the text is empty or suspiciously short (likely an image/scan).
    """
    text = ""
    
    if filename.lower().endswith(".pdf"):
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    elif filename.lower().endswith(".docx"):
        doc = docx.Document(BytesIO(content))
        for para in doc.paragraphs:
            if para.text:
                text += para.text + "\n"
    else:
        raise ValueError("Unsupported file format. Please upload a PDF or DOCX file.")
    
    # Check if text is suspiciously short (e.g., under 100 characters)
    if len(text.strip()) < 100:
        raise ValueError("Couldn't read text from this file — if it's a scanned image or photo, please upload a text-based PDF or Word doc instead.")
        
    return text.strip()
