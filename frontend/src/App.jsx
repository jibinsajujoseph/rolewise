import { useState, useRef, useEffect } from 'react';
import { UploadCloud, FileText, CheckCircle2, Copy, AlertCircle, Loader2, ArrowRight, Check, Download, FileDown } from 'lucide-react';
import './index.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [step, setStep] = useState(1);
  const [apiKey, setApiKey] = useState('');
  const [requiresApiKey, setRequiresApiKey] = useState(true);
  const [resumeFile, setResumeFile] = useState(null);
  const [jdText, setJdText] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [tailoredResume, setTailoredResume] = useState('');
  const [missingKeywords, setMissingKeywords] = useState([]);
  const [addedKeywords, setAddedKeywords] = useState([]);
  const [originalMatchScore, setOriginalMatchScore] = useState(0);
  const [newMatchScore, setNewMatchScore] = useState(0);
  
  const [copied, setCopied] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/api/config`)
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

      const response = await fetch(`${API_URL}/api/optimize`, {
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
      setAddedKeywords(data.added_keywords || []);
      setOriginalMatchScore(data.original_match_score || 0);
      setNewMatchScore(data.new_match_score || 0);
      setStep(2);
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

  const handleExport = async (format) => {
      setIsExporting(true);
      try {
          const response = await fetch(`${API_URL}/api/export/${format}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ text: tailoredResume })
          });
          if (!response.ok) throw new Error("Export failed");
          
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `Optimized_Resume.${format}`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
      } catch (err) {
          alert(err.message);
      } finally {
          setIsExporting(false);
      }
  };

  const resetFlow = () => {
    setStep(1);
    setTailoredResume('');
    setMissingKeywords([]);
    setAddedKeywords([]);
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

      <main className="container" style={{ maxWidth: step === 2 ? '1400px' : '1280px' }}>
        
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
            <div className="mb-6 flex justify-between items-center">
              <div className="flex items-center gap-2 cursor-pointer" onClick={resetFlow} style={{ color: 'var(--secondary)' }}>
                 <ArrowRight size={16} style={{ transform: 'rotate(180deg)' }}/> Back
              </div>
              <div className="flex gap-4">
                 <button className="btn btn-secondary" onClick={handleCopy}>
                    {copied ? <><CheckCircle2 size={16} /> Copied</> : <><Copy size={16} /> Copy Text</>}
                 </button>
                 <button className="btn btn-secondary" onClick={() => handleExport('docx')} disabled={isExporting}>
                    <FileDown size={16} /> Download DOCX
                 </button>
                 <button className="btn btn-primary" onClick={() => handleExport('pdf')} disabled={isExporting}>
                    <Download size={16} /> Download PDF
                 </button>
              </div>
            </div>

            <div className="optimization-layout">
               <div className="editor-pane">
                  <div className="card h-full flex flex-col p-0 overflow-hidden">
                    <div className="editor-header flex justify-between items-center" style={{ padding: '12px 24px', backgroundColor: '#f8fafc', borderBottom: '1px solid var(--outline)' }}>
                      <div className="flex items-center gap-2" style={{ color: '#16a34a', fontSize: '13px', fontWeight: 500 }}>
                         <Check size={16} /> ATS Parsable Format Confirmed
                      </div>
                      <span style={{ fontSize: '13px', color: 'var(--secondary)', fontFamily: 'var(--font-mono)' }}>Plain Text (.txt)</span>
                    </div>
                    <textarea
                      className="resume-editor flex-grow"
                      style={{ border: 'none', borderRadius: 0 }}
                      value={tailoredResume}
                      onChange={(e) => setTailoredResume(e.target.value)}
                    />
                  </div>
               </div>

               <div className="optimization-pane flex flex-col gap-4">
                  
                  <div className="card text-center flex flex-col items-center">
                     <label className="label w-full text-left mb-4">Match Score</label>
                     <div className="score-circle mb-2" style={{ position: 'relative' }}>
                        <svg viewBox="0 0 36 36" className="circular-chart">
                          <path className="circle-bg"
                            d="M18 2.0845
                              a 15.9155 15.9155 0 0 1 0 31.831
                              a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                          <path className="circle-new"
                            strokeDasharray={`${newMatchScore}, 100`}
                            d="M18 2.0845
                              a 15.9155 15.9155 0 0 1 0 31.831
                              a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                          <path className="circle-original"
                            strokeDasharray={`${originalMatchScore}, 100`}
                            d="M18 2.0845
                              a 15.9155 15.9155 0 0 1 0 31.831
                              a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                          <text x="18" y="20.35" className="percentage">{newMatchScore}</text>
                        </svg>
                     </div>
                     <p style={{ fontWeight: 500, fontSize: '14px', color: 'var(--primary)', marginBottom: '4px' }}>
                        Original: {originalMatchScore} → New: {newMatchScore}
                     </p>
                     <p style={{ fontSize: '13px', color: 'var(--secondary)' }}>
                        Consider adding missing keywords to further improve the match score.
                     </p>
                  </div>

                  {addedKeywords.length > 0 && (
                    <div className="card flex-grow" style={{ borderColor: '#86efac', backgroundColor: '#f0fdf4', alignSelf: 'flex-start', marginBottom: '16px' }}>
                      <label className="label" style={{ color: '#16a34a', marginBottom: '8px' }}>Added Keywords</label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {addedKeywords.map((kw, i) => (
                          <span key={i} className="chip" style={{ backgroundColor: '#ffffff', borderColor: '#86efac', color: '#16a34a' }}>{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {missingKeywords.length > 0 && (
                    <div className="card flex-grow" style={{ borderColor: '#fecdd3', backgroundColor: '#fff1f2', alignSelf: 'flex-start' }}>
                      <label className="label" style={{ color: '#be123c', marginBottom: '8px' }}>Missing Keywords</label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {missingKeywords.map((kw, i) => (
                          <span key={i} className="chip" style={{ backgroundColor: '#ffffff', borderColor: '#fecdd3', color: '#be123c' }}>{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}

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

        .optimization-layout {
           display: grid;
           grid-template-columns: 1fr;
           gap: 24px;
        }
        @media (min-width: 1024px) {
           .optimization-layout {
              grid-template-columns: 2fr 1fr;
           }
        }

        .score-circle {
           width: 120px;
           height: 120px;
        }
        .circular-chart {
           display: block;
           margin: 0 auto;
           max-width: 100%;
           max-height: 250px;
        }
        .circle-bg {
           fill: none;
           stroke: #eee;
           stroke-width: 3.8;
        }
        .circle-original {
           fill: none;
           stroke-width: 3.8;
           stroke-linecap: round;
           stroke: #0F172A;
           transition: stroke-dasharray 0.5s ease-out;
        }
        .circle-new {
           fill: none;
           stroke-width: 3.8;
           stroke-linecap: round;
           stroke: #10b981;
           transition: stroke-dasharray 0.5s ease-out;
        }
        .percentage {
           fill: #0F172A;
           font-family: var(--font-display);
           font-weight: 700;
           font-size: 10px;
           text-anchor: middle;
        }

        .suggestion-item {
           border: 1px solid var(--outline);
           border-radius: 6px;
           padding: 12px;
        }
        .suggestion-section {
           font-family: var(--font-mono);
           font-size: 11px;
           color: var(--secondary);
           margin-bottom: 8px;
           text-transform: uppercase;
        }
        .suggestion-diff {
           font-size: 13px;
           font-family: var(--font-body);
        }
        .diff-old {
           color: #be123c;
           background-color: #fff1f2;
           padding: 6px 8px;
           border-radius: 4px;
           margin-bottom: 4px;
           text-decoration: line-through;
        }
        .diff-new {
           color: #15803d;
           background-color: #f0fdf4;
           padding: 6px 8px;
           border-radius: 4px;
        }
      `}</style>
    </div>
  );
}

export default App;
