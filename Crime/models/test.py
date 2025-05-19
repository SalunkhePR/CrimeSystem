import cv2
import time
import numpy as np
from ultralytics import YOLO
import torch
import mediapipe as mp

# Initialize models
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
yolo = YOLO(r'D:\Prathamesh\Django Projects\CrimeSystem\Crime\models\best.pt')
resnet = torch.hub.load('pytorch/vision', 'resnet18', pretrained=True).eval().to(device)
mp_pose = mp.solutions.pose.Pose(static_image_mode=False, min_detection_confidence=0.5)

# Initialize camera
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Lower resolution
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 15)

frame_count = 0
skip_frames = 2

def preprocess_frame(frame, target_size=(224, 224)):
    frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)
    frame = frame.astype(np.float32) / 255.0
    frame = np.transpose(frame, (2, 0, 1))[np.newaxis, ...]
    return frame

while True:
    start_time = time.time()
    ret, frame = cap.read()
    if not ret:
        break
    capture_time = time.time() - start_time

    frame_count += 1
    if frame_count % skip_frames != 0:
        cv2.imshow('Output', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        continue

    # Preprocessing
    t2 = time.time()
    input_tensor = preprocess_frame(frame)
    input_tensor = torch.tensor(input_tensor).to(device)
    preprocess_time = time.time() - t2

    # Inference
    t3 = time.time()
    try:
        yolo_results = yolo(frame)  # YOLOv8 inference
    except RuntimeError as e:
        print(f"YOLO error: {e}")
        break
    with torch.no_grad():
        resnet_pred = resnet(input_tensor).argmax().item()
    pose_results = mp_pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    inference_time = time.time() - t3

    # Postprocessing
    t4 = time.time()
    for box in yolo_results[0].boxes.xyxy:
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    if pose_results.pose_landmarks:
        mp.solutions.drawing_utils.draw_landmarks(frame, pose_results.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS)
    cv2.putText(frame, f'Class: {resnet_pred}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow('Output', frame)
    postprocess_time = time.time() - t4

    # Log timings
    total_time = time.time() - start_time
    print(f"Capture: {capture_time:.3f}s, Preprocess: {preprocess_time:.3f}s, "
          f"Inference: {inference_time:.3f}s, Postprocess: {postprocess_time:.3f}s, "
          f"Total: {total_time:.3f}s, FPS: {1/total_time:.2f}")

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
mp_pose.close()