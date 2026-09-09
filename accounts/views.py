from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import LoginSerializer, NotificationSerializer, SignupSerializer, UserProfileSerializer


class SignupView(APIView):
    """Public endpoint used to create an employee or HR account."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Account created successfully.",
                "user": {
                    "id": user.id,
                    "full_name": user.get_full_name() or user.username,
                    "email": user.email,
                    "role": user.role,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Public endpoint that returns JWT tokens after valid authentication."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class ProfileView(APIView):
    """Return the profile associated with the authenticated JWT user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationListView(APIView):
    """Return the current user's latest notifications and unread total."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # User filtering prevents notifications from leaking between accounts.
        notifications = Notification.objects.filter(user=request.user)[:30]
        return Response({
            "unread_count": Notification.objects.filter(user=request.user, is_read=False).count(),
            "results": NotificationSerializer(notifications, many=True).data,
        })


class NotificationReadView(APIView):
    """Mark one user-owned notification as read."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        # Include the user in the lookup so IDs cannot access other accounts.
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if notification is None:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    """Mark every unread notification for the current user as read."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"message": "All notifications marked as read."})
