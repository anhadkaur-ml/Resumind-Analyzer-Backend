from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("resumes", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="resumeanalysis",
            name="detailed_report",
            field=models.JSONField(default=dict),
        ),
    ]
