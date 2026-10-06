from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_notification"),
    ]

    operations = [
        # Defaults preserve email delivery for existing accounts after migration.
        migrations.AddField(
            model_name="user",
            name="email_notifications_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="email_resume_analysis",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="email_resume_builder",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="email_interview_results",
            field=models.BooleanField(default=True),
        ),
    ]
