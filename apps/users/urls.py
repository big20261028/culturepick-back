from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("register/", views.register, name="register"),
    path("password/reset/request/", views.PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("account/recovery/", views.AccountRecoveryView.as_view(), name="account_recovery"),
    path("token/refresh/", views.CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("social/", views.social_login, name="social_login"),
    path("me/", views.MyProfileView.as_view(), name="my_profile"),
    path("me/password/verify/", views.MyPasswordVerificationView.as_view(), name="my_password_verify"),
    path("me/interests/", views.MyInterestPerformanceListView.as_view(), name="my_interest_performances"),
    path("me/watchlist/", views.MyWatchlistPerformanceListView.as_view(), name="my_watchlist_performances"),
    path("me/posts/", views.MyCommunityPostListView.as_view(), name="my_community_posts"),
]
