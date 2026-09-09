from django.db import migrations, models


class Migration(migrations.Migration):
    """Add structured Education and Skills collections to Resume Builder."""

    dependencies = [
        ("resumes", "0005_builderresume"),
    ]

    operations = [
        migrations.AddField(
            model_name="builderresume",
            name="education_entries",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="builderresume",
            name="skill_items",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
