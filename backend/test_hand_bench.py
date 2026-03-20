"""Quick benchmark for hand detection latency."""
import time, statistics, numpy as np, cv2, base64
from app.ai.hand_face_detector import analyze_hands, warm_up

# Create test frame
frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
cv2.ellipse(frame, (320, 240), (80, 100), 0, 0, 360, (200, 180, 160), -1)
_, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
test_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buf).decode()

# Warm up
warm_up()
print('Warmed up')

# Benchmark
face_bbox = {'x1': 240, 'y1': 140, 'x2': 400, 'y2': 340}
times = []
for i in range(20):
    t0 = time.time()
    r = analyze_hands(test_b64, f'bench_{i%3}', face_bbox)
    elapsed = (time.time() - t0) * 1000
    times.append(elapsed)

avg = round(statistics.mean(times), 1)
p95 = round(sorted(times)[18], 1)
mx = round(max(times), 1)
mn = round(min(times), 1)
print(f'Hand Detection: avg={avg}ms | P95={p95}ms | min={mn}ms | max={mx}ms')
hands = r.get('hands_detected')
near = r.get('hand_near_face')
phone = r.get('phone_usage_suspected')
print(f'Last result: hands={hands}, near_face={near}, phone={phone}')
