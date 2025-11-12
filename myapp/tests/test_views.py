import pytest
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from model_bakery import baker

from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from myapp.models import (
    User, Challenge, Participant, Exercise, ProgressEntry,
    ParticipantState, ParticipantRole, ChallengeType,
    ChallengeStatus, HabitChallenge, TargetChallenge, PasswordResetToken
)

# Import views directly for APIRequestFactory-based coverage
from myapp.views import (
    ProfileMeView, LogoutView, DashboardAPIView, PublicChallengeListAPIView,
    JoinChallengeAPIView, LeaveChallengeAPIView, ChallengeCreateAPIView,
    ChallengeUpdateAPIView, ChallengeDeleteAPIView, ProgressEntryCreateAPIView,
    ProgressEntryListAPIView, ExerciseListAPIView, ExerciseCreateAPIView,
    ChallengeDetailAPIView, ChallengeProgressHistoryAPIView, UserChallengesAPIView,
    ChallengeAnalyticsAPIView, AdminUserSearchAPIView, AdminUserDetailAPIView,
    AdminExerciseManagementAPIView, AdminChallengeManagementAPIView,
    LocationUpdateAPIView, WeatherForecastAPIView, LocationSearchAPIView,
)

# ---------------------------------------------------------------------
# Common Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def rf():
    return APIRequestFactory()

@pytest.fixture
def user():
    u = baker.make(User, email='user@test.com', display_name="user")
    u.set_password('password123')
    u.save()
    return u

@pytest.fixture
def staff_user():
    u = baker.make(User, email='staff@test.com', display_name="staff", is_staff=True)
    u.set_password('password123')
    u.save()
    return u

@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def challenge(user):
    # default published habit challenge (most paths accept this)
    ch = baker.make(
        Challenge, creator=user, status='published', is_deleted=False,
        challenge_type=ChallengeType.HABIT, threshold_percentage=80, title="C1"
    )
    ex = baker.make(Exercise, unit_type="reps", max_rate_per_minute=100, category="strength")
    HabitChallenge.objects.create(challenge=ch, exercise=ex, duration_weeks=2, frequency_per_week=3)
    return ch

@pytest.fixture
def exercise():
    return baker.make(Exercise, name="X", unit_type="reps", max_rate_per_minute=100, category="strength")


# ---------------------------------------------------------------------
# Authentication Views
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestAuthViews:
    def test_register(self, api_client):
        payload = {
            'email': 'new@test.com',
            'display_name': 'Test User',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!'
        }
        url = reverse('register')
        response = api_client.post(url, payload)
        assert response.status_code == 201
        # Views return flat tokens under `data`
        assert 'access' in response.data['data']
        assert 'refresh' in response.data['data']
        assert response.data['data']['email'] == 'new@test.com'

    def test_login(self, api_client, user):
        payload = {'email': user.email, 'password': 'password123'}
        url = reverse('login')
        response = api_client.post(url, payload)
        assert response.status_code == 200
        assert 'access' in response.data['data']
        assert 'refresh' in response.data['data']

    def test_change_password(self, auth_client):
        payload = {'current_password': 'password123', 'new_password': 'NewStrongPass123'}
        url = reverse('change_password')
        response = auth_client.post(url, payload)
        assert response.status_code == 200

    def test_logout_with_valid_refresh(self, rf, user):
        # Needs auth + a real refresh token string
        refresh = RefreshToken.for_user(user)
        req = rf.post('/api/logout/', {'refresh': str(refresh)})
        force_authenticate(req, user=user)
        resp = LogoutView.as_view()(req)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestAuthViewsEdgeCases:
    def test_register_password_mismatch(self, api_client):
        payload = {
            'email': 'new@test.com',
            'display_name': 'Test User',
            'password': 'Pass123!',
            'password2': 'Pass1234!'
        }
        url = reverse('register')
        response = api_client.post(url, payload)
        assert response.status_code == 400

    def test_register_weak_password(self, api_client):
        payload = {
            'email': 'new@test.com',
            'display_name': 'Test User',
            'password': '123',
            'password2': '123'
        }
        url = reverse('register')
        response = api_client.post(url, payload)
        assert response.status_code == 400

    def test_login_invalid_credentials(self, api_client):
        payload = {'email': 'nonexist@test.com', 'password': 'wrong'}
        url = reverse('login')
        response = api_client.post(url, payload)
        assert response.status_code == 400

    def test_change_password_wrong_current(self, auth_client):
        payload = {'current_password': 'wrong', 'new_password': 'NewStrongPass123'}
        url = reverse('change_password')
        response = auth_client.post(url, payload)
        assert response.status_code == 400

    def test_change_password_weak_new(self, auth_client):
        payload = {'current_password': 'password123', 'new_password': '123'}
        url = reverse('change_password')
        response = auth_client.post(url, payload)
        assert response.status_code == 400

    def test_password_reset_request_and_confirm(self, rf, user, monkeypatch):
        # Request
        req = rf.post('/api/password-reset/request/', {'email': user.email})
        resp = PasswordResetRequestAPIView.as_view()(req)  # no auth required
        assert resp.status_code == 200
        assert "Reset URL" in resp.data['data']['message']

        # Confirm using a real token record
        prt = PasswordResetToken.objects.create(user=user)
        req2 = rf.post('/api/password-reset/confirm/', {
            'token': prt.token,
            'new_password': 'AnotherStrong123!'
        })
        resp2 = PasswordResetConfirmAPIView.as_view()(req2)  # no auth required
        assert resp2.status_code == 200
        assert "Password changed successfully" in resp2.data['message']


