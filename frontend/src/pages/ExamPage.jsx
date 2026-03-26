/**
 * Exam Page — Main exam interface
 * Left: Primary webcam (server-side AI analysis every 2s) + Secondary phone cam feed
 * Right: MCQ questions + timer
 * Setup flow: Camera → Identity → QR Cam → Exam
 *
 * Enhanced proctoring:
 *  - Real-time warning overlays (no face, looking away, multiple people, objects)
 *  - Cumulative risk score + risk level from backend scoring engine
 *  - Head pose + eye gaze attention indicators
 *  - Browser monitoring (tab switch, fullscreen exit, copy/paste, right click)
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { useAuth } from '../context/AuthContext';
import { examAPI, proctoringAPI, codeAPI } from '../services/api';
import CodeEditor from '../components/compiler/CodeEditor';
import QuestionDisplay from '../components/compiler/QuestionDisplay';
import { initVision, analyzeFaceGeometry } from '../services/vision';

const FALLBACK_QUESTIONS = [
  { id: 1, category: 'CS Fundamentals', text: 'Which data structure uses LIFO ordering?', options: ['Queue', 'Stack', 'Linked List', 'Tree'] },
  { id: 2, category: 'CS Fundamentals', text: 'Time complexity of binary search?', options: ['O(n)', 'O(n²)', 'O(log n)', 'O(n log n)'] },
  { id: 3, category: 'CS Fundamentals', text: 'Which protocol is used for secure communication?', options: ['HTTP', 'FTP', 'HTTPS', 'SMTP'] },
  { id: 4, category: 'CS Fundamentals', text: 'What does DDL stand for in SQL?', options: ['Data Definition Language', 'Data Display Logic', 'Dynamic Data Layer', 'Database Design Language'] },
  { id: 5, category: 'CS Fundamentals', text: 'Which sorting algorithm has best average-case complexity?', options: ['Bubble Sort', 'Selection Sort', 'Merge Sort', 'Insertion Sort'] },
  { id: 6, category: 'AI & ML', text: 'Which technique classifies spam emails?', options: ['Linear Regression', 'K-Means', 'Naive Bayes', 'PCA'] },
  { id: 7, category: 'AI & ML', text: 'Activation function outputting values 0–1?', options: ['ReLU', 'Sigmoid', 'Tanh', 'Leaky ReLU'] },
  { id: 8, category: 'AI & ML', text: 'Technique to prevent overfitting in neural networks?', options: ['Dropout', 'Batch Norm', 'Gradient Descent', 'Backpropagation'] },
  { id: 9, category: 'AI & ML', text: 'CNN stands for?', options: ['Computer Neural Nets', 'Convolutional Neural Network', 'Central Neuron Node', 'Connected Network'] },
  { id: 10, category: 'AI & ML', text: 'Algorithm used for recommendation systems?', options: ['Decision Trees', 'Collaborative Filtering', 'KNN', 'SVM'] },
  { id: 11, category: 'Networking', text: 'TCP stands for?', options: ['Transfer Control Protocol', 'Transmission Control Protocol', 'Traffic Control Protocol', 'Transfer Call Protocol'] },
  { id: 12, category: 'Networking', text: 'OSI layer handling routing between networks?', options: ['Transport', 'Data Link', 'Network', 'Application'] },
  { id: 13, category: 'Networking', text: 'Encryption using public/private key pair?', options: ['Symmetric', 'Asymmetric', 'Hashing', 'Caesar Cipher'] },
  { id: 14, category: 'Networking', text: 'Attack that floods a server?', options: ['Phishing', 'SQL Injection', 'DDoS', 'Man-in-the-Middle'] },
  { id: 15, category: 'Networking', text: 'Default HTTPS port?', options: ['80', '21', '443', '8080'] },
];

const EXAM_DURATION = 600; // 10 minutes
const ANALYSIS_INTERVAL_MS = 2000; // send frame every 2000ms for stable detection

export default function ExamPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // ── Setup flow ──────────────────────────────────────────────────────────────
  const [step, setStep] = useState('camera'); // camera | identity | qr | exam

  // ── Camera ──────────────────────────────────────────────────────────────────
  const primaryVideoRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState('');
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

  // ── Coding state ────────────────────────────────────────────────────────────
  const [codingSolutions, setCodingSolutions] = useState({});
  const [codingOutputs, setCodingOutputs] = useState({});
  const [activeLanguage, setActiveLanguage] = useState({});
  const [codeRunning, setCodeRunning] = useState(false);
  const [stdins, setStdins] = useState({});
  const [executionTimes, setExecutionTimes] = useState({});
  const [codingScores, setCodingScores] = useState({});


  // ── Proctoring state ────────────────────────────────────────────────────────
  const [violations, setViolations] = useState(0);
  const [events, setEvents] = useState([]);
  const [tabSwitches, setTabSwitches] = useState(0);
  const [faceDetected, setFaceDetected] = useState(true);
  const [showWarning, setShowWarning] = useState(false);
  const [showPause, setShowPause] = useState(false);
  const [examTerminated, setExamTerminated] = useState(false);
  const violationTypesRef = useRef([]);

  // ── Enhanced proctoring state ───────────────────────────────────────────────
  const [warningBanners, setWarningBanners] = useState([]); // active warning messages
  const [riskScore, setRiskScore] = useState(0);
  const [riskLevel, setRiskLevel] = useState('Safe');
  const [headPose, setHeadPose] = useState({ yaw: 0, pitch: 0, looking_away: false });
  const [eyeGaze, setEyeGaze] = useState({ direction: 'center', looking_offscreen: false });
  const [attentionStatus, setAttentionStatus] = useState('Focused'); // Focused | Distracted | Away

  const timerRef = useRef(null);
  const analysisRef = useRef(null);
  const viewerWsRef = useRef(null);
  const warningTimeoutRef = useRef(null);

  const logEvent = (type, msg) => {
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
      
      let outText = `Submission Result: ${res.status.toUpperCase()}\n`;
      outText += `Passed ${passed} of ${total} test cases. (Score: ${pct}%)\n\n`;
      if (res.details) {
         res.details.forEach((d, i) => {
            outText += `Test ${i+1}: ${d.status === 'pass' ? '✅ Pass' : '❌ Fail'}\n`;
            if (d.error) outText += `   Error: ${d.error}\n`;
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


  // ── Load questions ──────────────────────────────────────────────────────────
  useEffect(() => {
    examAPI.getQuestions()
      .then(q => { setQuestions(q); setAnswers(new Array(q.length).fill(-1)); })
      .catch(() => {});
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
    setCameraError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (primaryVideoRef.current) {
        primaryVideoRef.current.srcObject = stream;
      }
      setCameraOn(true);
      setStep('identity');
    } catch (err) {
      setCameraOn(false);
      const message = err?.message || 'Camera permission denied or unavailable. Please allow camera and retry.';
      setCameraError(message);
      setStep('camera');
    }
  };

  const setPrimaryVideoRef = (el) => {
    primaryVideoRef.current = el;
    if (el && streamRef.current && !el.srcObject) {
      el.srcObject = streamRef.current;
      el.play().catch(() => {});
    }
  };

  const captureIdentity = () => {
    if (!primaryVideoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = 320; canvas.height = 240;
    canvas.getContext('2d').drawImage(primaryVideoRef.current, 0, 0, 320, 240);
    setIdentityPhoto(canvas.toDataURL('image/jpeg', 0.8));
    logEvent('success', 'Identity photo captured');
  };

  // ── Start Exam ──────────────────────────────────────────────────────────────
  const startExam = () => {
    setStep('exam');
    setExamStarted(true);
    logEvent('info', 'Exam started — AI proctoring active');
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
    // Auto-clear after 4 seconds
    setTimeout(() => {
      setWarningBanners(prev => prev.filter(m => m !== msg));
    }, 4000);
  }, []);

  // ── Compute attention status from head pose + eye gaze ──────────────────────
  const computeAttention = useCallback((hp, eg) => {
    if (hp.looking_away && eg.looking_offscreen) return 'Away';
    if (hp.looking_away || eg.looking_offscreen) return 'Distracted';
    return 'Focused';
  }, []);

  // ── Send browser events to backend ──────────────────────────────────────────
  const sendBrowserEvent = useCallback(async (eventType) => {
    if (!user?.email) return;
    try {
      const res = await proctoringAPI.sendBrowserEvent(user.email, eventType);
      if (res.score) {
        setRiskScore(res.score.cumulative_score || 0);
        setRiskLevel(res.score.risk_level || 'Safe');
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

  // ── Fullscreen exit detection ───────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onFullscreen = () => {
      if (!document.fullscreenElement) {
        addViolation('fullscreen_exit');
        logEvent('warning', 'Fullscreen exited');
        sendBrowserEvent('fullscreen_exit');
      }
    };
    document.addEventListener('fullscreenchange', onFullscreen);
    return () => document.removeEventListener('fullscreenchange', onFullscreen);
  }, [examStarted, sendBrowserEvent]);

  // ── Copy / Paste detection ──────────────────────────────────────────────────
  useEffect(() => {
    if (!examStarted) return;
    const onCopy = (e) => {
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

  // ── Client-side AI analysis via WebAssembly (Real-time 30FPS) ───────────────
  const faceLandmarkerRef = useRef(null);
  const objectDetectorRef = useRef(null);
  const lastVideoTimeRef = useRef(-1);
  const lastViolationTimeRef = useRef({ no_face: 0, multiple_faces: 0, looking_away: 0, looking_offscreen: 0, object: 0 });

  useEffect(() => {
    if (!examStarted || examSubmitted) return;
    let cancel = false;

    const runVision = async () => {
      try {
        if (!faceLandmarkerRef.current || !objectDetectorRef.current) {
          const visionModels = await initVision();
          faceLandmarkerRef.current = visionModels.faceLandmarker;
          objectDetectorRef.current = visionModels.objectDetector;
        }
        
        const predict = () => {
          if (cancel || examSubmitted || !primaryVideoRef.current) return;
          
          const video = primaryVideoRef.current;
          if (video.currentTime !== lastVideoTimeRef.current && video.videoWidth > 0) {
            lastVideoTimeRef.current = video.currentTime;
            const nowTime = performance.now();
            
            const results = faceLandmarkerRef.current.detectForVideo(video, nowTime);
            if (results && results.faceLandmarks) {
               const geom = analyzeFaceGeometry(results.faceLandmarks, video.videoWidth, video.videoHeight);
               
               setFaceDetected(geom.face_detected);
               if (geom.head_pose) setHeadPose(geom.head_pose);
               if (geom.eye_gaze) setEyeGaze(geom.eye_gaze);
               if (geom.head_pose && geom.eye_gaze) {
                 setAttentionStatus(computeAttention(geom.head_pose, geom.eye_gaze));
               }
               
               const now = performance.now();
               // Warning banners + violation logging
               if (geom.no_face && now - lastViolationTimeRef.current.no_face > 3000) {
                 lastViolationTimeRef.current.no_face = now;
                 addViolation('no_face');
                 logEvent('danger', 'No face detected!');
                 showWarningBanner('⚠ Face not detected');
               }
               if (geom.multiple_faces && now - lastViolationTimeRef.current.multiple_faces > 3000) {
                 lastViolationTimeRef.current.multiple_faces = now;
                 addViolation('multiple_faces');
                 logEvent('danger', 'Multiple faces detected!');
                 showWarningBanner('⚠ Multiple people detected');
               }
               if (geom.head_pose?.looking_away && now - lastViolationTimeRef.current.looking_away > 3000) {
                 lastViolationTimeRef.current.looking_away = now;
                 addViolation('looking_away');
                 logEvent('warning', 'Looking away from screen');
                 showWarningBanner('⚠ Please look at the screen');
               }
               if (geom.eye_gaze?.looking_offscreen && now - lastViolationTimeRef.current.looking_offscreen > 3000) {
                 lastViolationTimeRef.current.looking_offscreen = now;
                 logEvent('warning', `Gaze off-screen: ${geom.eye_gaze.direction}`);
               }
            }

            // Object Detection
            const objResults = objectDetectorRef.current.detectForVideo(video, nowTime);
            if (objResults && objResults.detections) {
              objResults.detections.forEach(det => {
                 const cls = det.categories[0].categoryName?.toLowerCase() || '';
                 const conf = det.categories[0].score;
                 
                 // Debug trace: console.log(`Detected: ${cls} - ${Math.round(conf * 100)}%`);
                 
                 const suspiciousCats = ['cell phone', 'book', 'laptop', 'tablet', 'remote', 'telephone', 'tv'];
                 if (suspiciousCats.includes(cls) && conf > 0.30) {
                    if (nowTime - lastViolationTimeRef.current.object > 5000) {
                      lastViolationTimeRef.current.object = nowTime;
                      
                      const alias = (cls === 'book' || cls === 'laptop') ? cls : 'Unauthorized Device';
                      
                      addViolation(`object:${cls}`);
                      logEvent('danger', `Suspicious object: ${alias} (${Math.round(conf * 100)}%)`);
                      showWarningBanner(`⚠ Suspicious object detected: ${alias.toUpperCase()}`);
                    }
                 }
              });
            }
          }
          analysisRef.current = requestAnimationFrame(predict);
        };
        
        predict();
      } catch (err) {
        logEvent('warning', 'AI vision initialization failed. Proctoring AI paused.');
        showWarningBanner('⚠ AI vision failed to initialize');
        console.error("WASM Vision setup failed:", err);
      }
    };
    
    runVision();
    return () => {
      cancel = true;
      if (analysisRef.current) cancelAnimationFrame(analysisRef.current);
    };
  }, [examStarted, examSubmitted, computeAttention, showWarningBanner]);

  // ── WebSocket receiver for secondary camera (30 FPS) ────────────────────────
  useEffect(() => {
    if (!examStarted || !user?.email) return;
    const sid = encodeURIComponent(user.email);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/viewer/${sid}`;

    const connect = () => {
      const ws = new WebSocket(url);
      ws.onmessage = (e) => {
        setSecondCamFrame(e.data);
        setSecondCamConnected(true);
      };
      ws.onclose = () => {
        setSecondCamConnected(false);
        setTimeout(() => { if (examStarted && !examSubmitted) connect(); }, 2000);
      };
      const ping = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping'); }, 10000);
      ws.addEventListener('close', () => clearInterval(ping));
      viewerWsRef.current = ws;
    };
    connect();

    return () => {
      viewerWsRef.current?.close();
    };
  }, [examStarted, user]);

  const addViolation = (type) => {
    violationTypesRef.current.push(type);
    setViolations(prev => {
      const next = prev + 1;
      
      // Compute Risk Logic locally (since WASM replaced Backend AI)
      const newScore = Math.min(100, next * 15);
      setRiskScore(newScore);
      setRiskLevel(newScore >= 60 ? 'High' : newScore >= 30 ? 'Medium' : 'Low');

      if (next === 5) setShowWarning(true);
      if (next === 8) { setShowWarning(false); setShowPause(true); }
      if (next >= 12) { setShowPause(false); setExamTerminated(true); handleSubmit(true); }
      return next;
    });
  };

  // ── Submit ──────────────────────────────────────────────────────────────────
  const handleSubmit = async (terminated = false) => {
    if (examSubmitted) return;
    setExamSubmitted(true);
    clearInterval(timerRef.current);
    if (analysisRef.current) cancelAnimationFrame(analysisRef.current);
    viewerWsRef.current?.close();

    const procData = {
      violations,
      total_violations: violations,
      violation_types: [...new Set(violationTypesRef.current)],
      tab_switches: tabSwitches,
      risk_level: riskLevel,
      risk_score: riskScore,
      events,
    };

    try {
      const result = await examAPI.submitExam({
        answers,
        time_used: EXAM_DURATION - timeLeft,
        proctoring_data: procData,
        coding_scores: codingScores,
      });
      result.proctoring_summary = procData;
      localStorage.setItem('mm_exam_result', JSON.stringify(result));
    } catch {
      const correct = answers.filter((a, i) => a !== -1 && questions[i] && a === (FALLBACK_QUESTIONS[i]?.correct ?? -99)).length;
      const localResult = {
        score: Math.round((correct / questions.length) * 100),
        correct,
        questions_total: questions.length,
        questions_answered: answers.filter(a => a !== -1).length,
        time_used: EXAM_DURATION - timeLeft,
        terminated,
        proctoring_summary: procData,
      };
      localStorage.setItem('mm_exam_result', JSON.stringify(localResult));
    }
    navigate('/score');
  };

  const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  const timerColor = timeLeft <= 60 ? 'var(--danger)' : timeLeft <= 180 ? 'var(--warning)' : 'var(--accent)';
  const letters = ['A', 'B', 'C', 'D'];
  const q = questions[currentQ];

  // Risk level colour
  const riskColor = riskLevel === 'Cheating' ? 'var(--danger)' : riskLevel === 'High Risk' ? '#ff6b35' : riskLevel === 'Suspicious' ? 'var(--warning)' : 'var(--success)';
  // Attention colour
  const attColor = attentionStatus === 'Away' ? 'var(--danger)' : attentionStatus === 'Distracted' ? 'var(--warning)' : 'var(--success)';
  const attIcon = attentionStatus === 'Focused' ? '🎯' : attentionStatus === 'Distracted' ? '👀' : '🚫';

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

      {/* Step 1: Camera */}
      {step === 'camera' && (
        <div className="setup-overlay">
          <div className="setup-card">
            <div className="setup-icon">📹</div>
            <h2>Enable Camera</h2>
            <p>MindMesh needs your webcam for AI proctoring. Your video is analyzed on the server for face detection and object detection. It is never recorded or stored.</p>
            {cameraError && (
              <div className="alert alert-error" style={{ marginBottom: 14, fontSize: 12 }}>
                {cameraError}
              </div>
            )}
            <button className="btn btn-primary btn-lg" onClick={startCamera}>
              🔓 Enable Camera & Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Identity */}
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

      {/* Step 3: QR Code */}
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

      {showSubmitModal && (
        <div className="warn-overlay blocking">
          <div className="warn-card">
            <div style={{ fontSize: 40, marginBottom: 12 }}>📤</div>
            <h2 style={{ marginBottom: 8 }}>Submit Exam?</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
              Answered <strong>{answers.filter(a => a !== -1).length}</strong> of <strong>{questions.length}</strong> questions. This cannot be undone.
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

                {/* ── Debug overlay — head pose & gaze ── */}


                {/* ── Real-time warning banners over camera ── */}
                {warningBanners.length > 0 && (
                  <div style={{
                    position: 'absolute', bottom: 28, left: 4, right: 4,
                    display: 'flex', flexDirection: 'column', gap: 4, zIndex: 10,
                  }}>
                    {warningBanners.map((msg, i) => (
                      <div key={i} style={{
                        background: 'rgba(239, 68, 68, 0.92)',
                        color: '#fff',
                        fontSize: 11,
                        fontWeight: 700,
                        padding: '5px 10px',
                        borderRadius: 6,
                        textAlign: 'center',
                        backdropFilter: 'blur(4px)',
                        animation: 'fadeIn 0.3s ease',
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

            {/* Stats — enhanced with risk score + attention */}
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
              <h2>📝 Demo Assessment — {user?.name}</h2>
              <div className="timer" style={{ color: timerColor }}>{fmtTime(timeLeft)}</div>
            </div>

            {/* Question or Coding area */}
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
            </div>

            {/* Nav bar */}
            <div className="question-nav">
              <div className="q-dots">
                {questions.map((_, i) => (
                  <span
                    key={i}
                    className={`q-dot ${questions[i]?.type === 'coding' ? 'coding-dot' : ''} ${i === currentQ ? 'current' : ''} ${answers[i] !== -1 ? 'answered' : ''}`}
                    onClick={() => examStarted && setCurrentQ(i)}
                  >
                    {i + 1}
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
