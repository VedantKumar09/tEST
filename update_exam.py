import sys

file_path = r"c:\Users\jisha\OneDrive\Desktop\Vedant\frontend\src\pages\ExamPage.jsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
content = content.replace(
    "import { examAPI, proctoringAPI } from '../services/api';",
    "import { examAPI, proctoringAPI, codeAPI } from '../services/api';\nimport CodeEditor from '../components/compiler/CodeEditor';\nimport QuestionDisplay from '../components/compiler/QuestionDisplay';"
)

# 2. State Additions
state_addition = """  const [showSubmitModal, setShowSubmitModal] = useState(false);

  // ── Coding state ────────────────────────────────────────────────────────────
  const [codingSolutions, setCodingSolutions] = useState({});
  const [codingOutputs, setCodingOutputs] = useState({});
  const [activeLanguage, setActiveLanguage] = useState({});
  const [codeRunning, setCodeRunning] = useState(false);
  const [stdins, setStdins] = useState({});
  const [executionTimes, setExecutionTimes] = useState({});
  const [codingScores, setCodingScores] = useState({});
"""
content = content.replace("  const [showSubmitModal, setShowSubmitModal] = useState(false);", state_addition)

# 3. Coding Handlers
handlers = """  const logEvent = (type, msg) => {
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    setEvents(prev => [{ type, msg, timeStr }, ...prev].slice(0, 50));
  };

  // ── Coding handlers ─────────────────────────────────────────────────────────
  const handleRunCode = async (qId) => {
    const q = questions[currentQ];
    if (q.type !== 'coding') return;
    const code = codingSolutions[qId] ?? q.starter_code ?? '';
    const lang = activeLanguage[qId] ?? q.language ?? 'python';
    const input = stdins[qId] ?? '';
    
    setCodeRunning(true);
    setCodingOutputs(prev => ({...prev, [qId]: 'Executing...'}));
    
    try {
      const res = await codeAPI.execute(lang, code, input);
      setCodingOutputs(prev => ({...prev, [qId]: res.output || res.error || 'No output'}));
      if (res.execution_time_ms) {
        setExecutionTimes(prev => ({...prev, [qId]: `${res.execution_time_ms.toFixed(1)}ms`}));
      }
    } catch (err) {
      setCodingOutputs(prev => ({...prev, [qId]: 'Execution failed: ' + err.message}));
    } finally {
      setCodeRunning(false);
    }
  };

  const handleSubmitCode = async (qId) => {
    const q = questions[currentQ];
    if (q.type !== 'coding') return;
    const code = codingSolutions[qId] ?? q.starter_code ?? '';
    const lang = activeLanguage[qId] ?? q.language ?? 'python';
    
    setCodeRunning(true);
    setCodingOutputs(prev => ({...prev, [qId]: 'Submitting and running hidden tests...'}));
    
    try {
      const res = await codeAPI.submit(lang, code, qId);
      const passed = res.passed_tests;
      const total = res.total_tests;
      const pct = total ? Math.round((passed / total) * 100) : 0;
      
      let outText = `Submission Result: ${res.status.toUpperCase()}\\n`;
      outText += `Passed ${passed} of ${total} test cases. (Score: ${pct}%)\\n\\n`;
      if (res.details) {
         res.details.forEach((d, i) => {
            outText += `Test ${i+1}: ${d.status === 'pass' ? '✅ Pass' : '❌ Fail'}\\n`;
            if (d.error) outText += `   Error: ${d.error}\\n`;
         });
      }
      setCodingOutputs(prev => ({...prev, [qId]: outText}));
      setCodingScores(prev => ({...prev, [qId]: pct}));

      const nextAnswers = [...answers];
      nextAnswers[currentQ] = pct;
      setAnswers(nextAnswers);

    } catch (err) {
      setCodingOutputs(prev => ({...prev, [qId]: 'Submission failed: ' + err.message}));
    } finally {
      setCodeRunning(false);
    }
  };
"""
# Assuming logEvent definition is at the beginning of the proctoring refs/functions
content = content.replace(
    "  const logEvent = (type, msg) => {\n    const now = new Date();\n    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;\n    setEvents(prev => [{ type, msg, timeStr }, ...prev].slice(0, 50));\n  };",
    handlers
)

