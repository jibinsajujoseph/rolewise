# Rolewise

**Your resume, tailored to the role.**

Rolewise is an AI-powered resume optimization tool that strictly tailors your existing resume to a specific job description without hallucinating or fabricating facts. It extracts your true professional history and intelligently rewrites it to bypass Applicant Tracking Systems (ATS) while maintaining 100% factual integrity.

## Features

- **Strict Factual Integrity**: Utilizes a two-step Gemini LLM pipeline to ensure no fake jobs, skills, or metrics are ever added to your resume.
- **Born-Digital Parsing**: Safely reads PDF and DOCX files locally.
- **Missing Keyword Analysis**: Deterministically cross-references your resume against the job description to highlight missing ATS keywords.
- **Flexible Configuration**: Supports both Bring-Your-Own-Key (BYOK) mode for users and Server-Mode for hosted deployments.
- **Executive Precision Design**: A modern, distraction-free user interface built for career professionals.

## Architecture

Rolewise is a stateless application built with:
- **Frontend**: React + Vite (Vanilla CSS)
- **Backend**: FastAPI (Python)
- **AI Engine**: Google Gemini (gemini-2.5-flash)

No databases are used. Resumes and Job Descriptions are processed entirely in memory and immediately discarded after the request to ensure maximum privacy.

## Setup Instructions

### 1. Backend (FastAPI)

Navigate to the `backend` directory and set up a virtual environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Configuration
Copy the `.env.example` file to create your local `.env`:
```bash
cp .env.example .env
```

You can run the backend in two modes:
- **BYOK (Bring Your Own Key)**: Leave `KEY_SOURCE=byok`. The frontend will prompt the user to paste their Gemini API key.
- **Server Mode**: Set `KEY_SOURCE=server` and provide your `GEMINI_API_KEY`. The frontend will automatically hide the API key input.

Start the backend development server:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend (React + Vite)

Open a new terminal window, navigate to the `frontend` directory, and install dependencies:

```bash
cd frontend
npm install
```

Start the frontend development server:
```bash
npm run dev
```

The application will be available at [http://localhost:5173](http://localhost:5173).

## Usage

1. Upload your current, text-based PDF or DOCX resume.
2. Paste the full target Job Description.
3. Click "Start Optimization".
4. Review your tailored resume and the missing keywords analysis.
5. Copy your new tailored resume directly to your clipboard!
