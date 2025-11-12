import pytest
from unittest.mock import patch
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory
from model_bakery import baker

from myapp.serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    ChallengeSerializer, ProgressEntrySerializer
)
from myapp.models import (
    User, Exercise, Challenge, HabitChallenge, TargetChallenge,
    Participant, ParticipantState, ChallengeType, UserRole
)

# -----------------------------
# REGISTER SERIALIZER
# -----------------------------

@pytest.mark.django_db
def test_register_serializer_valid_saves_user():
    data = {
        "email": "test@example.com",
        "display_name": "Tester",
        "password": "ComplexPass123",
        "password2": "ComplexPass123",
    }
    ser = RegisterSerializer(data=data)
    assert ser.is_valid(), ser.errors
    user = ser.save()
    assert user.email == "test@example.com"
    assert user.check_password("ComplexPass123")

@pytest.mark.django_db
def test_register_serializer_mismatch_and_duplicate_email():
    baker.make(User, email="dup@example.com")

    mismatch = {
        "email": "x@example.com", "display_name": "X",
        "password": "pass1", "password2": "pass2"
    }
    dup = {
        "email": "dup@example.com", "display_name": "Dup",
        "password": "ComplexPass123", "password2": "ComplexPass123"
    }

    with pytest.raises(DRFValidationError):
        RegisterSerializer(data=mismatch).is_valid(raise_exception=True)
    with pytest.raises(DRFValidationError):
        RegisterSerializer(data=dup).is_valid(raise_exception=True)

@pytest.mark.django_db
def test_register_serializer_normalizes_email():
    data = {
        "email": "UPPERCASE@Example.COM",
        "display_name": "Case",
        "password": "ComplexPass123",
        "password2": "ComplexPass123",
    }
    ser = RegisterSerializer(data=data)
    ser.is_valid(raise_exception=True)
    user = ser.save()
    assert user.email == "uppercase@example.com"

# -----------------------------
# LOGIN SERIALIZER
# -----------------------------

@pytest.mark.django_db
def test_login_serializer_calls_authenticate_lowercase(monkeypatch):
    user = baker.make(User, email="login@example.com")
    user.set_password("Correct123")
    user.save()

    mock_auth = patch("myapp.serializers.authenticate", return_value=user)
    with mock_auth as mock:
        ser = LoginSerializer(
            data={"email": "LoGiN@Example.com", "password": "Correct123"},
            context={"request": None}
        )
        assert ser.is_valid()
        mock.assert_called_once_with(request=None, email="login@example.com", password="Correct123")

@pytest.mark.django_db
def test_login_serializer_invalid_credentials():
    user = baker.make(User, email="fail@example.com")
    user.set_password("GoodPass123")
    user.save()

    ser = LoginSerializer(
        data={"email": "fail@example.com", "password": "WrongPass"},
        context={"request": None}
    )
    with pytest.raises(DRFValidationError):
        ser.is_valid(raise_exception=True)

# -----------------------------
# USER SERIALIZER
# -----------------------------

@pytest.mark.django_db
def test_user_serializer_staff_can_update_role():
    staff = baker.make(User, is_staff=True)
    factory = APIRequestFactory()
    request = factory.patch("/")
    request.user = staff
    ser = UserSerializer(
        staff, data={"role": UserRole.ADMIN}, partial=True, context={"request": request}
    )
    ser.is_valid(raise_exception=True)
    updated = ser.save()
    assert updated.role == UserRole.ADMIN

@pytest.mark.django_db
def test_user_serializer_nonstaff_role_update_forbidden():
    user = baker.make(User)
    factory = APIRequestFactory()
    request = factory.patch("/")
    request.user = user
    ser = UserSerializer(
        user, data={"role": "admin"}, partial=True, context={"request": request}
    )
    with pytest.raises(DRFValidationError):
        ser.is_valid(raise_exception=True)

@pytest.mark.django_db
def test_user_serializer_display_name_immutable():
    user = baker.make(User, display_name="Old")
    ser = UserSerializer(user, data={"display_name": "New"}, partial=True)
    with pytest.raises(DRFValidationError):
        ser.is_valid(raise_exception=True)

# -----------------------------
# PROGRESS ENTRY SERIALIZER
# -----------------------------

