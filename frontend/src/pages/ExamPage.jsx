/**
 * Exam Page — Full exam interface with MCQ + Coding + AI Proctoring
 *
 * Setup flow: Camera → Identity → QR Cam → Exam
 *
 * Exam features:
 *  - MCQ questions with option selection
 *  - Coding questions with Monaco Editor, run/submit, stdin/stdout
 *  - Timer with auto-submit
 *
 * Proctoring features:
 *  - Real-time warning overlays (no face, looking away, multiple people, objects)
 *  - Cumulative risk score + risk level from backend scoring engine
 *  - Head pose + eye gaze attention indicators
 *  - Browser monitoring: tab switch, fullscreen exit, copy/paste, right click
 *  - DevTools detection (window size diff + debugger trap)
 *  - Fullscreen enforcement on exam start
 *
 * Phase 4 enhancements:
 *  - Monaco Editor integration for coding questions
 *  - Code execution (run) + submission (grade) via Phase 1 API
 *  - DevTools detection with violation reporting
 *  - Fullscreen enforcement with re-prompt
 *  - Keyboard shortcuts (Ctrl+Enter to run code)
 *  - Execution status loading indicator
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { useAuth } from '../context/AuthContext';
import { examAPI, proctoringAPI, codeAPI } from '../services/api';
import Editor from '@monaco-editor/react';

const FALLBACK_QUESTIONS = [
  { id: 1, type: 'mcq', category: 'CS Fundamentals', text: 'Which data structure uses LIFO ordering?', options: ['Queue', 'Stack', 'Linked List', 'Tree'] },
  { id: 2, type: 'mcq', category: 'CS Fundamentals', text: 'Time complexity of binary search?', options: ['O(n)', 'O(n²)', 'O(log n)', 'O(n log n)'] },
  { id: 3, type: 'mcq', category: 'CS Fundamentals', text: 'Which protocol is used for secure communication?', options: ['HTTP', 'FTP', 'HTTPS', 'SMTP'] },
];

const EXAM_DURATION = 600; // 10 minutes
const ANALYSIS_INTERVAL_MS = 700;

// Monaco language mapping
const LANG_MAP = { python: 'python', c: 'c', java: 'java', sql: 'sql' };

export default function ExamPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // ── Setup flow ──────────────────────────────────────────────────────────────
  const [step, setStep] = useState('camera'); // camera | identity | qr | exam

  // ── Camera ──────────────────────────────────────────────────────────────────
  const primaryVideoRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [identityPhoto, setIdentityPhoto] = useState(null);

  // Secondary cam
  const [secondCamUrl, setSecondCamUrl] = useState('');
  const [secondCamFrame, setSecondCamFrame] = useState(null);
  const [secondCamConnected, setSecondCamConnected] = useState(false);

  // ── Exam state ──────────────────────────────────────────────────────────────
  const [questions, setQuestions] = useState(FALLBACK_QUESTIONS);
  const [answers, setAnswers] = useState(new Array(FALLBACK_QUESTIONS.length).fill(-1));
  const [currentQ, setCurrentQ] = useState(0);
  const [timeLeft, setTimeLeft] = useState(EXAM_DURATION);
  const [examStarted, setExamStarted] = useState(false);
  const [examSubmitted, setExamSubmitted] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);

  // ── Coding editor state (Phase 4) ──────────────────────────────────────────
  const [codeSolutions, setCodeSolutions] = useState({}); // {questionId: code}
  const [codeOutput, setCodeOutput] = useState('');
  const [codeRunning, setCodeRunning] = useState(false);
  const [codeSubmitting, setCodeSubmitting] = useState(false);
  const [codeStdin, setCodeStdin] = useState('');
  const [codingScores, setCodingScores] = useState({}); // {questionId: score}
  const [codingQuestions, setCodingQuestions] = useState({}); // {id: full question data}
  const [execTime, setExecTime] = useState(null);
  const lastRunRef = useRef(0); // debounce

  // ── Proctoring state ────────────────────────────────────────────────────────
  const [violations, setViolations] = useState(0);
  const [events, setEvents] = useState([]);
  const [tabSwitches, setTabSwitches] = useState(0);
  const [faceDetected, setFaceDetected] = useState(true);
  const [showWarning, setShowWarning] = useState(false);
  const [showPause, setShowPause] = useState(false);
  const [examTerminated, setExamTerminated] = useState(false);
  const violationTypesRef = useRef([]);
  const [warningBanners, setWarningBanners] = useState([]);
  const [riskScore, setRiskScore] = useState(0);
  const [riskLevel, setRiskLevel] = useState('Low');
  const [headPose, setHeadPose] = useState({ yaw: 0, pitch: 0, looking_away: false });
  const [eyeGaze, setEyeGaze] = useState({ direction: 'center', looking_offscreen: false });
  const [attentionStatus, setAttentionStatus] = useState('Focused');

  // ── Fullscreen state (Phase 4) ─────────────────────────────────────────────
  const [fullscreenExits, setFullscreenExits] = useState(0);
  const [showFullscreenPrompt, setShowFullscreenPrompt] = useState(false);

  const timerRef = useRef(null);
  const analysisRef = useRef(null);
  const viewerWsRef = useRef(null);
  const devtoolsIntervalRef = useRef(null);

  const logEvent = (type, msg) => {
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    setEvents(prev => [{ type, msg, timeStr }, ...prev].slice(0, 50));
  };

  // ── Load questions (MCQ + coding) ──────────────────────────────────────────
  useEffect(() => {
    const loadAll = async () => {
      try {
        // Load exam questions (MCQ + coding refs)
        const q = await examAPI.getQuestions();
        setQuestions(q);
        setAnswers(new Array(q.filter(x => x.type === 'mcq').length).fill(-1));

        // Load full coding question data (descriptions, starter code)
        const codingQs = await codeAPI.getQuestions();
        const map = {};
        const starters = {};
        codingQs.forEach(cq => {
          map[cq.id] = cq;
          starters[cq.id] = cq.starter_code || '';
        });
        setCodingQuestions(map);
        setCodeSolutions(starters);
      } catch {
        setQuestions(FALLBACK_QUESTIONS);
        setAnswers(new Array(FALLBACK_QUESTIONS.length).fill(-1));
      }
    };
    loadAll();
  }, []);

  // ── Build second camera URL ─────────────────────────────────────────────────
  useEffect(() => {
    const sid = encodeURIComponent(user?.email || 'anonymous');
    const buildUrl = async () => {
      let host = window.location.hostname;
      const port = window.location.port || '5173';
      if (host === 'localhost' || host === '127.0.0.1') {
        try {
          const res = await fetch('/api/network/lan-ip');
          const data = await res.json();
          if (data.ip) host = data.ip;
        } catch { /* keep localhost */ }
      }
      const lanBase = `https://${host}:${port}`;
      setSecondCamUrl(`${lanBase}/qr-camera?sid=${sid}`);
    };
    buildUrl();
  }, [user]);

  // ── Primary camera init ─────────────────────────────────────────────────────
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (primaryVideoRef.current) {
        primaryVideoRef.current.srcObject = stream;
      }
      setCameraOn(true);
      setStep('identity');
    } catch {
      setStep('identity');
    }
  };

  const setPrimaryVideoRef = (el) => {
    primaryVideoRef.current = el;
    if (el && streamRef.current && !el.srcObject) {
      el.srcObject = streamRef.current;
      el.play().catch(() => {});
    }
  };

  const captureIdentity = async () => {
    if (!primaryVideoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = 320; canvas.height = 240;
    canvas.getContext('2d').drawImage(primaryVideoRef.current, 0, 0, 320, 240);
    const photo = canvas.toDataURL('image/jpeg', 0.8);
    setIdentityPhoto(photo);
    logEvent('success', 'Identity photo captured');

    // Send to backend for identity verification
    if (user?.email) {
      try {
        await proctoringAPI.verifyIdentity(user.email, photo);
        logEvent('success', 'Identity verified by server');
      } catch { /* handled gracefully */ }
    }
  };

  // ── Fullscreen enforcement (Phase 4) ────────────────────────────────────────
  const enterFullscreen = useCallback(async () => {
    try {
      await document.documentElement.requestFullscreen();
      setShowFullscreenPrompt(false);
    } catch {
      // Browser may block fullscreen without user gesture
    }
  }, []);

  // ── Start Exam ──────────────────────────────────────────────────────────────
  const startExam = async () => {
    if (user?.email) {
      try { await proctoringAPI.startSession(user.email); } catch { /* ignore */ }
    }
    setViolations(0);
    setTabSwitches(0);
    setRiskScore(0);
    setRiskLevel('Low');
    setEvents([]);
    setFaceDetected(true);
    setHeadPose({ yaw: 0, pitch: 0, looking_away: false });
    setEyeGaze({ direction: 'center', looking_offscreen: false });
    setAttentionStatus('Focused');
    setWarningBanners([]);
    setFullscreenExits(0);
    violationTypesRef.current = [];
    setCodeOutput('');
    setCodingScores({});

    setStep('exam');
    setExamStarted(true);
    logEvent('info', 'Exam started — AI proctoring active');

    // Enter fullscreen
    enterFullscreen();
  };

  // ── Timer ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted || examSubmitted) return;
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) { clearInterval(timerRef.current); handleSubmit(true); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [examStarted, examSubmitted]);

  // ── Warning banner helper ───────────────────────────────────────────────────
  const showWarningBanner = useCallback((msg) => {
    setWarningBanners(prev => {
      if (prev.includes(msg)) return prev;
      return [...prev, msg];
    });
    setTimeout(() => {
      setWarningBanners(prev => prev.filter(m => m !== msg));
    }, 4000);
  }, []);

  const computeAttention = useCallback((hp, eg) => {
    if (hp.looking_away && eg.looking_offscreen) return 'Away';
    if (hp.looking_away || eg.looking_offscreen) return 'Distracted';
    return 'Focused';
  }, []);

  const sendBrowserEvent = useCallback(async (eventType) => {
    if (!user?.email) return;
    try {
      const res = await proctoringAPI.sendBrowserEvent(user.email, eventType);
      if (res.cumulative_score !== undefined) {
        setRiskScore(res.cumulative_score || 0);
        setRiskLevel(res.risk_level || 'Low');
      }
    } catch { /* ignore */ }
  }, [user]);

  // ── Tab / visibility detection ──────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onVisibility = () => {
      if (document.hidden) {
        setTabSwitches(prev => prev + 1);
        addViolation('tab_switch');
        logEvent('danger', 'Tab switch detected!');
        showWarningBanner('⚠ Tab switch detected — stay on exam page');
        sendBrowserEvent('tab_switch');
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [examStarted, sendBrowserEvent, showWarningBanner]);

  // ── Fullscreen exit detection + enforcement ─────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onFullscreen = () => {
      if (!document.fullscreenElement) {
        setFullscreenExits(prev => {
          const next = prev + 1;
          if (next >= 3) {
            // After 3 exits, auto-submit
            logEvent('danger', 'Fullscreen exited 3 times — auto-submitting');
            handleSubmit(true);
          }
          return next;
        });
        addViolation('fullscreen_exit');
        logEvent('warning', 'Fullscreen exited');
        sendBrowserEvent('fullscreen_exit');
        showWarningBanner('⚠ Fullscreen exited — please re-enter fullscreen');
        setShowFullscreenPrompt(true);
      }
    };
    document.addEventListener('fullscreenchange', onFullscreen);
    return () => document.removeEventListener('fullscreenchange', onFullscreen);
  }, [examStarted, sendBrowserEvent, showWarningBanner]);

  // ── Copy / Paste detection ──────────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onCopy = (e) => {
      // Allow copy/paste inside Monaco editor area for coding questions
      const target = e.target;
      if (target && target.closest && target.closest('.monaco-editor')) return;
      e.preventDefault();
      addViolation('copy_paste');
      logEvent('danger', 'Copy/paste detected!');
      showWarningBanner('⚠ Copy/paste is not allowed');
      sendBrowserEvent('copy_paste');
    };
    document.addEventListener('copy', onCopy);
    document.addEventListener('paste', onCopy);
    document.addEventListener('cut', onCopy);
    return () => {
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('paste', onCopy);
      document.removeEventListener('cut', onCopy);
    };
  }, [examStarted, sendBrowserEvent, showWarningBanner]);

  // ── Right-click detection ───────────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onRightClick = (e) => {
      e.preventDefault();
      addViolation('right_click');
      logEvent('warning', 'Right-click detected');
      sendBrowserEvent('right_click');
    };
    document.addEventListener('contextmenu', onRightClick);
    return () => document.removeEventListener('contextmenu', onRightClick);
  }, [examStarted, sendBrowserEvent]);

  // ── DevTools detection (Phase 4) ────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;

    const checkDevTools = () => {
      // Method 1: Window size difference
      const widthDiff = window.outerWidth - window.innerWidth;
      const heightDiff = window.outerHeight - window.innerHeight;
      if (widthDiff > 160 || heightDiff > 160) {
        addViolation('devtools_open');
        logEvent('danger', 'DevTools detected (window size)');
        showWarningBanner('⚠ Developer Tools detected — close them immediately');
        sendBrowserEvent('devtools_open');
      }
    };

    // Method 2: Debugger trap via console timing
    const debuggerTrap = () => {
      const start = performance.now();
      // eslint-disable-next-line no-debugger
      debugger;
      const end = performance.now();
      if (end - start > 100) {
        addViolation('devtools_open');
        logEvent('danger', 'DevTools detected (debugger trap)');
        showWarningBanner('⚠ Developer Tools detected — close them immediately');
        sendBrowserEvent('devtools_open');
      }
    };

    // Check every 3 seconds (lightweight)
    devtoolsIntervalRef.current = setInterval(() => {
      checkDevTools();
      // Only run debugger trap occasionally (every 15s)
      if (Date.now() % 15000 < 3000) {
        try { debuggerTrap(); } catch { /* ignore */ }
      }
    }, 3000);

    return () => clearInterval(devtoolsIntervalRef.current);
  }, [examStarted, sendBrowserEvent, showWarningBanner]);

  // ── Keyboard shortcuts (Ctrl+Enter to run code) ────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        const q = questions[currentQ];
        if (q?.type === 'coding') runCode();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [examStarted, currentQ, questions]);

  // ── AI analysis ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted || examSubmitted) return;
    analysisRef.current = setInterval(() => analyzeFrame(), ANALYSIS_INTERVAL_MS);
    return () => clearInterval(analysisRef.current);
  }, [examStarted, examSubmitted]);

  const captureFrame = () => {
    if (!primaryVideoRef.current) return null;
    const canvas = document.createElement('canvas');
    canvas.width = 320; canvas.height = 240;
    canvas.getContext('2d').drawImage(primaryVideoRef.current, 0, 0, 320, 240);
    return canvas.toDataURL('image/jpeg', 0.6);
  };

  const analyzeFrame = async () => {
    const frame = captureFrame();
    if (!frame || !user?.email) return;
    try {
      const res = await proctoringAPI.analyzeFrame(frame, user.email);
      setFaceDetected(res.face_detected);
      if (res.head_pose) setHeadPose(res.head_pose);
      if (res.eye_gaze) setEyeGaze(res.eye_gaze);
      if (res.head_pose && res.eye_gaze) {
        setAttentionStatus(computeAttention(res.head_pose, res.eye_gaze));
      }
      if (res.score) {
        setRiskScore(res.score.cumulative_score || 0);
        setRiskLevel(res.score.risk_level || 'Low');
      }
      if (res.no_face) {
        addViolation('no_face');
        logEvent('danger', 'No face detected!');
        showWarningBanner('⚠ Face not detected');
      }
      if (res.multiple_faces) {
        addViolation('multiple_faces');
        logEvent('danger', 'Multiple faces detected!');
        showWarningBanner('⚠ Multiple people detected');
      }
      if (res.head_pose?.looking_away) {
        addViolation('looking_away');
        logEvent('warning', 'Looking away from screen');
        showWarningBanner('⚠ Please look at the screen');
      }
      if (res.eye_gaze?.looking_offscreen) {
        logEvent('warning', `Gaze off-screen: ${res.eye_gaze.direction}`);
      }
      if (res.suspicious_found) {
        res.objects_detected.forEach(obj => {
          addViolation(`object:${obj.class}`);
          logEvent('danger', `Suspicious object: ${obj.class} (${Math.round(obj.confidence * 100)}%)`);
          showWarningBanner(`⚠ Suspicious object detected: ${obj.class}`);
        });
      }
    } catch { /* ignore */ }
  };

  // ── WebSocket secondary camera ──────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted || !user?.email) return;
    const sid = encodeURIComponent(user.email);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/viewer/${sid}`;
    const connect = () => {
      const ws = new WebSocket(url);
      ws.onmessage = (e) => { setSecondCamFrame(e.data); setSecondCamConnected(true); };
      ws.onclose = () => { setSecondCamConnected(false); setTimeout(() => { if (examStarted && !examSubmitted) connect(); }, 2000); };
      const ping = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping'); }, 10000);
      ws.addEventListener('close', () => clearInterval(ping));
      viewerWsRef.current = ws;
    };
    connect();
    return () => { viewerWsRef.current?.close(); };
  }, [examStarted, user]);

  const addViolation = (type) => {
    violationTypesRef.current.push(type);
    setViolations(prev => {
      const next = prev + 1;
      if (next === 5) setShowWarning(true);
      if (next === 8) { setShowWarning(false); setShowPause(true); }
      if (next >= 12) { setShowPause(false); setExamTerminated(true); handleSubmit(true); }
      return next;
    });
  };

  // ── Code execution (Phase 4) ────────────────────────────────────────────────
  const runCode = async () => {
    const q = questions[currentQ];
    if (!q || q.type !== 'coding') return;

    // Debounce: min 1.5s between runs
    if (Date.now() - lastRunRef.current < 1500) return;
    lastRunRef.current = Date.now();

    const code = codeSolutions[q.id] || '';
    const lang = q.language || 'python';

    setCodeRunning(true);
    setCodeOutput('⏳ Running...');
    setExecTime(null);

    try {
      const result = await codeAPI.execute(lang, code, codeStdin);
      let output = '';
      if (result.error) output += `❌ ${result.error}\n`;
      if (result.stdout) output += result.stdout;
      if (result.stderr) output += `\n⚠ ${result.stderr}`;
      if (result.timed_out) output = '⏱ Time Limit Exceeded (10s max)';
      if (!output.trim()) output = '(no output)';
      setCodeOutput(output);
      setExecTime(result.execution_time_ms);
    } catch (err) {
      setCodeOutput(`❌ Network error: ${err.message}`);
    } finally {
      setCodeRunning(false);
    }
  };

  const submitCode = async () => {
    const q = questions[currentQ];
    if (!q || q.type !== 'coding') return;
    const code = codeSolutions[q.id] || '';
    const lang = q.language || 'python';

    setCodeSubmitting(true);
    setCodeOutput('📝 Grading against test cases...');

    try {
      const result = await codeAPI.submit(lang, code, q.id);
      let output = `📊 Score: ${result.score}% (${result.passed}/${result.total} tests passed)\n\n`;
      result.results?.forEach(tc => {
        const icon = tc.passed ? '✅' : '❌';
        output += `${icon} Test ${tc.test_case}: `;
        if (tc.passed) {
          output += `Passed (${tc.execution_time_ms}ms)\n`;
        } else {
          output += `Failed\n   Expected: ${tc.expected}\n   Got:      ${tc.actual}\n`;
          if (tc.stderr) output += `   Error: ${tc.stderr}\n`;
        }
      });
      setCodeOutput(output);
      setCodingScores(prev => ({ ...prev, [q.id]: result.score }));
      setExecTime(null);
    } catch (err) {
      setCodeOutput(`❌ Submission error: ${err.message}`);
    } finally {
      setCodeSubmitting(false);
    }
  };

  // ── Submit exam ─────────────────────────────────────────────────────────────
  const handleSubmit = async (terminated = false) => {
    if (examSubmitted) return;
    setExamSubmitted(true);
    clearInterval(timerRef.current);
    clearInterval(analysisRef.current);
    clearInterval(devtoolsIntervalRef.current);
    viewerWsRef.current?.close();

    // Exit fullscreen
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch { /* ignore */ }
    }

    const procData = {
      total_violations: violations,
      violation_types: [...new Set(violationTypesRef.current)],
      tab_switches: tabSwitches,
      risk_level: riskLevel,
      risk_score: riskScore,
    };

    if (user?.email) {
      try { await proctoringAPI.endSession(user.email); } catch { /* ignore */ }
    }

    try {
      const result = await examAPI.submitExam({
        answers,
        coding_scores: codingScores,
        time_used: EXAM_DURATION - timeLeft,
        proctoring_data: procData,
      });
      result.proctoring_summary = procData;
      localStorage.setItem('mm_exam_result', JSON.stringify(result));
    } catch {
      const mcqQuestions = questions.filter(q => q.type === 'mcq' || !q.type);
      const correct = answers.filter((a, i) => a !== -1 && mcqQuestions[i]).length;
      const localResult = {
        score: Math.round((correct / mcqQuestions.length) * 100),
        correct,
        questions_total: questions.length,
        questions_answered: answers.filter(a => a !== -1).length + Object.keys(codingScores).length,
        time_used: EXAM_DURATION - timeLeft,
        terminated,
        coding_scores: codingScores,
        proctoring_summary: procData,
      };
      localStorage.setItem('mm_exam_result', JSON.stringify(localResult));
    }
    navigate('/score');
  };

  // ── Derived values ──────────────────────────────────────────────────────────
  const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  const timerColor = timeLeft <= 60 ? 'var(--danger)' : timeLeft <= 180 ? 'var(--warning)' : 'var(--accent)';
  const letters = ['A', 'B', 'C', 'D'];
  const q = questions[currentQ];
  const isCoding = q?.type === 'coding';

  // Separate MCQ and coding questions for navigation
  const mcqQuestions = questions.filter(x => x.type === 'mcq' || !x.type);
  const codingQList = questions.filter(x => x.type === 'coding');
  // MCQ index for this question
  const mcqIndex = isCoding ? -1 : mcqQuestions.indexOf(q);

  const riskColor = riskLevel === 'Critical' ? 'var(--danger)' : riskLevel === 'High' ? '#ff6b35' : riskLevel === 'Medium' ? 'var(--warning)' : 'var(--success)';
  const attColor = attentionStatus === 'Away' ? 'var(--danger)' : attentionStatus === 'Distracted' ? 'var(--warning)' : 'var(--success)';
  const attIcon = attentionStatus === 'Focused' ? '🎯' : attentionStatus === 'Distracted' ? '👀' : '🚫';

  // Coding question data
  const codingData = isCoding ? codingQuestions[q.id] : null;

  // ──────────────────────────────────────────────────────────────────────────
  // RENDER
  // ──────────────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Navbar ── */}
      <nav className="navbar">
        <div className="navbar-inner container">
          <span className="navbar-brand">🧠 MindMesh</span>
          <ul className="navbar-links">
            <li><span className="badge badge-danger">● PROCTORING ACTIVE</span></li>
            <li>
              <button className="btn btn-outline btn-sm" onClick={() => { logout(); navigate('/login'); }}>
                🚪 Logout
              </button>
            </li>
          </ul>
        </div>
      </nav>

      {/* ── SETUP OVERLAYS ── */}
      {step === 'camera' && (
        <div className="setup-overlay">
          <div className="setup-card">
            <div className="setup-icon">📹</div>
            <h2>Enable Camera</h2>
            <p>MindMesh needs your webcam for AI proctoring. Your video is analyzed on the server for face detection and object detection. It is never recorded or stored.</p>
            <button className="btn btn-primary btn-lg" onClick={startCamera}>
              🔓 Enable Camera & Continue
            </button>
          </div>
        </div>
      )}

      {step === 'identity' && (
        <div className="setup-overlay">
          <div className="setup-card">
            <div className="setup-icon">🪪</div>
            <h2>Identity Verification</h2>
            <p>Please look directly at the camera and capture your identity photo. This is used as your reference image.</p>
            <div style={{ width: '100%', aspectRatio: '4/3', background: '#000', borderRadius: 'var(--radius-md)', overflow: 'hidden', marginBottom: 20, border: '2px solid var(--border)' }}>
              {!identityPhoto
                ? <video ref={setPrimaryVideoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }} />
                : <img src={identityPhoto} alt="Identity" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              }
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              {!identityPhoto
                ? <button className="btn btn-primary btn-lg" onClick={captureIdentity}>📸 Capture Photo</button>
                : <>
                    <button className="btn btn-outline" onClick={() => setIdentityPhoto(null)}>🔄 Retake</button>
                    <button className="btn btn-success btn-lg" onClick={() => setStep('qr')}>✅ Confirm & Continue</button>
                  </>
              }
            </div>
          </div>
        </div>
      )}

      {step === 'qr' && (
        <div className="setup-overlay">
          <div className="setup-card" style={{ maxWidth: 520 }}>
            <div className="setup-icon">📱</div>
            <h2>Connect Phone Camera</h2>
            <p>Scan the QR code with your phone to connect a secondary camera that monitors your exam desk.</p>
            <div style={{ padding: 20, background: '#fff', borderRadius: 'var(--radius-md)', display: 'inline-block', border: '3px solid var(--accent)', boxShadow: '0 0 24px var(--accent-glow)', margin: '16px 0' }}>
              <QRCodeSVG value={secondCamUrl} size={180} level="H" />
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', wordBreak: 'break-all', marginBottom: 8 }}>
              <a href={secondCamUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{secondCamUrl}</a>
            </p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>
              1. Open the link on your phone → 2. Tap "Start Camera" → 3. Click below
            </p>
            <button className="btn btn-success btn-lg" onClick={startExam} style={{ width: '100%', justifyContent: 'center' }}>
              ✅ Start Exam →
            </button>
          </div>
        </div>
      )}

      {/* ── PROCTORING OVERLAYS ── */}
      {showWarning && (
        <div className="warn-overlay" style={{ pointerEvents: 'none' }}>
          <div className="warn-card" style={{ border: '2px solid var(--warning)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
            <h2 style={{ color: 'var(--warning)', marginBottom: 8 }}>Warning</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
              You have {violations} violations. Continued violations will result in exam termination.
            </p>
            <button className="btn btn-outline" onClick={() => setShowWarning(false)} style={{ pointerEvents: 'all' }}>
              Acknowledge
            </button>
          </div>
        </div>
      )}

      {showPause && (
        <div className="warn-overlay blocking">
          <div className="warn-card" style={{ border: '2px solid var(--danger)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>⏸️</div>
            <h2 style={{ color: 'var(--danger)', marginBottom: 8 }}>Exam Paused</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
              {violations} violations recorded. Please ensure you are following exam rules.
            </p>
            <button className="btn btn-danger btn-lg" onClick={() => setShowPause(false)}>
              ▶ Acknowledge & Resume
            </button>
          </div>
        </div>
      )}

      {showFullscreenPrompt && (
        <div className="warn-overlay blocking">
          <div className="warn-card" style={{ border: '2px solid var(--warning)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>⛶</div>
            <h2 style={{ color: 'var(--warning)', marginBottom: 8 }}>Fullscreen Required</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
              You have exited fullscreen ({fullscreenExits}/3 allowed). Please re-enter fullscreen to continue.
            </p>
            <button className="btn btn-primary btn-lg" onClick={enterFullscreen}>
              ⛶ Re-enter Fullscreen
            </button>
          </div>
        </div>
      )}

      {showSubmitModal && (
        <div className="warn-overlay blocking">
          <div className="warn-card">
            <div style={{ fontSize: 40, marginBottom: 12 }}>📤</div>
            <h2 style={{ marginBottom: 8 }}>Submit Exam?</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
              MCQ Answered: <strong>{answers.filter(a => a !== -1).length}</strong> / <strong>{mcqQuestions.length}</strong> &nbsp;|&nbsp;
              Coding Submitted: <strong>{Object.keys(codingScores).length}</strong> / <strong>{codingQList.length}</strong>.
              This cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button className="btn btn-outline" onClick={() => setShowSubmitModal(false)}>← Go Back</button>
              <button className="btn btn-success btn-lg" onClick={() => { setShowSubmitModal(false); handleSubmit(false); }}>✅ Confirm Submit</button>
            </div>
          </div>
        </div>
      )}

      {/* ── MAIN EXAM LAYOUT ── */}
      {step === 'exam' && (
        <div className="exam-layout">
          {/* ── LEFT: Proctoring Panel ── */}
          <aside className="proctor-panel">
            {/* Primary webcam */}
            <div style={{ position: 'relative' }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>Primary Camera</p>
              <div className="cam-box" style={{ borderColor: cameraOn ? 'var(--success)' : 'var(--border)' }}>
                <video ref={setPrimaryVideoRef} autoPlay playsInline muted />
                <span className="cam-label">🎥 Primary</span>
                <span className={`cam-status-dot ${cameraOn ? 'active' : ''}`} />

                {examStarted && (
                  <div style={{
                    position: 'absolute', top: 4, left: 4,
                    background: 'rgba(0,0,0,0.7)', color: '#0f0',
                    fontFamily: 'monospace', fontSize: 10, padding: '4px 7px',
                    borderRadius: 4, zIndex: 11, lineHeight: 1.5, pointerEvents: 'none',
                  }}>
                    <div>Yaw: {headPose.yaw ?? 0}° | Pitch: {headPose.pitch ?? 0}°</div>
                    <div>Away: {headPose.looking_away ? '🔴 YES' : '🟢 NO'}</div>
                    <div>Gaze: {eyeGaze.direction ?? '—'} ({eyeGaze.ratio ?? '-'})</div>
                    <div>Attention: {attentionStatus}</div>
                  </div>
                )}

                {warningBanners.length > 0 && (
                  <div style={{
                    position: 'absolute', bottom: 28, left: 4, right: 4,
                    display: 'flex', flexDirection: 'column', gap: 4, zIndex: 10,
                  }}>
                    {warningBanners.map((msg, i) => (
                      <div key={i} style={{
                        background: 'rgba(239, 68, 68, 0.92)', color: '#fff',
                        fontSize: 11, fontWeight: 700, padding: '5px 10px',
                        borderRadius: 6, textAlign: 'center', backdropFilter: 'blur(4px)',
                      }}>
                        {msg}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Secondary cam */}
            <div>
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                Secondary Camera <span className={`badge ${secondCamConnected ? 'badge-success' : 'badge-info'}`} style={{ marginLeft: 6 }}>{secondCamConnected ? 'Connected' : 'Waiting'}</span>
              </p>
              <div className="cam-box" style={{ borderColor: secondCamConnected ? 'var(--success)' : 'var(--border)' }}>
                {secondCamFrame
                  ? <img src={secondCamFrame} alt="Secondary" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  : <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', flexDirection: 'column', gap: 8 }}>
                      <span style={{ fontSize: 28 }}>📱</span>
                      <span style={{ fontSize: 11 }}>Waiting for phone...</span>
                    </div>
                }
                <span className="cam-label">📱 Phone</span>
                <span className={`cam-status-dot ${secondCamConnected ? 'active' : ''}`} />
              </div>
            </div>

            {/* Stats */}
            <div className="proctor-stats">
              {[
                { val: violations, lbl: 'Violations', color: violations > 5 ? 'var(--danger)' : violations > 0 ? 'var(--warning)' : 'var(--success)' },
                { val: tabSwitches, lbl: 'Tab Switches', color: tabSwitches > 0 ? 'var(--warning)' : 'var(--success)' },
                { val: faceDetected ? '✅' : '❌', lbl: 'Face', color: faceDetected ? 'var(--success)' : 'var(--danger)' },
                { val: riskLevel, lbl: `Risk (${riskScore})`, color: riskColor },
                { val: `${attIcon}`, lbl: attentionStatus, color: attColor },
              ].map(({ val, lbl, color }) => (
                <div key={lbl} className="glass-card stat-card">
                  <div className="stat-val" style={{ color }}>{val}</div>
                  <div className="stat-lbl">{lbl}</div>
                </div>
              ))}
            </div>

            {/* Event log */}
            <div className="glass-card event-log">
              <h4>📋 Activity Log</h4>
              {events.length === 0
                ? <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>No events yet.</p>
                : events.map((ev, i) => (
                    <div key={i} className="event-item">
                      <span className="event-time">{ev.timeStr}</span>
                      <span>{ev.type === 'danger' ? '🚨' : ev.type === 'warning' ? '⚠️' : ev.type === 'success' ? '✅' : 'ℹ️'} {ev.msg}</span>
                    </div>
                  ))
              }
            </div>
          </aside>

          {/* ── RIGHT: Exam Panel ── */}
          <main className="exam-panel">
            {/* Header */}
            <div className="exam-header">
              <h2>📝 Assessment — {user?.name}</h2>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <span className="risk-indicator" style={{ background: riskColor + '22', color: riskColor, border: `1px solid ${riskColor}44` }}>
                  {riskLevel} ({riskScore})
                </span>
                <div className="timer" style={{ color: timerColor }}>{fmtTime(timeLeft)}</div>
              </div>
            </div>

            {/* ── MCQ Question ── */}
            {!isCoding && (
              <div className="question-area">
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
                        className={`option-item ${answers[mcqIndex] === i ? 'selected' : ''}`}
                        onClick={() => {
                          if (!examStarted || examSubmitted) return;
                          const next = [...answers];
                          next[mcqIndex] = i;
                          setAnswers(next);
                        }}
                      >
                        <span className="option-letter">{letters[i]}</span>
                        <span>{opt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* ── Coding Question (Phase 4) ── */}
            {isCoding && codingData && (
              <div className="coding-area">
                {/* Question description */}
                <div className="coding-question-panel">
                  <div className="q-meta">
                    <span className="q-number">Question {currentQ + 1} of {questions.length}</span>
                    <span className="badge badge-info">{q.category}</span>
                    <span className="badge badge-success">{q.difficulty}</span>
                    {codingScores[q.id] !== undefined && (
                      <span className="badge" style={{ background: codingScores[q.id] >= 100 ? 'var(--success)' : 'var(--warning)', color: '#fff' }}>
                        Score: {codingScores[q.id]}%
                      </span>
                    )}
                  </div>
                  <h3 className="coding-title">{codingData.title}</h3>
                  <div className="coding-description">{codingData.description}</div>
                </div>

                {/* Editor + output */}
                <div className="coding-editor-panel">
                  <div className="editor-header">
                    <span className="editor-lang-badge">{q.language?.toUpperCase()}</span>
                    <div className="editor-actions">
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={runCode}
                        disabled={codeRunning || codeSubmitting}
                        title="Ctrl+Enter"
                      >
                        {codeRunning ? '⏳ Running...' : '▶ Run Code'}
                      </button>
                      <button
                        className="btn btn-success btn-sm"
                        onClick={submitCode}
                        disabled={codeRunning || codeSubmitting}
                      >
                        {codeSubmitting ? '📝 Grading...' : '📤 Submit'}
                      </button>
                    </div>
                  </div>

                  <div className="monaco-wrapper">
                    <Editor
                      height="300px"
                      language={LANG_MAP[q.language] || 'python'}
                      theme="vs-dark"
                      value={codeSolutions[q.id] || ''}
                      onChange={(val) => setCodeSolutions(prev => ({ ...prev, [q.id]: val || '' }))}
                      options={{
                        fontSize: 14,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                        automaticLayout: true,
                        tabSize: 4,
                        lineNumbers: 'on',
                        renderLineHighlight: 'all',
                        padding: { top: 8 },
                      }}
                    />
                  </div>

                  {/* Stdin input */}
                  <div className="stdin-section">
                    <label className="stdin-label">📥 Input (stdin)</label>
                    <textarea
                      className="stdin-textarea"
                      value={codeStdin}
                      onChange={(e) => setCodeStdin(e.target.value)}
                      placeholder="Enter input here (one value per line)..."
                      rows={2}
                    />
                  </div>

                  {/* Output console */}
                  <div className="output-console">
                    <div className="output-header">
                      <span>📤 Output</span>
                      {execTime !== null && <span className="exec-time">{execTime}ms</span>}
                    </div>
                    <pre className="output-content">{codeOutput || 'Run your code to see output here.'}</pre>
                  </div>
                </div>
              </div>
            )}

            {/* Coding question but no data loaded yet */}
            {isCoding && !codingData && (
              <div className="question-area">
                <div className="glass-card question-card" style={{ textAlign: 'center', padding: '40px' }}>
                  <span style={{ fontSize: 32 }}>⏳</span>
                  <p>Loading coding challenge...</p>
                </div>
              </div>
            )}

            {/* Nav bar */}
            <div className="question-nav">
              <div className="q-dots">
                {questions.map((qItem, i) => (
                  <span
                    key={i}
                    className={`q-dot ${i === currentQ ? 'current' : ''} ${
                      qItem.type === 'coding'
                        ? codingScores[qItem.id] !== undefined ? 'answered' : ''
                        : answers[mcqQuestions.indexOf(qItem)] !== -1 ? 'answered' : ''
                    } ${qItem.type === 'coding' ? 'coding-dot' : ''}`}
                    onClick={() => examStarted && setCurrentQ(i)}
                    title={qItem.type === 'coding' ? `Coding: ${qItem.title}` : `MCQ ${i + 1}`}
                  >
                    {qItem.type === 'coding' ? '‹›' : i + 1}
                  </span>
                ))}
              </div>
              <div className="nav-btns">
                <button className="btn btn-outline" onClick={() => setCurrentQ(p => Math.max(p - 1, 0))} disabled={currentQ === 0}>
                  ← Prev
                </button>
                {currentQ < questions.length - 1
                  ? <button className="btn btn-primary" onClick={() => setCurrentQ(p => p + 1)}>Next →</button>
                  : <button className="btn btn-success" onClick={() => setShowSubmitModal(true)}>📤 Submit</button>
                }
              </div>
            </div>
          </main>
        </div>
      )}
    </>
  );
}
