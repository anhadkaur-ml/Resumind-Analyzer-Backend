from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("interviews", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="interviewsession",
            name="question_source",
            field=models.CharField(default="fallback", max_length=20),
        ),
        migrations.AddField(
            model_name="interviewanswer",
            name="evaluation_source",
            field=models.CharField(default="local", max_length=20),
        ),
    ]
