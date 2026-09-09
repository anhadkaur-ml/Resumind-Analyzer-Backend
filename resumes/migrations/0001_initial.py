import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="ResumeAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resume_file", models.FileField(upload_to="resumes/%Y/%m/")),
                ("original_filename", models.CharField(max_length=255)),
                ("job_title", models.CharField(max_length=180)),
                ("job_description", models.TextField(blank=True)),
                ("overall_score", models.PositiveSmallIntegerField()),
                ("impact_score", models.PositiveSmallIntegerField()),
                ("clarity_score", models.PositiveSmallIntegerField()),
                ("ats_score", models.PositiveSmallIntegerField()),
                ("status", models.CharField(max_length=30)),
                ("recommendations", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resume_analyses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        )
    ]
