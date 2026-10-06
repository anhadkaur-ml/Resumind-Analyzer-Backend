from rest_framework import serializers

from .models import InterviewAnswer, InterviewSession


class InterviewAnswerSerializer(serializers.ModelSerializer):
    """Expose saved answers and their evaluation metadata as read-only data."""
    class Meta:
        model = InterviewAnswer
        fields = ("id", "question_index", "question", "answer", "score", "feedback", "evaluation_source", "created_at")


class InterviewSessionSerializer(serializers.ModelSerializer):
    """Validate interview setup input and return complete session progress."""
    answers = InterviewAnswerSerializer(many=True, read_only=True)
    # This setup-only value controls generation and is not stored separately;
    # the saved questions array remains the source of truth for session length.
    question_count = serializers.ChoiceField(choices=(5, 10, 15, 20), write_only=True, default=10)
    # Clients send a simple ID; the view performs the user-ownership check.
    resume_id = serializers.IntegerField(source="builder_resume_id", required=False, allow_null=True, min_value=1)
    resume_title = serializers.CharField(source="builder_resume.title", read_only=True, default="")

    class Meta:
        model = InterviewSession
        fields = ("id", "interview_type", "target_role", "experience_level", "resume_id", "resume_title", "question_count", "questions", "question_source", "current_index", "status", "overall_score", "final_feedback", "result_summary", "answers", "created_at", "completed_at")
        read_only_fields = ("questions", "question_source", "current_index", "status", "overall_score", "final_feedback", "result_summary", "answers")


class InterviewAnswerRequestSerializer(serializers.Serializer):
    """Validate one answer before sending it to the evaluator."""
    answer = serializers.CharField(min_length=2, max_length=8000, trim_whitespace=True)
