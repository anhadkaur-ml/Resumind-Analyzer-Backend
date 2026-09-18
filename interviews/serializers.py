from rest_framework import serializers

from .models import InterviewAnswer, InterviewSession


class InterviewAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewAnswer
        fields = ("id", "question_index", "question", "answer", "score", "feedback", "evaluation_source", "created_at")


class InterviewSessionSerializer(serializers.ModelSerializer):
    answers = InterviewAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = InterviewSession
        fields = ("id", "interview_type", "target_role", "experience_level", "questions", "question_source", "current_index", "status", "overall_score", "final_feedback", "result_summary", "answers", "created_at", "completed_at")
        read_only_fields = ("questions", "question_source", "current_index", "status", "overall_score", "final_feedback", "result_summary", "answers")


class InterviewAnswerRequestSerializer(serializers.Serializer):
    answer = serializers.CharField(min_length=2, max_length=8000, trim_whitespace=True)
