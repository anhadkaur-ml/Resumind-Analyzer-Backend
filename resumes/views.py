import json

from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BuilderResume, ChatConversation, ChatMessage, ResumeAnalysis, ResumeVersion
from .serializers import AskAIRequestSerializer, BuilderResumeSerializer, ChatMessageSerializer, ProfessionalSummaryRequestSerializer, ResumeAnalysisCreateSerializer, ResumeAnalysisSerializer, ResumeVersionCreateSerializer, ResumeVersionSerializer
from .service import ask_groq, generate_professional_summary


class IsEmployee(permissions.BasePermission):
    """Allow access only to authenticated users with the employee role."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "employee"


class ResumeAnalysisListCreateView(generics.ListCreateAPIView):
    """List the employee's reports or create a report from a multipart upload."""

    permission_classes = (IsEmployee,)
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Never expose another employee's analysis history.
        return ResumeAnalysis.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        # POST accepts upload fields; GET returns the complete saved result.
        return ResumeAnalysisCreateSerializer if self.request.method == "POST" else ResumeAnalysisSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis = serializer.save()
        return Response(ResumeAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)


class ResumeAnalysisDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete one report owned by the current employee."""

    permission_classes = (IsEmployee,)
    serializer_class = ResumeAnalysisSerializer

    def get_queryset(self):
        return ResumeAnalysis.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        # Deleting a database row does not automatically delete its media file.
        stored_file = instance.resume_file
        instance.delete()
        if stored_file:
            stored_file.delete(save=False)


class ResumeAnalysisDownloadView(APIView):
    """Stream the original resume file as an authenticated download."""

    permission_classes = (IsEmployee,)

    def get(self, request, pk):
        analysis = generics.get_object_or_404(ResumeAnalysis, pk=pk, user=request.user)
        return FileResponse(analysis.resume_file.open("rb"), as_attachment=True, filename=analysis.original_filename)


class ResumeVersionListCreateView(generics.ListCreateAPIView):
    """List or upload reusable resume versions owned by the employee."""

    permission_classes = (IsEmployee,)
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        return ResumeVersion.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return ResumeVersionCreateSerializer if self.request.method == "POST" else ResumeVersionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        return Response(ResumeVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class ResumeVersionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, edit, archive, or delete one owned resume version."""

    permission_classes = (IsEmployee,)
    serializer_class = ResumeVersionSerializer

    def get_queryset(self):
        return ResumeVersion.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        # Remove the physical upload after the database record is deleted.
        stored_file = instance.resume_file
        instance.delete()
        if stored_file:
            stored_file.delete(save=False)


class ResumeVersionDownloadView(APIView):
    """Download one employee-owned resume version."""

    permission_classes = (IsEmployee,)

    def get(self, request, pk):
        version = generics.get_object_or_404(ResumeVersion, pk=pk, user=request.user)
        return FileResponse(version.resume_file.open("rb"), as_attachment=True, filename=version.original_filename)


class BuilderResumeListCreateView(generics.ListCreateAPIView):
    """List the employee's builder resumes or create a new draft/completed resume."""

    permission_classes = (IsEmployee,)
    serializer_class = BuilderResumeSerializer

    def get_queryset(self):
        # Ownership filtering keeps every employee's builder workspace private.
        return BuilderResume.objects.filter(user=self.request.user)


class BuilderResumeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Load, update, or delete one employee-owned builder resume."""

    permission_classes = (IsEmployee,)
    serializer_class = BuilderResumeSerializer

    def get_queryset(self):
        return BuilderResume.objects.filter(user=self.request.user)


class BuilderProfessionalSummaryView(APIView):
    """Generate the Professional Summary section from current builder facts."""

    permission_classes = (IsEmployee,)

    def post(self, request):
        serializer = ProfessionalSummaryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        context = (
            f"Target role: {values.get('target_role') or 'Not specified'}\n"
            f"Skills: {', '.join(values.get('skills', [])) or 'Not specified'}\n"
            f"Experience: {values.get('experience') or 'Not specified'}\n"
            f"Projects: {values.get('projects') or 'Not specified'}\n"
            f"Current rough summary: {values.get('current_summary') or 'Not provided'}"
        )
        summary, provider = generate_professional_summary(context)
        if not summary:
            return Response(
                {"detail": "AI summary writing is temporarily unavailable. Check the Groq configuration and try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"summary": summary, "provider": provider})


class ResumeDashboardView(APIView):
    """Provide compact analysis statistics for the employee overview page."""

    permission_classes = (IsEmployee,)

    def get(self, request):
        analyses = ResumeAnalysis.objects.filter(user=request.user)
        latest = analyses.first()
        return Response({"analysis_count": analyses.count(), "latest": ResumeAnalysisSerializer(latest).data if latest else None})


class AskAIView(APIView):
    """Answer questions using only one employee-owned resume report."""

    permission_classes = (IsEmployee,)

    def post(self, request):
        # Validate that the request contains both a question and a report ID.
        serializer = AskAIRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Filter by both ID and user so an employee cannot ask questions about
        # another employee's private report. DRF returns 404 when it is not owned.
        analysis = generics.get_object_or_404(
            ResumeAnalysis,
            pk=serializer.validated_data["analysis_id"],
            user=request.user,
        )

        # Convert the selected report into plain text that Groq can understand.
        # This includes the scores and all detailed feedback generated earlier.
        context = (
            f"Report ID: {analysis.id}\n"
            f"Resume: {analysis.original_filename}\n"
            f"Target role: {analysis.job_title}\n"
            f"Job description: {analysis.job_description or 'Not provided'}\n"
            f"Status: {analysis.status}\n"
            f"Overall score: {analysis.overall_score}/100\n"
            f"Impact score: {analysis.impact_score}/100\n"
            f"Clarity score: {analysis.clarity_score}/100\n"
            f"ATS score: {analysis.ats_score}/100\n"
            f"Recommendations: {json.dumps(analysis.recommendations, ensure_ascii=False)}\n"
            f"Detailed report: {json.dumps(analysis.detailed_report, ensure_ascii=False)}"
        )[:20000]  # Limit context size to keep the AI request controlled.

        # Each report has its own saved conversation. Only the latest messages
        # are forwarded to keep follow-up answers useful and requests bounded.
        conversation, _ = ChatConversation.objects.get_or_create(user=request.user, analysis=analysis)
        history = list(conversation.messages.values("role", "content"))[-8:]

        # Save the question before requesting an answer so the user's message is
        # not lost if the provider is temporarily unavailable.
        ChatMessage.objects.create(conversation=conversation, role=ChatMessage.Role.USER, content=serializer.validated_data["question"])

        answer, provider = ask_groq(
            serializer.validated_data["question"],
            context,
            history,
        )

        # Save the returned response so reopening this report restores the chat.
        assistant_message = ChatMessage.objects.create(conversation=conversation, role=ChatMessage.Role.ASSISTANT, content=answer)

        # Returning the report identity lets the frontend confirm which resume
        # the response belongs to.
        return Response({"answer": answer, "provider": provider, "analysis_id": analysis.id, "resume": analysis.original_filename, "message": ChatMessageSerializer(assistant_message).data})


class AskAIHistoryView(APIView):
    """Load or clear the saved AI conversation for one employee-owned report."""

    permission_classes = (IsEmployee,)

    def get_analysis(self, request, analysis_id):
        # Ownership filtering protects report conversations from other users.
        return generics.get_object_or_404(ResumeAnalysis, pk=analysis_id, user=request.user)

    def get(self, request, analysis_id):
        analysis = self.get_analysis(request, analysis_id)
        conversation = ChatConversation.objects.filter(user=request.user, analysis=analysis).first()
        messages = conversation.messages.all() if conversation else ChatMessage.objects.none()
        return Response({"analysis_id": analysis.id, "resume": analysis.original_filename, "results": ChatMessageSerializer(messages, many=True).data})

    def delete(self, request, analysis_id):
        analysis = self.get_analysis(request, analysis_id)
        ChatConversation.objects.filter(user=request.user, analysis=analysis).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
