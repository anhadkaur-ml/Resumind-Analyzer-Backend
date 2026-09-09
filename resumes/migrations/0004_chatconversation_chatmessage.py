from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    # This migration creates permanent, report-specific chatbot storage.
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("resumes", "0003_resumeversion"),
    ]

    operations = [
        # One conversation is linked to exactly one resume analysis.
        migrations.CreateModel(
            name="ChatConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("analysis", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="chat_conversation", to="resumes.resumeanalysis")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resume_chat_conversations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        # Each conversation contains ordered user and assistant messages.
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant")], max_length=20)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="resumes.chatconversation")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
    ]