# ---------------------------------------------------------------------
# Profile & Dashboard
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestProfileAndDashboard:
    def test_profile_me_get_and_put_display_name(self, rf, user):
        # GET
        req = rf.get('/api/me/')
        force_authenticate(req, user=user)
        resp = ProfileMeView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data['email'] == user.email

        # PUT display_name only
        req2 = rf.put('/api/me/', {'display_name': 'New Name'})
        force_authenticate(req2, user=user)
        resp2 = ProfileMeView.as_view()(req2)
        assert resp2.status_code == 200
        assert resp2.data['display_name'] == 'New Name'

    def test_dashboard_lists_published_challenges_with_participation_flag(self, rf, user):
        # One published, one draft
        published = baker.make(Challenge, title="Pub", status='published', is_deleted=False, creator=user)
        draft = baker.make(Challenge, title="Draft", status='draft', is_deleted=False, creator=user)
        Participant.objects.create(user=user, challenge=published, state=ParticipantState.ACTIVE)

        req = rf.get('/api/dashboard/')
        force_authenticate(req, user=user)
        resp = DashboardAPIView.as_view()(req)
        assert resp.status_code == 200
        titles = {c['title'] for c in resp.data['data']['challenges']}
        assert "Pub" in titles and "Draft" not in titles
        # participation flag present
        for c in resp.data['data']['challenges']:
            if c['title'] == "Pub":
                assert c['is_participating'] is True


