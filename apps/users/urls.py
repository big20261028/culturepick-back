from django.urls import path
from . import views
# from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('register/', views.register, name='register'),
    path('token/refresh/', views.CustomTokenRefreshView.as_view(), name='token_refresh'), #JWT 엑세스 토큰 재발급
]
