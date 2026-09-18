from django.urls import path

from .views import InterviewAnswerView, InterviewEndView, InterviewSessionDetailView, InterviewSessionListCreateView, InterviewSkipView

urlpatterns = [
    path("sessions/", InterviewSessionListCreateView.as_view(), name="interview-sessions"),
    path("sessions/<int:pk>/", InterviewSessionDetailView.as_view(), name="interview-session-detail"),
    path("sessions/<int:pk>/answer/", InterviewAnswerView.as_view(), name="interview-answer"),
    path("sessions/<int:pk>/skip/", InterviewSkipView.as_view(), name="interview-skip"),
    path("sessions/<int:pk>/end/", InterviewEndView.as_view(), name="interview-end"),
]
