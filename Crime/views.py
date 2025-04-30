from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.http import HttpResponseForbidden
from .models import Recording, Camera
import cv2 

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

@login_required
@never_cache
def home_view(request):
    cameras = Camera.objects.all()  # Get all cameras from the database
    user_profile = None
    try:
        user_profile = request.user.userprofile
    except:
        pass  # profile might not exist if not set up

    context = {
        'user': request.user,
        'profile': user_profile,
        'cameras': cameras,
    }
    return render(request, 'Homepage.html', context)

def custom_logout_view(request):
    logout(request)  # Logs out the user
    request.session.flush()
    return redirect('login')

def gen_frames(ip_url):
    print(f"Streaming from: {ip_url}")  # Add this to debug in console
    cap = cv2.VideoCapture(ip_url)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@login_required
def video_feed(request, camera_id):
    try:
        camera = Camera.objects.get(id=camera_id)
        ip_url = f"http://{camera.ip_address}:8080/video"  # Make sure this endpoint works
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
@user_passes_test(is_admin)
def add_camera(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        ip_address = request.POST.get('ip_address')

        # Save camera with logged-in user
        Camera.objects.create(
            name=name,
            location=location,
            ip_address=ip_address,
            added_by=request.user
        )
        return redirect('admin_dashboard')

    return render(request, 'add_camera.html')

# Delete Camera
@login_required
@user_passes_test(is_admin)
def delete_camera(request, camera_id):
    if request.method == 'POST':  # Use POST instead of DELETE for simplicity with forms
        camera = get_object_or_404(Camera, id=camera_id)
        if request.user != camera.added_by and not request.user.is_superuser:
            return HttpResponseForbidden("You do not have permission to delete this camera.")
        camera.delete()
        return redirect('admin_dashboard')  # Redirect to dashboard after deletion
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