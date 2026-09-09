from django.urls import path

from .views import LoginView, NotificationListView, NotificationReadAllView, NotificationReadView, ProfileView, SignupView


app_name = "accounts"

urlpatterns = [
    # Authentication and current-user profile endpoints.
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),

    # Notification bell endpoints.
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/read-all/", NotificationReadAllView.as_view(), name="notifications-read-all"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
]
