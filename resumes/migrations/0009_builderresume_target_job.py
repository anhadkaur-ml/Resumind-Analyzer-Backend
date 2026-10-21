from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("resumes", "0008_careerconversation_careermessage")]

    operations = [
        migrations.AddField(
            model_name="builderresume",
            name="target_company",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="builderresume",
            name="job_description",
            field=models.TextField(blank=True),
        ),
    ]
