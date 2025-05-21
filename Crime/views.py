from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import StreamingHttpResponse, JsonResponse, HttpResponseForbidden
from .models import Recording, Camera, Alert
import cv2 
import os
import time
from ultralytics import YOLO
import threading
from django.utils import timezone
from django.utils.timezone import localtime
from datetime import timedelta

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')  # redirect to your home page
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'login.html')


def signup_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('signup')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        messages.success(request, "Account created successfully. Please log in.")
        return redirect('login')
    return render(request,'signup.html')


def get_recent_and_today_alerts(user):
    today = timezone.now().date()
    cameras = Camera.objects.filter(added_by=user)
    alerts_today_qs = Alert.objects.filter(camera__in=cameras, timestamp__date=today)
    alerts_today = alerts_today_qs.count()
    recent_alerts = (
        alerts_today_qs.order_by('-timestamp')[:20]
    )
    # Group by (type, camera, location), keep up to 3 per group
    grouped = {}
    for alert in recent_alerts:
        key = (alert.type, alert.camera.name, alert.camera.location)
        grouped.setdefault(key, []).append(alert)
    flat_alerts = []
    for alerts in grouped.values():
        flat_alerts.extend(alerts[:3])
    flat_alerts = sorted(flat_alerts, key=lambda a: a.timestamp, reverse=True)[:3]
    return flat_alerts, alerts_today


@login_required
@never_cache
def home_view(request):
    cameras = Camera.objects.filter(added_by=request.user)  # Only user's cameras
    user_profile = None
    try:
        user_profile = request.user.userprofile
    except:
        pass  # profile might not exist if not set up

    recent_alerts, alerts_today = get_recent_and_today_alerts(request.user)
    
    context = {
        'user': request.user,
        'profile': user_profile,
        'cameras': cameras,
        'recent_alerts': recent_alerts,   # Add to context
        'alerts_today': alerts_today,     # Add to context
    }
    return render(request, 'Homepage.html', context)

def custom_logout_view(request):
    logout(request)  # Logs out the user
    request.session.flush()
    return redirect('login')


# === Model cache ===
model_cache = {}

MODEL_PATHS = {
    "best": r"D:\Prathamesh\Django Projects\CrimeSystem\Crime\models\best.pt",
    "best_Pranav": r"D:\Prathamesh\Django Projects\CrimeSystem\Crime\models\best_Pranav.pt"
}

def load_model(model_key):
    if model_key not in model_cache:
        path = MODEL_PATHS.get(model_key)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Model '{model_key}' not found at: {path}")
        model_cache[model_key] = YOLO(path)
        print(f"[INFO] Loaded model: {model_key}")
    return model_cache[model_key]

# === Threaded Video Stream Class ===
class VideoStream:
    def __init__(self, url):
        self.stream = cv2.VideoCapture(url)
        if not self.stream.isOpened():
            raise ValueError(f"Unable to open video stream: {url}")

        # Optional: set resolution for performance
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.stopped = False
        self.read_lock = threading.Lock()
        self.frame = None

        # Start background thread
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while not self.stopped:
            if self.stream.isOpened():
                grabbed, frame = self.stream.read()
                if grabbed:
                    with self.read_lock:
                        self.frame = frame
            time.sleep(0.01)

    def read(self):
        with self.read_lock:
            if self.frame is not None:
                return True, self.frame.copy()
            return False, None

    def release(self):
        self.stopped = True
        self.thread.join()
        self.stream.release()

# === Frame Generator ===
def gen_frames(ip_url):
    print(f"[INFO] Connecting to stream at: {ip_url}")
    try:
        stream = VideoStream(ip_url)
    except ValueError as e:
        print("[ERROR] Stream connection failed:", str(e))
        return

    model1 = load_model("best")
    model2 = load_model("best_Pranav")

    while True:
        success, frame = stream.read()
        if not success or frame is None:
            print("[WARNING] Frame not ready.")
            continue  # Try next frame

        try:
            # === Run YOLO inference ===
            results1 = model1(frame, verbose=False)[0]
            results2 = model2(frame, verbose=False)[0]

            # === Draw bounding boxes ===
            for box in results1.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = f"[{model1.model.names[cls_id]} | M1 | {conf:.2f}]"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            for box in results2.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = f"[{model2.model.names[cls_id]} | M2 | {conf:.2f}]"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                if conf > 0.7:
                    try:
                        ip = ip_url.split("//")[1].split(":")[0]
                        camera = Camera.objects.get(ip_address=ip)
                        now = timezone.now()
                        detected_type = model2.model.names[cls_id]
                        if detected_type.lower() == "weapon":  # Adjust to your class name
                            # Count weapon detections in last 30 seconds
                            recent_count = Alert.objects.filter(
                                camera=camera,
                                type=detected_type,
                                timestamp__gte=now - timedelta(seconds=30)
                            ).count()
                            # Every 3rd detection triggers alert (rolling window)
                            if (recent_count + 1) % 3 == 0:
                                Alert.objects.create(
                                    camera=camera,
                                    type=detected_type,
                                    timestamp=now,
                                )
                        else:
                            # Usual alert logic for other types
                            recent = Alert.objects.filter(
                                camera=camera,
                                type=detected_type,
                                timestamp__gte=now - timedelta(seconds=30)
                            )
                            if not recent.exists():
                                Alert.objects.create(
                                    camera=camera,
                                    type=detected_type,
                                    timestamp=now,
                                )
                    except Camera.DoesNotExist:
                        print(f"[ERROR] Camera with IP {ip} not found.")
                    except Exception as e:
                        print(f"[ERROR] Alert creation failed: {e}")

        except Exception as e:
            print(f"[ERROR] YOLO detection failed: {e}")

        # === Encode JPEG and yield ===
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            print("[ERROR] JPEG encoding failed.")
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    stream.release()
    print("[INFO] Stream released.")
    