# ---------------------------------------------------------------------
# Challenge Views
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestChallengeViews:
    def test_public_challenge_list(self, auth_client, challenge):
        url = reverse('challenge_list')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) >= 1

    def test_join_challenge(self, rf, challenge, user):
        req = rf.post(f'/api/challenges/{challenge.id}/join/')
        force_authenticate(req, user=user)
        resp = JoinChallengeAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 200
        participant = Participant.objects.get(user=user, challenge=challenge)
        assert participant.state == ParticipantState.ACTIVE

    def test_leave_challenge(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge, state=ParticipantState.ACTIVE)
        req = rf.post(f'/api/challenges/{challenge.id}/leave/')
        force_authenticate(req, user=user)
        resp = LeaveChallengeAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 200
        assert Participant.objects.get(user=user, challenge=challenge).state == ParticipantState.LEFT

    def test_create_habit_challenge(self, auth_client, exercise, user):
        payload = {
            'title': 'New Habit Challenge',
            'challenge_type': ChallengeType.HABIT,
            'status': ChallengeStatus.PUBLISHED,
            'threshold_percentage': 80,
            'habit_details': {
                'exercise_id': exercise.id,
                'duration_weeks': 2,
                'frequency_per_week': 3
            }
        }
        url = reverse('challenge_create')
        response = auth_client.post(url, payload, format='json')
        assert response.status_code == 201
        assert response.data['data']['title'] == 'New Habit Challenge'

    def test_update_challenge_by_creator(self, rf, challenge, user):
        req = rf.put(f'/api/challenges/{challenge.id}/', {'title': 'Updated'}, format='json')
        force_authenticate(req, user=user)
        resp = ChallengeUpdateAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 200
        assert resp.data['data']['title'] == 'Updated'

    def test_delete_challenge_by_creator_without_others(self, rf, user):
        ch = baker.make(Challenge, creator=user, status='published', is_deleted=False, title="Solo")
        req = rf.delete(f'/api/challenges/{ch.id}/')
        force_authenticate(req, user=user)
        resp = ChallengeDeleteAPIView.as_view()(req, challenge_id=ch.id)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestChallengeViewsEdgeCases:
    def test_join_already_participating(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge, state=ParticipantState.ACTIVE)
        req = rf.post(f'/api/challenges/{challenge.id}/join/')
        force_authenticate(req, user=user)
        resp = JoinChallengeAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 400

    def test_leave_not_participating(self, rf, challenge, user):
        req = rf.post(f'/api/challenges/{challenge.id}/leave/')
        force_authenticate(req, user=user)
        resp = LeaveChallengeAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 400

    def test_leave_owner_if_only_participant_deletes_challenge(self, rf, user):
        ch = baker.make(Challenge, creator=user, status='published', is_deleted=False, title="OwnerOnly")
        Participant.objects.create(
            user=user, challenge=ch, state=ParticipantState.ACTIVE, role=ParticipantRole.OWNER
        )
        req = rf.post(f'/api/challenges/{ch.id}/leave/')
        force_authenticate(req, user=user)
        resp = LeaveChallengeAPIView.as_view()(req, challenge_id=ch.id)
        assert resp.status_code == 200
        assert resp.data['data']['challenge_deleted'] is True

    def test_update_challenge_non_creator(self, rf, challenge):
        other_user = baker.make(User)
        req = rf.put(f'/api/challenges/{challenge.id}/', {'title': 'Hacked'})
        force_authenticate(req, user=other_user)
        resp = ChallengeUpdateAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 403

    def test_delete_challenge_with_other_participants(self, rf, challenge, user):
        other_user = baker.make(User)
        Participant.objects.create(user=other_user, challenge=challenge, state=ParticipantState.ACTIVE)
        req = rf.delete(f'/api/challenges/{challenge.id}/')
        force_authenticate(req, user=user)
        resp = ChallengeDeleteAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 400

    def test_delete_challenge_non_creator(self, rf, challenge):
        other_user = baker.make(User)
        req = rf.delete(f'/api/challenges/{challenge.id}/')
        force_authenticate(req, user=other_user)
        resp = ChallengeDeleteAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 403


# ---------------------------------------------------------------------
# Progress Entry Views
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestProgressEntryViews:
    def test_create_progress_entry_habit(self, rf, user):
        exercise = Exercise.objects.create(
            name="Push Ups", unit_type="reps",
            max_sessions_per_day=5, max_rate_per_minute=Decimal("100"),
            category="strength"
        )

        challenge_instance = Challenge.objects.create(
            title="Habit Challenge Test",
            challenge_type=ChallengeType.HABIT,
            status="published",
            creator=user,
            threshold_percentage=80
        )

        HabitChallenge.objects.create(
            challenge=challenge_instance,
            exercise=exercise,
            duration_weeks=2,
            frequency_per_week=3
        )
        Participant.objects.create(user=user, challenge=challenge_instance, state=ParticipantState.ACTIVE)

        payload = {'challenge': challenge_instance.id, 'progress_value': 3, 'duration_minutes': "3"}
        req = rf.post('/api/progress/', payload, format='json')
        force_authenticate(req, user=user)
        resp = ProgressEntryCreateAPIView.as_view()(req)
        assert resp.status_code == 201

    def test_create_progress_entry_target(self, rf, user):
        exercise = Exercise.objects.create(
            name="Cycling", unit_type="km",
            max_sessions_per_day=10, max_rate_per_minute=Decimal("5"),
            category="cardio"
        )

        challenge_instance = Challenge.objects.create(
            title="Target Challenge Test",
            challenge_type=ChallengeType.TARGET,
            status="published",
            creator=user,
            threshold_percentage=80
        )

        TargetChallenge.objects.create(
            challenge=challenge_instance,
            exercise=exercise,
            duration_days=5,
            target_value=50
        )
        Participant.objects.create(user=user, challenge=challenge_instance, state=ParticipantState.ACTIVE)

        payload = {'challenge': challenge_instance.id, 'progress_value': 50, 'duration_minutes': "20"}
        req = rf.post('/api/progress/', payload, format='json')
        force_authenticate(req, user=user)
        resp = ProgressEntryCreateAPIView.as_view()(req)
        assert resp.status_code == 201

    def test_list_progress_entries(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge, state=ParticipantState.ACTIVE)
        ProgressEntry.objects.create(user=user, challenge=challenge, progress_value=5, duration_minutes=Decimal("10"))

        req = rf.get(f'/api/progress/{challenge.id}/')
        force_authenticate(req, user=user)
        resp = ProgressEntryListAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 1


