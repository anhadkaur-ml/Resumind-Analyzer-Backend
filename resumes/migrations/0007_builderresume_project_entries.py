from django.db import migrations, models


class Migration(migrations.Migration):
    """Add structured, repeatable project records to Resume Builder."""

    dependencies = [("resumes", "0006_builderresume_structured_education_skills")]

    operations = [
        migrations.AddField(
            model_name="builderresume",
            name="project_entries",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
