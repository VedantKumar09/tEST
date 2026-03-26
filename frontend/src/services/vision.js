import { FaceLandmarker, ObjectDetector, FilesetResolver } from "@mediapipe/tasks-vision";

let faceLandmarker = null;
let objectDetector = null;

export const initVision = async () => {
  if (faceLandmarker && objectDetector) {
    return { faceLandmarker, objectDetector };
  }
  
  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
  );

  const faceBaseOptions = {
    modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    delegate: "GPU"
  };
  const objectBaseOptions = {
    modelAssetPath: "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite2/float32/1/efficientdet_lite2.tflite",
    delegate: "GPU"
  };

  try {
    faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
      baseOptions: faceBaseOptions,
      runningMode: "VIDEO",
      numFaces: 2,
      minFaceDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });

    objectDetector = await ObjectDetector.createFromOptions(vision, {
      baseOptions: objectBaseOptions,
      runningMode: "VIDEO",
      scoreThreshold: 0.25
    });
  } catch {
    faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
      baseOptions: { ...faceBaseOptions, delegate: "CPU" },
      runningMode: "VIDEO",
      numFaces: 2,
      minFaceDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });

    objectDetector = await ObjectDetector.createFromOptions(vision, {
      baseOptions: { ...objectBaseOptions, delegate: "CPU" },
      runningMode: "VIDEO",
      scoreThreshold: 0.25
    });
  }

  return { faceLandmarker, objectDetector };
};

// Moving average histories
const SMOOTH_WINDOW = 15;
const history = {
  yaw: [], pitch: [], gaze: []
};

const getAvg = (arr) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

export const analyzeFaceGeometry = (landmarks, imgW, imgH) => {
  if (!landmarks || landmarks.length === 0) {
    return {
      face_detected: false, multiple_faces: false, no_face: true,
      head_pose: { yaw: 0, pitch: 0, looking_away: false },
      eye_gaze: { direction: 'unknown', ratio: 0.5, looking_offscreen: false }
    };
  }

  const faceCount = landmarks.length;
  const primary = landmarks[0]; // array of 478 points
  
  // Head Pose (Yaw / Pitch)
  const nose = primary[1];
  const chin = primary[152];
  const l_eye = primary[33];
  const r_eye = primary[263];

  const nose_x = nose.x * imgW, nose_y = nose.y * imgH;
  const chin_x = chin.x * imgW, chin_y = chin.y * imgH;
  const le_x = l_eye.x * imgW, le_y = l_eye.y * imgH;
  const re_x = r_eye.x * imgW, re_y = r_eye.y * imgH;

  const mid_x = (le_x + re_x) / 2;
  const mid_y = (le_y + re_y) / 2;

  const eye_dist = Math.sqrt(Math.pow(re_x - le_x, 2) + Math.pow(re_y - le_y, 2));
  
  let raw_yaw = 0, raw_pitch = 0;
  if (eye_dist >= 1) {
    const dx = nose_x - mid_x;
    raw_yaw = (Math.atan2(dx, eye_dist) * 180 / Math.PI) * 2;

    const face_height = chin_y - mid_y;
    if (face_height >= 1) {
      const nose_ratio = (nose_y - mid_y) / face_height;
      raw_pitch = (nose_ratio - 0.35) * 100;
    }
  }

  history.yaw.push(raw_yaw);
  history.pitch.push(raw_pitch);
  while(history.yaw.length > SMOOTH_WINDOW) history.yaw.shift();
  while(history.pitch.length > SMOOTH_WINDOW) history.pitch.shift();

  const yaw = getAvg(history.yaw);
  const pitch = getAvg(history.pitch);
  const looking_away = Math.abs(yaw) > 35 || Math.abs(pitch) > 30;

  // Eye Gaze
  let direction = "center";
  let looking_offscreen = false;
  let avg_ratio = 0.5;

  if (primary.length >= 473) {
    const _LEFT_IRIS = [468, 469, 470, 471, 472];
    const _RIGHT_IRIS = [473, 474, 475, 476, 477];
    
    const l_iris_x = (_LEFT_IRIS.reduce((sum, i) => sum + primary[i].x, 0) / 5) * imgW;
    const l_inner_x = primary[133].x * imgW;
    const l_outer_x = primary[33].x * imgW;
    const l_eye_width = Math.abs(l_inner_x - l_outer_x);
    const l_ratio = l_eye_width >= 1 ? (l_iris_x - l_outer_x) / (l_inner_x - l_outer_x + 1e-6) : 0.5;

    const r_iris_x = (_RIGHT_IRIS.reduce((sum, i) => sum + primary[i].x, 0) / 5) * imgW;
    const r_inner_x = primary[362].x * imgW;
    const r_outer_x = primary[263].x * imgW;
    const r_eye_width = Math.abs(r_outer_x - r_inner_x);
    const r_ratio = r_eye_width >= 1 ? (r_iris_x - r_inner_x) / (r_outer_x - r_inner_x + 1e-6) : 0.5;

    let raw_ratio = (l_ratio + r_ratio) / 2;
    raw_ratio = Math.max(0.0, Math.min(1.0, raw_ratio));

    history.gaze.push(raw_ratio);
    while (history.gaze.length > SMOOTH_WINDOW) history.gaze.shift();
    avg_ratio = getAvg(history.gaze);

    if (avg_ratio < 0.28) direction = "left";
    else if (avg_ratio > 0.72) direction = "right";
    else direction = "center";

    looking_offscreen = direction !== "center";
  }

  return {
    face_detected: true,
    face_count: faceCount,
    no_face: false,
    multiple_faces: faceCount > 1,
    head_pose: { yaw: parseFloat(yaw.toFixed(1)), pitch: parseFloat(pitch.toFixed(1)), looking_away },
    eye_gaze: { direction, ratio: parseFloat(avg_ratio.toFixed(3)), looking_offscreen }
  };
};
