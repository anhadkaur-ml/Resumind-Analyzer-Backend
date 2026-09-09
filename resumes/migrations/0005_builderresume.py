from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Create persistent, employee-owned Resume Builder records."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("resumes", "0004_chatconversation_chatmessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="BuilderResume",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Untitled Resume", max_length=180)),
                ("target_role", models.CharField(blank=True, max_length=180)),
                ("template", models.CharField(default="Modern ATS", max_length=80)),
                ("status", models.CharField(choices=[("Draft", "Draft"), ("Completed", "Completed")], default="Draft", max_length=20)),
                ("completion", models.PositiveSmallIntegerField(default=0)),
                ("full_name", models.CharField(blank=True, max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("summary", models.TextField(blank=True)),
                ("job_title", models.CharField(blank=True, max_length=180)),
                ("company", models.CharField(blank=True, max_length=180)),
                ("period", models.CharField(blank=True, max_length=120)),
                ("experience", models.TextField(blank=True)),
                ("education", models.TextField(blank=True)),
                ("skills", models.TextField(blank=True)),
                ("projects", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="builder_resumes", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
    ]
