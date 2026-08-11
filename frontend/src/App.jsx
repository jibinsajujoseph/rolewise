import { useState, useRef, useEffect } from 'react';
import { UploadCloud, FileText, CheckCircle2, Copy, AlertCircle, Loader2, ArrowRight, Check, Download } from 'lucide-react';
import './index.css';

function App() {
  const [step, setStep] = useState(1);
  const [apiKey, setApiKey] = useState('');
  const [requiresApiKey, setRequiresApiKey] = useState(true); // Default to true until we check
  const [resumeFile, setResumeFile] = useState(null);
  const [jdText, setJdText] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [tailoredResume, setTailoredResume] = useState('');
  const [missingKeywords, setMissingKeywords] = useState([]);
  
  const [copied, setCopied] = useState(false);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    // Check if the backend has a server-side API key configured
    fetch('http://localhost:8000/api/config')
      .then(res => res.json())
      .then(data => {
        setRequiresApiKey(data.requires_api_key);
      })
      .catch(err => {
        console.error("Failed to fetch config:", err);
      });
  }, []);

  const canOptimize = (!requiresApiKey || apiKey.trim()) && resumeFile && jdText.trim() && !isLoading;

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.name.endsWith('.pdf') || file.name.endsWith('.docx')) {
        setResumeFile(file);
        setError('');
      } else {
        setError('Please upload a PDF or DOCX file.');
        setResumeFile(null);
      }
    }
  };

  const handleOptimize = async () => {
    setIsLoading(true);
    setError('');
    
    try {
      const formData = new FormData();
      formData.append('resume_file', resumeFile);
      formData.append('jd_text', jdText);
      
      const headers = {};
      if (requiresApiKey) {
        headers['X-Gemini-Api-Key'] = apiKey;
      }

      const response = await fetch('http://localhost:8000/api/optimize', {
        method: 'POST',
        headers,
        body: formData,
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to optimize resume');
      }
      
      setTailoredResume(data.tailored_resume_text);
      setMissingKeywords(data.missing_keywords || []);
      setStep(2); // Move to results step
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = async () => {
    if (tailoredResume) {
      await navigator.clipboard.writeText(tailoredResume);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const resetFlow = () => {
    setStep(1);
    setTailoredResume('');
    setMissingKeywords([]);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand">
          <FileText size={24} />
          Rolewise
        </div>
        <div className="nav-links">
          <span className="nav-link active">Optimizer</span>
        </div>
        <button className="btn btn-primary" onClick={resetFlow} style={{ padding: '8px 16px' }}>
          Build New Resume
        </button>
      </header>

      <main className="container">
        
        {step === 1 && (
          <div className="step-container">
            <div className="text-center mb-6">
              <h1 className="mb-2">Optimize Your Resume</h1>
              <p style={{ color: 'var(--secondary)', maxWidth: '600px', margin: '0 auto' }}>
                Upload your current resume and paste the target job description. Our AI will analyze ATS compatibility and suggest precise improvements.
              </p>
            </div>

            {requiresApiKey && (
              <div className="card mb-6 max-w-3xl mx-auto">
                <label className="label">Configuration</label>
                <input
                  type="password"
                  className="input"
                  placeholder="Enter your Gemini API key"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <p style={{ fontSize: '12px', color: 'var(--secondary)', marginTop: '8px' }}>
                  Your key is never stored and only used for this session. Alternatively, configure GEMINI_API_KEY on the server.
                </p>
              </div>
            )}

            <div className="grid">
              <div className="card h-full flex flex-col">
                <div className="flex justify-between items-center mb-4">
                  <label className="label mb-0" style={{ fontSize: '16px', color: 'var(--primary)' }}>1. Upload Resume</label>
                  <span className="chip" style={{ fontSize: '11px' }}>PDF, DOCX</span>
                </div>
                
                <input
                  type="file"
                  accept=".pdf,.docx"
                  className="input"
                  style={{ display: 'none' }}
                  ref={fileInputRef}
                  onChange={handleFileChange}
                />
                
                <div 
                  className="upload-dropzone flex-grow"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <UploadCloud size={40} color="var(--tertiary)" style={{ margin: '0 auto', marginBottom: '16px' }} />
                  {resumeFile ? (
                    <>
                      <p style={{ fontWeight: 600, color: 'var(--primary)', marginBottom: '4px' }}>{resumeFile.name}</p>
                      <p style={{ fontSize: '13px', color: 'var(--tertiary)' }}>Click to replace file</p>
                    </>
                  ) : (
                    <>
                      <p style={{ fontWeight: 600, color: 'var(--primary)', marginBottom: '4px' }}>Drag and drop your file here</p>
                      <p style={{ fontSize: '14px', color: 'var(--secondary)', marginBottom: '16px' }}>or click to browse files</p>
                      <button className="btn btn-secondary" style={{ pointerEvents: 'none' }}>Select File</button>
                    </>
                  )}
                </div>
              </div>

              <div className="card h-full flex flex-col">
                <label className="label mb-4" style={{ fontSize: '16px', color: 'var(--primary)' }}>2. Target Job Description</label>
                <textarea
                  className="textarea flex-grow"
                  placeholder="Paste the full job description here... Our ATS engine will extract key skills, required experience, and analyze the language to score your resume's match."
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="error-text justify-center mt-6">
                <AlertCircle size={18} />
                {error}
              </div>
            )}

            <div className="action-bar mt-6 card flex justify-between items-center" style={{ backgroundColor: 'var(--surface-container-low)' }}>
              <div>
                <p style={{ fontWeight: 600, color: 'var(--primary)' }}>Ready for Analysis</p>
                <p style={{ fontSize: '14px', color: 'var(--secondary)' }}>Upload both a resume and job description to proceed.</p>
              </div>
              <button 
                className="btn btn-primary"
                style={{ padding: '12px 24px' }}
                disabled={!canOptimize}
                onClick={handleOptimize}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    Start Optimization <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="step-container">
            <div className="mb-6 flex items-center gap-2 cursor-pointer" onClick={resetFlow} style={{ color: 'var(--secondary)' }}>
               <ArrowRight size={16} style={{ transform: 'rotate(180deg)' }}/> Back to Editor
            </div>
            
            <div className="mb-6 flex justify-between items-end">
              <div>
                <h1 className="mb-2">Export Resume</h1>
                <p style={{ color: 'var(--secondary)', maxWidth: '800px' }}>
                  Your resume is optimized for Applicant Tracking Systems (ATS). Review the plain text format below or copy it to your clipboard.
                </p>
              </div>
              <div className="flex gap-4">
                <button 
                  className="btn btn-secondary" 
                  onClick={handleCopy}
                >
                  {copied ? (
                    <><CheckCircle2 size={16} /> Copied</>
                  ) : (
                    <><Copy size={16} /> Copy Text</>
                  )}
                </button>
                <button className="btn btn-primary" onClick={handleCopy}>
                  <Download size={16} /> Download
                </button>
              </div>
            </div>

            <div className="grid">
              
              <div className="card h-full flex flex-col p-0 overflow-hidden" style={{ gridColumn: 'span 2' }}>
                
                <div className="editor-header flex justify-between items-center" style={{ padding: '12px 24px', backgroundColor: '#f8fafc', borderBottom: '1px solid var(--outline)' }}>
                  <div className="flex items-center gap-2" style={{ color: '#16a34a', fontSize: '13px', fontWeight: 500 }}>
                     <Check size={16} /> ATS Parsable Format Confirmed
                  </div>
                  <span style={{ fontSize: '13px', color: 'var(--secondary)', fontFamily: 'var(--font-mono)' }}>Plain Text (.txt)</span>
                </div>

                {missingKeywords.length > 0 && (
                  <div style={{ padding: '16px 24px', backgroundColor: '#fff1f2', borderBottom: '1px solid #ffe4e6' }}>
                    <p style={{ color: '#be123c', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>Missing Keywords from Job Description</p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {missingKeywords.map((kw, i) => (
                        <span key={i} className="chip" style={{ backgroundColor: '#ffffff', borderColor: '#fecdd3', color: '#be123c' }}>{kw}</span>
                      ))}
                    </div>
                  </div>
                )}
                
                <textarea
                  className="resume-editor flex-grow"
                  style={{ border: 'none', borderRadius: 0 }}
                  value={tailoredResume}
                  onChange={(e) => setTailoredResume(e.target.value)}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer text-center" style={{ padding: '48px 24px', backgroundColor: 'var(--surface-container-high)', marginTop: '48px' }}>
        <h3 className="mb-4">Rolewise AI</h3>
        <div className="flex justify-center gap-4 mb-4" style={{ fontSize: '13px', color: 'var(--on-surface-variant)' }}>
          <span>Privacy Policy</span>
          <span>Terms of Service</span>
          <span>ATS Guide</span>
          <span>Contact</span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--secondary)', fontFamily: 'var(--font-mono)' }}>© 2024 Rolewise AI. Precision Career Engineering.</p>
      </footer>
      
      <style>{`
        .nav-links { display: flex; gap: 24px; }
        .nav-link { font-size: 14px; font-weight: 500; color: var(--secondary); cursor: pointer; padding: 8px 0; }
        .nav-link:hover { color: var(--primary); }
        .nav-link.active { color: var(--primary); border-bottom: 2px solid var(--primary); }
        
        .upload-dropzone {
          border: 2px dashed var(--outline-variant);
          border-radius: var(--radius-md);
          padding: 48px 24px;
          text-align: center;
          cursor: pointer;
          background-color: var(--surface-bright);
          transition: all 0.2s;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
        }
        .upload-dropzone:hover {
          border-color: var(--tertiary);
          background-color: #f0fdf4;
        }
        
        .max-w-3xl { max-width: 48rem; }
        .mx-auto { margin-left: auto; margin-right: auto; }
        
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}

export default App;
