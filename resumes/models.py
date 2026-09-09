from django.conf import settings
from django.db import models


class ResumeAnalysis(models.Model):
    """Persist an uploaded resume and the complete result of one AI analysis."""

    # Ownership is required for every list, detail, download, and AI query.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_analyses")
    # Django stores the file under MEDIA_ROOT using a year/month directory.
    resume_file = models.FileField(upload_to="resumes/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    job_title = models.CharField(max_length=180)
    job_description = models.TextField(blank=True)
    overall_score = models.PositiveSmallIntegerField()
    impact_score = models.PositiveSmallIntegerField()
    clarity_score = models.PositiveSmallIntegerField()
    ats_score = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=30)
    # JSON fields preserve structured AI output without extra report tables.
    recommendations = models.JSONField(default=list)
    detailed_report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Analysis history displays the most recent report first.
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.original_filename} — {self.overall_score}/100"


class ResumeVersion(models.Model):
    """Store a reusable resume document separately from analysis reports."""

    class Category(models.TextChoices):
        PRIMARY = "primary", "Primary"
        TAILORED = "tailored", "Tailored"
        ORIGINAL = "original", "Original"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_versions")
    resume_file = models.FileField(upload_to="resume_versions/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    title = models.CharField(max_length=180)
    target_role = models.CharField(max_length=180, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.TAILORED)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Recently edited resume versions appear first.
        ordering = ("-updated_at",)

    def __str__(self):
        return self.title


class BuilderResume(models.Model):
    """Store editable Resume Builder content for one employee."""

    class Status(models.TextChoices):
        DRAFT = "Draft", "Draft"
        COMPLETED = "Completed", "Completed"

    # Builder records are private and are always queried through their owner.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="builder_resumes")
    title = models.CharField(max_length=180, default="Untitled Resume")
    target_role = models.CharField(max_length=180, blank=True)
    template = models.CharField(max_length=80, default="Modern ATS")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    completion = models.PositiveSmallIntegerField(default=0)
    full_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=180, blank=True)
    summary = models.TextField(blank=True)
    job_title = models.CharField(max_length=180, blank=True)
    company = models.CharField(max_length=180, blank=True)
    period = models.CharField(max_length=120, blank=True)
    experience = models.TextField(blank=True)
    # Structured collections let the builder add multiple education records
    # and individual skills without storing them as one uneditable paragraph.
    education_entries = models.JSONField(default=list, blank=True)
    skill_items = models.JSONField(default=list, blank=True)
    education = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    project_entries = models.JSONField(default=list, blank=True)
    projects = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.title


class ChatConversation(models.Model):
    """One permanent AI-coach conversation for one employee report."""

    # Saving both user and analysis makes ownership explicit and keeps each
    # resume report connected to one independent conversation.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_chat_conversations")
    analysis = models.OneToOneField(ResumeAnalysis, on_delete=models.CASCADE, related_name="chat_conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"{self.user} — {self.analysis.original_filename}"


class ChatMessage(models.Model):
    """A saved user or assistant message belonging to a report conversation."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    # Deleting a conversation or its analysis also removes its saved messages.
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
