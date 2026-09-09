from django.urls import path

from .views import AskAIHistoryView, AskAIView, BuilderProfessionalSummaryView, BuilderResumeDetailView, BuilderResumeListCreateView, ResumeAnalysisDetailView, ResumeAnalysisDownloadView, ResumeAnalysisListCreateView, ResumeDashboardView, ResumeVersionDetailView, ResumeVersionDownloadView, ResumeVersionListCreateView

app_name = "resumes"

urlpatterns = [
    # Resume analysis history, creation, report detail, and original download.
    path("analyses/", ResumeAnalysisListCreateView.as_view(), name="analysis-list-create"),
    path("analyses/<int:pk>/", ResumeAnalysisDetailView.as_view(), name="analysis-detail"),
    path("analyses/<int:pk>/download/", ResumeAnalysisDownloadView.as_view(), name="analysis-download"),
    # Overview statistics and report-aware AI coaching.
    path("dashboard/", ResumeDashboardView.as_view(), name="dashboard"),
    path("ask-ai/", AskAIView.as_view(), name="ask-ai"),
    # GET restores one report's chat; DELETE clears that saved conversation.
    path("ask-ai/history/<int:analysis_id>/", AskAIHistoryView.as_view(), name="ask-ai-history"),

    # Reusable resume-version CRUD and download endpoints.
    path("versions/", ResumeVersionListCreateView.as_view(), name="version-list-create"),
    path("versions/<int:pk>/", ResumeVersionDetailView.as_view(), name="version-detail"),
    path("versions/<int:pk>/download/", ResumeVersionDownloadView.as_view(), name="version-download"),

    # Resume Builder drafts and generated resume content.
    path("builder/", BuilderResumeListCreateView.as_view(), name="builder-list-create"),
    path("builder/<int:pk>/", BuilderResumeDetailView.as_view(), name="builder-detail"),
    path("builder/generate-professional-summary/", BuilderProfessionalSummaryView.as_view(), name="builder-professional-summary"),
]
