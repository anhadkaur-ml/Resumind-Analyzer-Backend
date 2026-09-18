from django.conf import settings
from django.db import models


class InterviewSession(models.Model):
    """A user-owned practice interview and its generated questions."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interview_sessions")
    interview_type = models.CharField(max_length=30)
    target_role = models.CharField(max_length=160)
    experience_level = models.CharField(max_length=80)
    questions = models.JSONField(default=list)
    question_source = models.CharField(max_length=20, default="fallback")
    current_index = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    final_feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Structured result data powers the detailed post-interview dashboard.
    result_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)


class InterviewAnswer(models.Model):
    """One saved answer and the feedback produced for it."""

    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="answers")
    question_index = models.PositiveIntegerField()
    question = models.TextField()
    answer = models.TextField()
    score = models.PositiveSmallIntegerField()
    feedback = models.TextField()
    evaluation_source = models.CharField(max_length=20, default="local")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("question_index",)
        constraints = [models.UniqueConstraint(fields=("session", "question_index"), name="unique_interview_answer")]
