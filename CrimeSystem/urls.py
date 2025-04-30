"""
URL configuration for CrimeSystem project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from Crime.views import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('accounts/login/', login_view), 
    path('signup/',signup_view, name='signup'),
    path('',home_view, name='home'),
    path('logout/', custom_logout_view, name='logout'),
    path('video_feed/<int:camera_id>/', video_feed, name='video_feed'),
 

    path('admin-login/', admin_login_view, name='admin_login'),
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin-logout/', admin_logout_view, name='admin_logout'),  # For video feed (if applicable)
    
    path('delete-user/<int:user_id>/', delete_user, name='delete_user'),
    path('add-camera/', add_camera, name='add_camera'),
    path('delete-camera/<int:camera_id>/', delete_camera, name='delete_camera'),
    path('delete-recording/<int:recording_id>/', delete_recording, name='delete_recording'),
]