@pytest.mark.django_db
class TestProgressEntryViewsEdgeCases:
    def test_create_progress_not_participant(self, rf, challenge, user):
        payload = {'challenge': challenge.id, 'progress_value': 1, 'duration_minutes': "1"}
        req = rf.post('/api/progress/', payload)
        force_authenticate(req, user=user)
        resp = ProgressEntryCreateAPIView.as_view()(req)
        assert resp.status_code == 400

    def test_create_progress_above_rate_limit(self, rf, user):
        # Make a habit with very low allowed rate to trip the guard
        ex = baker.make(Exercise, max_rate_per_minute=1, unit_type="reps")
        ch = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=user, status='published')
        HabitChallenge.objects.create(challenge=ch, exercise=ex, duration_weeks=1, frequency_per_week=1)
        Participant.objects.create(user=user, challenge=ch, state=ParticipantState.ACTIVE)
        req = rf.post('/api/progress/', {'challenge': ch.id, 'progress_value': 100, 'duration_minutes': "1"})
        force_authenticate(req, user=user)
        resp = ProgressEntryCreateAPIView.as_view()(req)
        assert resp.status_code == 400


# ---------------------------------------------------------------------
# Exercise Views
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestExerciseViews:
    def test_list_exercises_wrapped_pagination(self, rf, exercise, user):
        req = rf.get('/api/exercises/')
        force_authenticate(req, user=user)
        resp = ExerciseListAPIView.as_view()(req)
        assert resp.status_code == 200
        assert 'results' in resp.data['data'] and len(resp.data['data']['results']) >= 1

    def test_create_exercise_staff(self, rf, staff_user):
        req = rf.post('/api/exercises/', {
            'name': 'New Exercise',
            'max_sessions_per_day': 5,
            'max_rate_per_minute': 100,
            'unit_type': 'reps',
            'category': 'strength'
        }, format='json')
        force_authenticate(req, user=staff_user)
        resp = ExerciseCreateAPIView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data['data']['name'] == 'New Exercise'


@pytest.mark.django_db
class TestExerciseViewsEdgeCases:
    def test_create_exercise_non_staff_forbidden(self, rf, user):
        req = rf.post('/api/exercises/', {
            'name': 'Invalid Exercise', 'unit_type': 'reps',
            'max_sessions_per_day': 5, 'max_rate_per_minute': 10,
            'category': 'strength'
        })
        force_authenticate(req, user=user)
        resp = ExerciseCreateAPIView.as_view()(req)
        assert resp.status_code == 403


# ---------------------------------------------------------------------
# Challenge Detail / History / User Challenges
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestChallengeDetailAndHistory:
    def test_challenge_detail_has_participants_and_units(self, rf, user):
        ex = baker.make(Exercise, unit_type="km", max_rate_per_minute=5, category="cardio")
        ch = baker.make(Challenge, creator=user, status='published',
                        challenge_type=ChallengeType.TARGET, title="T")
        TargetChallenge.objects.create(challenge=ch, exercise=ex, duration_days=7, target_value=100)
        Participant.objects.create(user=user, challenge=ch, state=ParticipantState.ACTIVE)
        ProgressEntry.objects.create(user=user, challenge=ch, progress_value=10, duration_minutes=10)

        req = rf.get(f'/api/challenges/{ch.id}/')
        force_authenticate(req, user=user)
        resp = ChallengeDetailAPIView.as_view()(req, challenge_id=ch.id)
        assert resp.status_code == 200
        data = resp.data['data']
        assert data['id'] == ch.id
        assert data['participant_count'] >= 1
        assert data['exercise_unit_type'] == "km"

    def test_progress_history_requires_participation_and_lists_entries(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge, state=ParticipantState.ACTIVE)
        ProgressEntry.objects.create(user=user, challenge=challenge, progress_value=2, duration_minutes=2)
        req = rf.get(f'/api/challenges/{challenge.id}/history/')
        force_authenticate(req, user=user)
        resp = ChallengeProgressHistoryAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 200
        assert resp.data['data']['total_entries'] >= 1

    def test_user_challenges_wrapped_response(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge, state=ParticipantState.ACTIVE)
        req = rf.get('/api/my-challenges/?status=active')
        force_authenticate(req, user=user)
        resp = UserChallengesAPIView.as_view()(req)
        assert resp.status_code == 200
        assert 'results' in resp.data['data']


