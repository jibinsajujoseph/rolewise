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
  const [isDragging, setIsDragging] = useState(false);
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [extractedResume, setExtractedResume] = useState(null);
  const [summarySuggestion, setSummarySuggestion] = useState(null);
  const [keywordSuggestions, setKeywordSuggestions] = useState([]);
  const [bulletSuggestions, setBulletSuggestions] = useState([]);
  const [structureSuggestions, setStructureSuggestions] = useState([]);
  
  const [coverLetter, setCoverLetter] = useState(null);
  const [isGeneratingCoverLetter, setIsGeneratingCoverLetter] = useState(false);
  const [coverLetterError, setCoverLetterError] = useState('');
  const [copiedItems, setCopiedItems] = useState({});
  const [expandedKeyword, setExpandedKeyword] = useState(null);
  
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

  const processFile = (file) => {
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

  const handleFileChange = (e) => {
    processFile(e.target.files[0]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
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
      
      setExtractedResume(data.extracted_resume);
      setSummarySuggestion(data.summary_suggestion);
      setKeywordSuggestions(data.keyword_suggestions || []);
      setBulletSuggestions(data.bullet_suggestions || []);
      setStructureSuggestions(data.structure_suggestions || []);
      setCoverLetter(null);
      setCopiedItems({});
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };



  const handleCopyItem = async (text, id) => {
    if (text) {
      await navigator.clipboard.writeText(text);
      setCopiedItems(prev => ({ ...prev, [id]: true }));
      setTimeout(() => setCopiedItems(prev => ({ ...prev, [id]: false })), 2000);
    }
  };

  const handleGenerateCoverLetter = async () => {
    setIsGeneratingCoverLetter(true);
    setCoverLetterError('');
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (requiresApiKey) {
        headers['X-Gemini-Api-Key'] = apiKey;
      }
      const response = await fetch(`${API_URL}/api/cover-letter`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          resume: extractedResume,
          jd_text: jdText
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to generate cover letter');
      setCoverLetter(data.cover_letter);
    } catch (err) {
      setCoverLetterError(err.message);
    } finally {
      setIsGeneratingCoverLetter(false);
    }
  };

  const resetFlow = () => {
    setStep(1);
    setExtractedResume(null);
    setSummarySuggestion(null);
    setKeywordSuggestions([]);
    setBulletSuggestions([]);
    setStructureSuggestions([]);
    setCoverLetter(null);
    setCoverLetterError('');
    setExpandedKeyword(null);
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
                  className={`upload-dropzone flex-grow ${isDragging ? 'dragging' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  style={{
                    backgroundColor: isDragging ? '#f0fdf4' : '',
                    borderColor: isDragging ? 'var(--tertiary)' : ''
                  }}
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
            </div>

            <div className="suggestions-layout flex flex-col gap-6 max-w-4xl mx-auto w-full">
               
               {summarySuggestion && (
                 <div className="card">
                    <div className="flex justify-between items-start mb-4">
                      <label className="label mb-0" style={{ fontSize: '16px', color: 'var(--primary)' }}>Summary Suggestion</label>
                      <button className="btn btn-secondary" onClick={() => handleCopyItem(summarySuggestion.suggested, 'summary')} style={{ padding: '6px 12px' }}>
                        {copiedItems['summary'] ? <CheckCircle2 size={14} /> : <Copy size={14} />} {copiedItems['summary'] ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    {summarySuggestion.original && (
                      <div className="diff-old mb-2">{summarySuggestion.original}</div>
                    )}
                    <div className="diff-new mb-3">{summarySuggestion.suggested}</div>
                    <p style={{ fontSize: '13px', color: 'var(--secondary)' }}><strong>Why:</strong> {summarySuggestion.rationale}</p>
                 </div>
               )}

               <div className="card">
                  <label className="label" style={{ fontSize: '16px', color: 'var(--primary)', marginBottom: '16px' }}>Keyword Strategy</label>
                  {keywordSuggestions.length === 0 ? (
                    <p style={{ fontSize: '14px', color: 'var(--secondary)' }}>No keyword suggestions here — this section looks strong.</p>
                  ) : (
                    <div className="flex flex-col gap-4">
                      <div className="flex flex-wrap gap-2">
                        {keywordSuggestions.map((kw, idx) => (
                          <span 
                            key={idx} 
                            onClick={() => setExpandedKeyword(expandedKeyword === idx ? null : idx)}
                            className="chip cursor-pointer" 
                            style={{ 
                              backgroundColor: kw.present ? '#f0fdf4' : '#fff1f2', 
                              borderColor: kw.present ? '#86efac' : '#fecdd3', 
                              color: kw.present ? '#16a34a' : '#be123c',
                              opacity: expandedKeyword === idx ? 0.7 : 1
                            }}
                          >
                            {kw.keyword}
                          </span>
                        ))}
                      </div>
                      
                      {expandedKeyword !== null && keywordSuggestions[expandedKeyword] && (
                        <div className="suggestion-item" style={{ backgroundColor: 'var(--surface-container-lowest)' }}>
                          <div className="flex justify-between items-start mb-2">
                            <div>
                              <span style={{ fontWeight: 600, color: 'var(--primary)' }}>{keywordSuggestions[expandedKeyword].keyword}</span>
                              <span style={{ marginLeft: '8px', fontSize: '12px', color: 'var(--secondary)', textTransform: 'capitalize' }}>
                                ({keywordSuggestions[expandedKeyword].importance}, {keywordSuggestions[expandedKeyword].present ? 'Present' : 'Missing'})
                              </span>
                            </div>
                            <button className="btn btn-secondary" onClick={() => handleCopyItem(keywordSuggestions[expandedKeyword].suggestion, `kw-${expandedKeyword}`)} style={{ padding: '4px 8px', fontSize: '12px' }}>
                              {copiedItems[`kw-${expandedKeyword}`] ? <CheckCircle2 size={12} /> : <Copy size={12} />} {copiedItems[`kw-${expandedKeyword}`] ? 'Copied' : 'Copy'}
                            </button>
                          </div>
                          <p style={{ fontSize: '14px', color: 'var(--on-surface)' }}>{keywordSuggestions[expandedKeyword].suggestion}</p>
                        </div>
                      )}
                    </div>
                  )}
               </div>

               <div className="card">
                  <label className="label" style={{ fontSize: '16px', color: 'var(--primary)', marginBottom: '16px' }}>Bullet Improvements</label>
                  {bulletSuggestions.length === 0 ? (
                    <p style={{ fontSize: '14px', color: 'var(--secondary)' }}>No bullet suggestions here — this section looks strong.</p>
                  ) : (
                    <div className="flex flex-col gap-6">
                      {Array.from(new Set(bulletSuggestions.map(b => b.section))).map((section) => (
                        <div key={section}>
                          <div className="suggestion-section">{section}</div>
                          <div className="flex flex-col gap-4">
                            {bulletSuggestions.filter(b => b.section === section).map((bullet, bIdx) => (
                              <div key={bIdx} className="suggestion-item relative group">
                                <div className="diff-old mb-2">{bullet.original_bullet}</div>
                                <div className="diff-new mb-3 flex flex-col relative">
                                  <span>
                                    {bullet.suggested_bullet.includes('[') && bullet.suggested_bullet.includes(']') ? (
                                      <span style={{ display: 'inline-block' }}>
                                        {bullet.suggested_bullet.split(/(\[.*?\])/g).map((part, i) => 
                                          part.startsWith('[') && part.endsWith(']') ? 
                                          <span key={i} style={{ backgroundColor: '#fef08a', color: '#854d0e', padding: '2px 4px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}>{part}</span> 
                                          : part
                                        )}
                                      </span>
                                    ) : (
                                      bullet.suggested_bullet
                                    )}
                                  </span>
                                </div>
                                <p style={{ fontSize: '13px', color: 'var(--secondary)' }}><strong>Why:</strong> {bullet.reason}</p>
                                <button className="btn btn-secondary absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => handleCopyItem(bullet.suggested_bullet, `bullet-${section}-${bIdx}`)} style={{ padding: '4px 8px', fontSize: '12px', backgroundColor: '#ffffff', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                                  {copiedItems[`bullet-${section}-${bIdx}`] ? <CheckCircle2 size={12} /> : <Copy size={12} />} {copiedItems[`bullet-${section}-${bIdx}`] ? 'Copied' : 'Copy'}
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
               </div>

               {structureSuggestions.length > 0 && (
                 <div className="card">
                    <label className="label" style={{ fontSize: '16px', color: 'var(--primary)', marginBottom: '16px' }}>Structure & Formatting</label>
                    <ul style={{ listStyleType: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {structureSuggestions.map((st, i) => (
                        <li key={i} style={{ borderBottom: i < structureSuggestions.length - 1 ? '1px solid var(--outline)' : 'none', paddingBottom: i < structureSuggestions.length - 1 ? '12px' : '0' }}>
                          <p style={{ fontWeight: 600, color: 'var(--primary)', fontSize: '14px', marginBottom: '4px' }}>{st.title}</p>
                          <p style={{ fontSize: '14px', color: 'var(--secondary)' }}>{st.detail}</p>
                        </li>
                      ))}
                    </ul>
                 </div>
               )}

               <div className="card text-center mb-12" style={{ backgroundColor: 'var(--surface-container-low)' }}>
                  <label className="label mb-2" style={{ fontSize: '16px', color: 'var(--primary)' }}>Final Touch</label>
                  <p style={{ fontSize: '14px', color: 'var(--secondary)', marginBottom: '16px', maxWidth: '500px', margin: '0 auto 16px auto' }}>
                    Need a cover letter tailored to this role? We can generate a concise, factual draft based on your verified resume.
                  </p>
                  
                  {coverLetter ? (
                    <div className="text-left mt-6">
                      <div className="flex justify-between items-center mb-4">
                        <span style={{ fontWeight: 600, color: 'var(--primary)' }}>Generated Cover Letter</span>
                        <button className="btn btn-primary" onClick={() => handleCopyItem(coverLetter, 'coverLetter')} style={{ padding: '6px 12px' }}>
                          {copiedItems['coverLetter'] ? <CheckCircle2 size={14} /> : <Copy size={14} />} {copiedItems['coverLetter'] ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                      <div className="suggestion-item p-6 whitespace-pre-wrap" style={{ backgroundColor: '#ffffff', fontSize: '14px', lineHeight: '1.6' }}>
                        {coverLetter}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-4">
                      <button 
                        className="btn btn-primary" 
                        onClick={handleGenerateCoverLetter} 
                        disabled={isGeneratingCoverLetter}
                        style={{ padding: '12px 24px' }}
                      >
                        {isGeneratingCoverLetter ? <><Loader2 size={16} className="animate-spin" /> Generating...</> : 'Generate Cover Letter'}
                      </button>
                      {coverLetterError && (
                        <div className="error-text justify-center" style={{ marginTop: '0', fontSize: '13px', backgroundColor: '#fff1f2', border: '1px solid #fecdd3', padding: '8px 12px', borderRadius: '6px', color: '#be123c', maxWidth: '100%', wordBreak: 'break-word', textAlign: 'left', display: 'flex', alignItems: 'flex-start' }}>
                          <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                          <span style={{ marginLeft: '8px' }}>{coverLetterError}</span>
                        </div>
                      )}
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