# 4. Modify HandleSubmit to include coding_scores
content = content.replace(
    "proctoring_data: procData,",
    "proctoring_data: procData,\n        coding_scores: codingScores,"
)

# 5. Modify Render block for question-area
render_old = """            {/* Question area */}
            <div className="question-area">
              <div className="glass-card question-card">
                <div className="q-meta">
                  <span className="q-number">Question {currentQ + 1} of {questions.length}</span>
                  <span className="badge badge-info">{q?.category}</span>
                </div>
                <div className="q-text">{q?.text}</div>
                <ul className="options-list">
                  {q?.options.map((opt, i) => (
                    <li
                      key={i}
                      className={`option-item ${answers[currentQ] === i ? 'selected' : ''}`}
                      onClick={() => {
                        if (!examStarted || examSubmitted) return;
                        const next = [...answers];
                        next[currentQ] = i;
                        setAnswers(next);
                      }}
                    >
                      <span className="option-letter">{letters[i]}</span>
                      <span>{opt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>"""

render_new = """            {/* Question or Coding area */}
            <div className={q?.type === 'coding' ? "coding-area" : "question-area"} style={q?.type === 'coding' ? { padding: '24px', overflowY: 'auto' } : {}}>
              {q?.type === 'coding' ? (
                <>
                  <QuestionDisplay 
                    question={q} 
                    stdin={stdins[q.id] ?? ''} 
                    setStdin={(val) => setStdins(prev => ({...prev, [q.id]: val}))} 
                  />
                  <div className="coding-editor-panel">
                    <CodeEditor 
                      code={codingSolutions[q.id] ?? q.starter_code ?? ''}
                      setCode={(val) => setCodingSolutions(prev => ({...prev, [q.id]: val}))}
                      language={activeLanguage[q.id] ?? q.language ?? 'python'}
                      setLanguage={(val) => setActiveLanguage(prev => ({...prev, [q.id]: val}))}
                      onRun={() => handleRunCode(q.id)}
                      running={codeRunning}
                      output={codingOutputs[q.id] ?? null}
                      executionTime={executionTimes[q.id]}
                    />
                    <button 
                      className="btn btn-success" 
                      onClick={() => handleSubmitCode(q.id)}
                      disabled={codeRunning}
                      style={{ padding: '8px 16px', fontWeight: 'bold' }}
                    >
                      {codeRunning ? 'Wait...' : 'Submit tests'}
                    </button>
                    {codingScores[q.id] !== undefined && (
                      <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(34, 197, 94, 0.1)', border: '1px solid #22c55e', borderRadius: '4px', color: '#22c55e', fontWeight: 'bold', fontSize: '12px' }}>
                         Highest Score Saved: {codingScores[q.id]}%
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="glass-card question-card">
                  <div className="q-meta">
                    <span className="q-number">Question {currentQ + 1} of {questions.length}</span>
                    <span className="badge badge-info">{q?.category}</span>
                  </div>
                  <div className="q-text">{q?.text}</div>
                  <ul className="options-list">
                    {q?.options?.map((opt, i) => (
                      <li
                        key={i}
                        className={`option-item ${answers[currentQ] === i ? 'selected' : ''}`}
                        onClick={() => {
                          if (!examStarted || examSubmitted) return;
                          const next = [...answers];
                          next[currentQ] = i;
                          setAnswers(next);
                        }}
                      >
                        <span className="option-letter">{letters[i]}</span>
                        <span>{opt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>"""

content = content.replace(render_old, render_new)

# 6. Formatting the dot in navigation
nav_dot_old = """className={`q-dot ${i === currentQ ? 'current' : ''} ${answers[i] !== -1 ? 'answered' : ''}`}"""
nav_dot_new = """className={`q-dot ${questions[i]?.type === 'coding' ? 'coding-dot' : ''} ${i === currentQ ? 'current' : ''} ${answers[i] !== -1 ? 'answered' : ''}`}"""
content = content.replace(nav_dot_old, nav_dot_new)

# 7. Navigation letter display fix
content = content.replace("""{q?.options.map((opt, i) => (""", """{q?.options?.map((opt, i) => (""")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("ExamPage.jsx updated successfully!")
