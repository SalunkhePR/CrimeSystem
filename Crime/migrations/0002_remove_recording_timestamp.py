# Generated by Django 5.0.7 on 2025-04-14 18:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Crime', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='recording',
            name='timestamp',
        ),
    ]
