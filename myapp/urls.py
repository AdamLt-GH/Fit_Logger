from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('api/register/', views.RegisterView.as_view(), name='register'),
    path('api/login/', views.LoginView.as_view(), name='login'),
    path('api/logout/', views.LogoutView.as_view(), name='logout'),
    path('api/change-password/', views.ChangePasswordAPIView.as_view(), name='change_password'),
    path('api/password-reset/request/', views.PasswordResetRequestAPIView.as_view(), name='password_reset_request'),
    path('api/password-reset/confirm/', views.PasswordResetConfirmAPIView.as_view(), name='password_reset_confirm'),

    # Profile (needed by your Profile page)
    path('api/profile/me/', views.ProfileMeView.as_view(), name='profile_me'),


    # Dashboard
    path('api/dashboard/', views.DashboardAPIView.as_view(), name='dashboard'),

    # Challenges
    path('api/challenges/', views.PublicChallengeListAPIView.as_view(), name='challenge_list'),
    path('api/challenge/create/', views.ChallengeCreateAPIView.as_view(), name='challenge_create'),
    path('api/challenge/<int:challenge_id>/update/', views.ChallengeUpdateAPIView.as_view(), name='challenge_update'),
    path('api/challenge/<int:challenge_id>/delete/', views.ChallengeDeleteAPIView.as_view(), name='challenge_delete'),
    path('api/challenge/<int:challenge_id>/join/', views.JoinChallengeAPIView.as_view(), name='challenge_join'),
    path('api/challenge/<int:challenge_id>/leave/', views.LeaveChallengeAPIView.as_view(), name='challenge_leave'),

    # Progress
    path('api/progress/', views.ProgressEntryListAPIView.as_view(), name='progress_list'),
    path('api/progress/create/', views.ProgressEntryCreateAPIView.as_view(), name='progress_create'),
    path('api/progress/<int:challenge_id>/', views.ProgressEntryListAPIView.as_view(), name='progress_list_by_challenge'),

    # Exercises
    path('api/exercises/', views.ExerciseListAPIView.as_view(), name='exercise_list'),
    path('api/exercise/create/', views.ExerciseCreateAPIView.as_view(), name='exercise_create'),

    # User challenges
    path('api/user/challenges/', views.UserChallengesAPIView.as_view(), name='user_challenges'),

    # Analytics
    path('api/challenge/<int:challenge_id>/analytics/', views.ChallengeAnalyticsAPIView.as_view(), name='challenge_analytics'),
    path('api/challenge/<int:challenge_id>/progress-history/', views.ChallengeProgressHistoryAPIView.as_view(), name='challenge_progress_history'),
    path('api/challenge/<int:challenge_id>/', views.ChallengeDetailAPIView.as_view(), name='challenge_detail'),

    # Weather
    path('api/weather/location/update/', views.LocationUpdateAPIView.as_view(), name='location_update'),
    path('api/weather/forecast/', views.WeatherForecastAPIView.as_view(), name='weather_forecast'),
    path('api/weather/location/search/', views.LocationSearchAPIView.as_view(), name='location_search'),

    # Admin
    path('api/admin/users/search/', views.AdminUserSearchAPIView.as_view(), name='admin_user_search'),
    path('api/admin/users/<int:user_id>/', views.AdminUserDetailAPIView.as_view(), name='admin_user_detail'),
    path('api/admin/exercises/', views.AdminExerciseManagementAPIView.as_view(), name='admin_exercise_management'),
    path('api/admin/exercises/<int:exercise_id>/', views.AdminExerciseManagementAPIView.as_view(), name='admin_exercise_detail'),
    path('api/admin/challenges/', views.AdminChallengeManagementAPIView.as_view(), name='admin_challenge_management'),
    path('api/admin/challenges/<int:challenge_id>/', views.AdminChallengeManagementAPIView.as_view(), name='admin_challenge_detail'),
]
