from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Camera(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()  # This will store IPv4 or IPv6 addresses

    def __str__(self):
        return self.name


class Recording(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    video_file = models.FileField(upload_to='recordings/')


    def __str__(self):
        return f"Recording for {self.camera.name} at {self.timestamp}"