# ---------------------------------------------------------------------
# Challenge Analytics
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestChallengeAnalytics:
    def test_challenge_analytics_for_participant(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge)
        req = rf.get(f'/api/challenges/{challenge.id}/analytics/?top_n=5')
        force_authenticate(req, user=user)
        resp = ChallengeAnalyticsAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 200
        assert 'progress' in resp.data['data']

    def test_analytics_not_participant_or_staff_forbidden(self, rf, challenge):
        other = baker.make(User)
        req = rf.get(f'/api/challenges/{challenge.id}/analytics/')
        force_authenticate(req, user=other)
        resp = ChallengeAnalyticsAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 403

    def test_analytics_invalid_date_range(self, rf, challenge, user):
        Participant.objects.create(user=user, challenge=challenge)
        req = rf.get(f'/api/challenges/{challenge.id}/analytics/?start_date=2025-10-20&end_date=2025-10-10')
        force_authenticate(req, user=user)
        resp = ChallengeAnalyticsAPIView.as_view()(req, challenge_id=challenge.id)
        assert resp.status_code == 400


# ---------------------------------------------------------------------
# Admin APIs
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminAPIs:
    def test_admin_user_search(self, rf, staff_user):
        baker.make(User, email="alice@test.com", display_name="Alice")
        baker.make(User, email="bob@test.com", display_name="Bob")
        req = rf.get('/api/admin/users/?q=ali')
        force_authenticate(req, user=staff_user)
        resp = AdminUserSearchAPIView.as_view()(req)
        assert resp.status_code == 200
        assert any(u['email'] == "alice@test.com" for u in resp.data['data']['users'])

    def test_admin_user_detail_get_and_delete_other_user(self, rf, staff_user):
        target = baker.make(User, email="delete-me@test.com")
        req_g = rf.get(f'/api/admin/users/{target.id}/')
        force_authenticate(req_g, user=staff_user)
        resp_g = AdminUserDetailAPIView.as_view()(req_g, user_id=target.id)
        assert resp_g.status_code == 200
        # Delete
        req_d = rf.delete(f'/api/admin/users/{target.id}/')
        force_authenticate(req_d, user=staff_user)
        resp_d = AdminUserDetailAPIView.as_view()(req_d, user_id=target.id)
        assert resp_d.status_code == 200

    def test_admin_user_detail_cannot_delete_self(self, rf, staff_user):
        req = rf.delete(f'/api/admin/users/{staff_user.id}/')
        force_authenticate(req, user=staff_user)
        resp = AdminUserDetailAPIView.as_view()(req, user_id=staff_user.id)
        assert resp.status_code == 400

    def test_admin_exercise_management_crud(self, rf, staff_user):
        # list
        req_l = rf.get('/api/admin/exercises/')
        force_authenticate(req_l, user=staff_user)
        resp_l = AdminExerciseManagementAPIView.as_view()(req_l)
        assert resp_l.status_code == 200

        # create
        req_c = rf.post('/api/admin/exercises/', {
            'name': 'Admin Ex', 'unit_type': 'reps', 'category': 'strength',
            'max_sessions_per_day': 3, 'max_rate_per_minute': 50
        }, format='json')
        force_authenticate(req_c, user=staff_user)
        resp_c = AdminExerciseManagementAPIView.as_view()(req_c)
        assert resp_c.status_code == 201
        ex_id = resp_c.data['data']['id']

        # update
        req_u = rf.put(f'/api/admin/exercises/{ex_id}/', {'name': 'Admin Ex 2'}, format='json')
        force_authenticate(req_u, user=staff_user)
        resp_u = AdminExerciseManagementAPIView.as_view()(req_u, exercise_id=ex_id)
        assert resp_u.status_code == 200
        assert resp_u.data['data']['name'] == 'Admin Ex 2'

        # delete
        req_d = rf.delete(f'/api/admin/exercises/{ex_id}/')
        force_authenticate(req_d, user=staff_user)
        resp_d = AdminExerciseManagementAPIView.as_view()(req_d, exercise_id=ex_id)
        assert resp_d.status_code == 200

    def test_admin_challenge_management_list_and_delete(self, rf, staff_user):
        ch = baker.make(Challenge, title="AdminC", status='published')
        Participant.objects.create(user=baker.make(User), challenge=ch, state=ParticipantState.ACTIVE)
        # list
        req_l = rf.get('/api/admin/challenges/?q=AdminC&page=1&page_size=10')
        force_authenticate(req_l, user=staff_user)
        resp_l = AdminChallengeManagementAPIView.as_view()(req_l)
        assert resp_l.status_code == 200
        # delete 
        req_d = rf.delete(f'/api/admin/challenges/{ch.id}/')
        force_authenticate(req_d, user=staff_user)
        resp_d = AdminChallengeManagementAPIView.as_view()(req_d, challenge_id=ch.id)
        assert resp_d.status_code == 200
        assert "Removed" in resp_d.data['message']