@never_cache
@login_required
def latest_alerts(request):
    recent_alerts, alerts_today = get_recent_and_today_alerts(request.user)
    data = [{
        'type': alert.type,
        'camera': alert.camera.name,
        'location': alert.camera.location,
        # Convert to local time and format as HH:MM:SS
        'timestamp': localtime(alert.timestamp).strftime('%H:%M:%S'),
    } for alert in recent_alerts]
    return JsonResponse({'alerts': data, 'alerts_today': alerts_today})

# === Django Streaming View ===
def video_feed(request, camera_id):
    try:
        camera = Camera.objects.get(id=camera_id)
        ip_url = f"http://{camera.ip_address}:8080/video"
        return StreamingHttpResponse(gen_frames(ip_url),
                                     content_type='multipart/x-mixed-replace; boundary=frame')
    except Camera.DoesNotExist:
        return StreamingHttpResponse("Camera not found", status=404)
    
    
# Check if user is admin
def is_admin(user):
    return user.is_staff

# Admin Login View
def admin_login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "User does not exist.")
            return redirect('admin_login')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if user is staff
            if user.is_staff:
                login(request, user)
                return redirect('admin_dashboard')
            else:
                messages.error(request, "Invalid admin credentials. You are not authorized.")
                return redirect('admin_login')
        else:
            messages.error(request, "Incorrect password.")
            return redirect('admin_login')
    
    return render(request, 'admin_login.html')

# Admin Logout
def admin_logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('admin_login')

# Admin Dashboard
@login_required
@never_cache
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    users = User.objects.all()
    cameras = Camera.objects.all()
    recordings = Recording.objects.all()
    return render(request, 'admin_dashboard.html', {
        'users': users,
        'cameras': cameras,
        'recordings': recordings,
    })
    

# Delete User
@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        # Prevent a user from deleting themselves unless they are a superuser
        if request.user.id == user_id and not request.user.is_superuser:
            return HttpResponseForbidden("You cannot delete your own account.")
        if not request.user.is_superuser and user.is_staff:
            return HttpResponseForbidden("You do not have permission to delete a staff user.")
        user.delete()
        return redirect('admin_dashboard')
    return HttpResponseForbidden("Invalid method.")

# Add Camera
@login_required
@never_cache
def add_camera(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        ip_address = request.POST.get('ip_address')

        camera = Camera.objects.create(
            name=name,
            location=location,
            ip_address=ip_address,
            added_by=request.user
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'camera': {
                    'id': camera.id,
                    'name': camera.name,
                    'ip_address': camera.ip_address,
                    'location': camera.location,
                    'added_by': camera.added_by.username
                }
            })
        return redirect('home')

    return render(request, 'add_camera.html')

@login_required
def delete_camera(request, camera_id):
    if request.method == 'POST':
        camera = get_object_or_404(Camera, id=camera_id)
        if request.user != camera.added_by:
            return HttpResponseForbidden("You do not have permission to delete this camera.")
        camera.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('home')
    return HttpResponseForbidden("Invalid method.")

# Delete Recording
@login_required
@user_passes_test(is_admin)
def delete_recording(request, recording_id):
    if request.method == 'POST':
        recording = get_object_or_404(Recording, id=recording_id)
        if request.user != recording.added_by and not request.user.is_superuser:  # Adjust added_by if applicable
            return HttpResponseForbidden("You do not have permission to delete this recording.")
        recording.delete()
        return redirect('admin_dashboard')
    return HttpResponseForbidden("Invalid method.")