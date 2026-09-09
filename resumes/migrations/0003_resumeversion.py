import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("resumes", "0002_resumeanalysis_detailed_report")]
    operations = [
        migrations.CreateModel(
            name="ResumeVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resume_file", models.FileField(upload_to="resume_versions/%Y/%m/")),
                ("original_filename", models.CharField(max_length=255)),
                ("title", models.CharField(max_length=180)),
                ("target_role", models.CharField(blank=True, max_length=180)),
                ("category", models.CharField(choices=[("primary", "Primary"), ("tailored", "Tailored"), ("original", "Original")], default="tailored", max_length=20)),
                ("score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resume_versions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        )
    ]