@pytest.mark.django_db
def test_progress_entry_serializer_validates_active_participant_and_strips_html():
    user = baker.make(User)
    exercise = baker.make(Exercise)
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=1, frequency_per_week=1)
    baker.make(Participant, challenge=challenge, user=user, state=ParticipantState.ACTIVE)

    request = APIRequestFactory().post("/")
    request.user = user

    ser = ProgressEntrySerializer(
        data={"challenge": challenge.id, "progress_value": 1, "duration_minutes": "5", "notes": "<b>Nice</b>"},
        context={"request": request}
    )
    ser.is_valid(raise_exception=True)
    entry = ser.save()
    assert entry.notes == "Nice"

@pytest.mark.django_db
def test_progress_entry_serializer_rejects_inactive_or_deleted_challenge():
    user = baker.make(User)
    challenge = baker.make(Challenge, is_deleted=True)
    baker.make(Participant, challenge=challenge, user=user, state=ParticipantState.ACTIVE)
    req = APIRequestFactory().post("/")
    req.user = user
    ser = ProgressEntrySerializer(
        data={"challenge": challenge.id, "progress_value": 1, "duration_minutes": "1"}, context={"request": req}
    )
    with pytest.raises(DRFValidationError):
        ser.is_valid(raise_exception=True)

# -----------------------------
# CHALLENGE SERIALIZER
# -----------------------------

@pytest.mark.django_db
def test_challenge_serializer_create_habit_nested():
    creator = baker.make(User)
    exercise = baker.make(Exercise)
    payload = {
        "title": "Habit",
        "challenge_type": ChallengeType.HABIT,
        "status": "draft",
        "threshold_percentage": 50,
        "habit_details": {
            "exercise_id": exercise.id,
            "duration_weeks": 2,
            "frequency_per_week": 3,
        },
    }
    req = APIRequestFactory().post("/")
    req.user = creator
    ser = ChallengeSerializer(data=payload, context={"request": req})
    ser.is_valid(raise_exception=True)
    challenge = ser.save()
    habit = HabitChallenge.objects.get(challenge=challenge)
    assert habit.exercise == exercise
    assert habit.frequency_per_week == 3

@pytest.mark.django_db
def test_challenge_serializer_create_target_nested():
    creator = baker.make(User)
    exercise = baker.make(Exercise)
    payload = {
        "title": "Target",
        "challenge_type": ChallengeType.TARGET,
        "status": "draft",
        "threshold_percentage": 70,
        "target_details": {
            "exercise_id": exercise.id,
            "duration_days": 5,
            "target_value": 20,
        },
    }
    req = APIRequestFactory().post("/")
    req.user = creator
    ser = ChallengeSerializer(data=payload, context={"request": req})
    ser.is_valid(raise_exception=True)
    challenge = ser.save()
    target = TargetChallenge.objects.get(challenge=challenge)
    assert target.duration_days == 5
    assert target.target_value == 20

@pytest.mark.django_db
def test_challenge_serializer_update_type_switch_forbidden():
    creator = baker.make(User)
    ch = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=ch, exercise=baker.make(Exercise))
    req = APIRequestFactory().patch("/")
    req.user = creator
    ser = ChallengeSerializer(
        ch,
        data={"target_details": {"exercise_id": baker.make(Exercise).id, "duration_days": 1, "target_value": 5}},
        partial=True,
        context={"request": req},
    )
    with pytest.raises(DRFValidationError):
        ser.is_valid(raise_exception=True)

@pytest.mark.django_db
def test_challenge_serializer_participants_filtered_out_if_not_creator():
    creator = baker.make(User)
    participant = baker.make(User)
    exercise = baker.make(Exercise)
    payload = {
        "title": "Filter",
        "challenge_type": ChallengeType.HABIT,
        "status": "draft",
        "threshold_percentage": 50,
        "habit_details": {
            "exercise_id": exercise.id,
            "duration_weeks": 2,
            "frequency_per_week": 3,
        },
        "participants_data": [{"user": participant.pk}],
    }
    req = APIRequestFactory().post("/")
    req.user = creator
    ser = ChallengeSerializer(data=payload, context={"request": req})
    ser.is_valid(raise_exception=True)
    assert ser.validated_data.get("participants_data") == []
