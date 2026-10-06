from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("interviews", "0003_interviewsession_result_summary"),
        ("resumes", "0007_builderresume_project_entries"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewsession",
            name="builder_resume",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="interview_sessions", to="resumes.builderresume"),
        ),
    ]
