from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InterviewAnswer, InterviewSession
from .serializers import InterviewAnswerRequestSerializer, InterviewSessionSerializer
from .service import QuestionGenerationError, build_resume_context, evaluate_answer, generate_questions
from resumes.models import BuilderResume
from accounts.email_service import send_interview_result_email


def complete_session(session, message=None):
    """Close a session and calculate its score from saved answers, including skips."""
    # Result statistics are calculated from persisted answers so refreshing the
    # frontend cannot change or lose the final interview result.
    answers = list(session.answers.all())
    scores = [answer.score for answer in answers]
    skipped = sum(1 for answer in answers if not answer.answer.strip())
    answered = len(answers) - skipped
    total = len(session.questions)
    completion_score = round((answered / total) * 100) if total else 0
    # Quality measures answer strength, while completion separately shows how
    # much of the interview the candidate attempted.
    strong_answers = sum(1 for score in scores if score >= 75)
    quality_score = round(sum(scores) / len(scores)) if scores else 0
    strongest = sorted((answer for answer in answers if answer.answer.strip()), key=lambda answer: answer.score, reverse=True)[:3]
    weakest = sorted((answer for answer in answers if answer.answer.strip()), key=lambda answer: answer.score)[:3]
    session.status = InterviewSession.Status.COMPLETED
    session.overall_score = quality_score
    session.final_feedback = message or "Review the feedback for each answer, then repeat the questions using clearer examples and measurable outcomes."
    session.result_summary = {
        "category_scores": {"answer_quality": quality_score, "completion": completion_score, "confidence": min(100, quality_score + (5 if strong_answers >= 3 else 0))},
        "strengths": ([f"Strong response: {answer.question}" for answer in strongest if answer.score >= 70] or ["You completed the practice session and created a baseline for improvement."]) + (["You attempted every question."] if skipped == 0 and answered == total else []),
        "improvements": ([f"Rework this response: {answer.question}" for answer in weakest if answer.score < 75] or ["Keep answers concise while preserving the strongest evidence."]) + ([f"Revisit the {skipped} skipped question{'s' if skipped != 1 else ''}." ] if skipped else []),
        "recommendations": ["Use the STAR structure: Situation, Task, Action and Result.", "Repeat weaker answers aloud before your next session.", "Connect each example directly to the target role."],
        "answered_count": answered, "skipped_count": skipped, "total_questions": total,
    }
    session.completed_at = timezone.now()
    # Save before sending the optional email so its link always points to an
    # already-completed result, even when delivery is immediate.
    session.save()
    send_interview_result_email(session)


class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "employee"


class InterviewSessionListCreateView(generics.ListCreateAPIView):
    serializer_class = InterviewSessionSerializer
    permission_classes = (IsEmployee,)

    def get_queryset(self):
        # Never expose another employee's practice sessions in history.
        return InterviewSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        data = serializer.validated_data
        # question_count is an input control, while the generated list is saved.
        count = data.pop("question_count", 10)
        resume_id = data.pop("builder_resume_id", None)
        builder_resume = None
        resume_context = ""
        if resume_id:
            # Only a completed resume owned by this employee can become prompt context.
            builder_resume = get_object_or_404(BuilderResume, pk=resume_id, user=self.request.user, status=BuilderResume.Status.COMPLETED)
            resume_context = build_resume_context(builder_resume)
        # Question generation receives resume text only as optional prompt
        # context; the original Builder resume is never modified.
        try:
            questions, source = generate_questions(data["interview_type"], data["target_role"], data["experience_level"], count=count, resume_context=resume_context)
        except QuestionGenerationError as error:
            # A retryable provider failure must not create an unusable session.
            from rest_framework.exceptions import APIException

            unavailable = APIException(str(error))
            unavailable.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            raise unavailable from error
        serializer.save(user=self.request.user, builder_resume=builder_resume, questions=questions, question_source=source)


class InterviewSessionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = InterviewSessionSerializer
    permission_classes = (IsEmployee,)

    def get_queryset(self):
        # Ownership filtering also protects retrieve and delete operations.
        return InterviewSession.objects.filter(user=self.request.user)


class InterviewAnswerView(APIView):
    permission_classes = (IsEmployee,)

    def post(self, request, pk):
        # Looking up by both primary key and user prevents ID-based access to a
        # different employee's interview.
        session = get_object_or_404(InterviewSession, pk=pk, user=request.user)
        if session.status == InterviewSession.Status.COMPLETED:
            return Response({"detail": "This interview is already completed."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = InterviewAnswerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = session.questions[session.current_index]
        answer = serializer.validated_data["answer"]
        # The evaluator may use Groq, but always returns a normalized score,
        # feedback, and source before this answer is stored.
        score, feedback, source = evaluate_answer(question, answer, session.interview_type, session.target_role)
        InterviewAnswer.objects.create(session=session, question_index=session.current_index, question=question, answer=answer, score=score, feedback=feedback, evaluation_source=source)
        session.current_index += 1
        # Completing the final answer immediately creates the saved result.
        if session.current_index >= len(session.questions):
            complete_session(session)
        session.save()
        return Response(InterviewSessionSerializer(session).data)


class InterviewSkipView(APIView):
    """Record the current question as skipped and move to the next question."""
    permission_classes = (IsEmployee,)

    def post(self, request, pk):
        session = get_object_or_404(InterviewSession, pk=pk, user=request.user)
        if session.status == InterviewSession.Status.COMPLETED:
            return Response({"detail": "This interview is already completed."}, status=status.HTTP_400_BAD_REQUEST)
        question = session.questions[session.current_index]
        # A skipped question is stored as a zero-score answer so progress and
        # completion statistics remain accurate.
        InterviewAnswer.objects.create(session=session, question_index=session.current_index, question=question, answer="", score=0, feedback="This question was skipped.", evaluation_source="local")
        session.current_index += 1
        if session.current_index >= len(session.questions):
            complete_session(session)
        session.save()
        return Response(InterviewSessionSerializer(session).data)


class InterviewEndView(APIView):
    """Finish an interview early while preserving all answers already submitted."""
    permission_classes = (IsEmployee,)

    def post(self, request, pk):
        session = get_object_or_404(InterviewSession, pk=pk, user=request.user)
        if session.status != InterviewSession.Status.COMPLETED:
            # Ending early preserves submitted answers and produces a partial
            # result instead of deleting the session.
            complete_session(session, "This session was ended early. Review your submitted answers and start another session when you are ready.")
            session.save()
        return Response(InterviewSessionSerializer(session).data)
