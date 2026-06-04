from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny

from .serializers import QnALogSerializer, SearchLogSerializer, ViewLogSerializer
from .services import request_user_or_none


class SearchLogCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = SearchLogSerializer

    def perform_create(self, serializer):
        serializer.save(user=request_user_or_none(self.request))


class ViewLogCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = ViewLogSerializer

    def perform_create(self, serializer):
        serializer.save(user=request_user_or_none(self.request))


class QnALogCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = QnALogSerializer

    def perform_create(self, serializer):
        serializer.save(user=request_user_or_none(self.request))