# ---------------------------------------------------------------------
# Weather / Location
# ---------------------------------------------------------------------

@pytest.mark.django_db
class TestWeatherAndLocation:
    def test_update_location_requires_city(self, rf, user):
        req = rf.post('/api/location/', {'country': 'CA'})
        force_authenticate(req, user=user)
        resp = LocationUpdateAPIView.as_view()(req)
        assert resp.status_code == 400

    def test_update_location_success(self, rf, user):
        req = rf.post('/api/location/', {'city': 'Toronto', 'country': 'CA', 'latitude': 43.7, 'longitude': -79.4})
        force_authenticate(req, user=user)
        resp = LocationUpdateAPIView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data['data']['city'] == 'Toronto'

    def test_weather_forecast_uses_user_saved_location(self, rf, user, monkeypatch):
        user.city = "Toronto"
        user.country = "CA"
        user.save()

        def fake_get_weather_by_location(loc):
            return {"location": loc, "forecast": [{"d": 1}]}

        monkeypatch.setattr("myapp.views.WeatherService.get_weather_by_location", fake_get_weather_by_location)

        req = rf.get('/api/weather/')
        force_authenticate(req, user=user)
        resp = WeatherForecastAPIView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data['data']['location'].startswith("Toronto")

    def test_weather_forecast_with_latlon_and_invalid_values(self, rf, user, monkeypatch):
        req_bad = rf.get('/api/weather/?lat=abc&lon=xyz')
        force_authenticate(req_bad, user=user)
        resp_bad = WeatherForecastAPIView.as_view()(req_bad)
        assert resp_bad.status_code == 400


        def fake_get_weather_forecast(lat, lon):
            return {"lat": lat, "lon": lon, "ok": True}
        monkeypatch.setattr("myapp.views.WeatherService.get_weather_forecast", fake_get_weather_forecast)

        req_ok = rf.get('/api/weather/?lat=43.7&lon=-79.4')
        force_authenticate(req_ok, user=user)
        resp_ok = WeatherForecastAPIView.as_view()(req_ok)
        assert resp_ok.status_code == 200
        assert resp_ok.data['data']['ok'] is True

    def test_location_search(self, rf, user, monkeypatch):
        def fake_geocode(q):
            return [{"name": "Toronto, CA", "lat": 43.7, "lon": -79.4}]
        monkeypatch.setattr("myapp.views.WeatherService.geocode_location", fake_geocode)

        req_bad = rf.get('/api/location/search/')
        force_authenticate(req_bad, user=user)
        resp_bad = LocationSearchAPIView.as_view()(req_bad)
        assert resp_bad.status_code == 400

        req_ok = rf.get('/api/location/search/?q=Toronto')
        force_authenticate(req_ok, user=user)
        resp_ok = LocationSearchAPIView.as_view()(req_ok)
        assert resp_ok.status_code == 200
        assert resp_ok.data['data'][0]['name'].startswith("Toronto")
