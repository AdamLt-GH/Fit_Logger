import pytest
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_bakery import baker

from myapp.models import (
    User, UserRole, LoginThrottle, PasswordResetToken,
    Exercise, Challenge, ChallengeType, ChallengeStatus,
    HabitChallenge, TargetChallenge, Participant, ParticipantState, ParticipantRole,
    ProgressEntry,
)


# =========================
# User / UserManager
# =========================

@pytest.mark.django_db
def test_user_manager_create_user_and_str():
    u = User.objects.create_user(email="x@y.com", password="pass12345", display_name="X")
    assert u.email == "x@y.com"
    assert str(u) == "X"
    assert u.has_usable_password() is True
    assert u.role == UserRole.USER


@pytest.mark.django_db
def test_user_manager_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x", display_name="Nope")


@pytest.mark.django_db
def test_user_manager_create_user_unusable_password_when_none():
    u = User.objects.create_user(email="nopass@y.com", password=None, display_name="NP")
    assert u.has_usable_password() is False


@pytest.mark.django_db
def test_user_manager_create_superuser_and_flags():
    su = User.objects.create_superuser(email="admin@y.com", password="Strong123!", display_name="Boss")
    assert su.is_staff is True and su.is_superuser is True

    # must have a password
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="bad@y.com", password=None, display_name="Nope")

    # flags must be True
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="x@y.com", password="p", display_name="x", is_staff=False)
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="y@y.com", password="p", display_name="y", is_superuser=False)


@pytest.mark.django_db
def test_user_avatar_default():
    u = baker.make(User, email="a@b.com", display_name="A")
    assert str(u.avatar)  # default path/name present


# =========================
# LoginThrottle
# =========================

@pytest.mark.django_db
def test_login_throttle_register_and_lock_and_reset():
    lt = LoginThrottle.objects.create(email="lock@ex.com", ip="127.0.0.1")
    for _ in range(LoginThrottle.MAX_ATTEMPTS):
        lt.register_failure()
    lt.refresh_from_db()
    assert lt.is_locked()

    lt.reset()
    lt.refresh_from_db()
    assert lt.failed_count == 0
    assert not lt.is_locked()   # returns falsy (None/False), don't compare with `is False`
    assert lt.last_failed_at is None


@pytest.mark.django_db
def test_login_throttle_window_resets_counter():
    lt = LoginThrottle.objects.create(email="w@ex.com", ip="127.0.0.2", failed_count=3)
    lt.last_failed_at = timezone.now() - timedelta(minutes=LoginThrottle.WINDOW_MINUTES + 1)
    lt.save(update_fields=["last_failed_at", "failed_count"])
    lt.register_failure()
    lt.refresh_from_db()
    assert lt.failed_count == 1  # counter reset because outside window


@pytest.mark.django_db
def test_login_throttle_unique_email_ip():
    LoginThrottle.objects.create(email="u@ex.com", ip="10.0.0.1")
    with pytest.raises(IntegrityError):
        LoginThrottle.objects.create(email="u@ex.com", ip="10.0.0.1")


# =========================
# PasswordResetToken
# =========================

@pytest.mark.django_db
def test_password_reset_token_autofill_and_validation_and_str():
    u = baker.make(User)
    t = PasswordResetToken.objects.create(user=u)
    assert t.token and t.expires_at
    assert t.is_valid() is True
    assert u.email in str(t)

    # mark used -> invalid
    t.mark_as_used()
    t.refresh_from_db()
    assert t.used is True and t.is_valid() is False

    # expired -> invalid
    t2 = PasswordResetToken.objects.create(user=u)
    t2.expires_at = timezone.now() - timedelta(seconds=1)
    t2.save(update_fields=["expires_at"])
    assert t2.is_valid() is False


# =========================
# Exercise
# =========================

@pytest.mark.django_db
def test_exercise_str_and_validators():
    ex = Exercise(name="Push Ups", max_sessions_per_day=5, max_rate_per_minute=Decimal("10.000"),
                  unit_type="reps", category="strength")
    ex.full_clean()
    ex.save()
    assert "Push Ups (reps)" in str(ex)

    # validators: non-positive values should fail on full_clean()
    ex_bad = Exercise(name="Bad", max_sessions_per_day=0, max_rate_per_minute=Decimal("-1"),
                      unit_type="reps", category="strength")
    with pytest.raises(ValidationError):
        ex_bad.full_clean()


@pytest.mark.django_db
def test_exercise_unique_name():
    Exercise.objects.create(name="UniqueName", max_sessions_per_day=1,
                            max_rate_per_minute=Decimal("1.000"), unit_type="reps", category="strength")
    # isolate the integrity error inside its own atomic block to avoid breaking the test transaction
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Exercise.objects.create(name="UniqueName", max_sessions_per_day=2,
                                    max_rate_per_minute=Decimal("2.000"), unit_type="reps", category="strength")


# =========================
# Challenge + nested details
# =========================

@pytest.mark.django_db
def test_challenge_defaults_and_habit_relation():
    u = baker.make(User)
    ch = Challenge.objects.create(
        creator=u, title="Habit X", challenge_type=ChallengeType.HABIT,
        threshold_percentage=50
    )
    assert ch.status == ChallengeStatus.DRAFT
    assert ch.published_at is None and ch.is_deleted is False
    assert ch.get_challenge_type_display() == "Habit"

    ex = baker.make(Exercise)
    HabitChallenge.objects.create(challenge=ch, exercise=ex, duration_weeks=2, frequency_per_week=3)
    ch.refresh_from_db()
    assert ch.habit_details.exercise == ex


@pytest.mark.django_db
def test_challenge_target_relation_and_threshold_validator():
    u = baker.make(User)
    ch = Challenge.objects.create(
        creator=u, title="Target X", challenge_type=ChallengeType.TARGET,
        threshold_percentage=80, status=ChallengeStatus.PUBLISHED
    )
    ex = baker.make(Exercise)
    TargetChallenge.objects.create(challenge=ch, exercise=ex, duration_days=5, target_value=20)
    assert ch.target_details.exercise == ex

    ch.threshold_percentage = 101
    with pytest.raises(ValidationError):
        ch.full_clean()


# =========================
# Participant
# =========================

@pytest.mark.django_db
def test_participant_displays_and_defaults():
    u = baker.make(User)
    ch = baker.make(Challenge, creator=u, challenge_type=ChallengeType.HABIT, threshold_percentage=10)
    p = Participant.objects.create(user=u, challenge=ch, state=ParticipantState.ACTIVE, role=ParticipantRole.PARTICIPANT)
    assert p.get_state_display() == "Active"
    assert p.get_role_display() == "Participant"


# =========================
# ProgressEntry
# =========================

@pytest.mark.django_db
def test_progress_entry_creation_and_logged_at():
    u = baker.make(User)
    ch = baker.make(Challenge, creator=u, challenge_type=ChallengeType.HABIT, threshold_percentage=10)
    ex = baker.make(Exercise, max_sessions_per_day=5, max_rate_per_minute=Decimal("100.000"))
    HabitChallenge.objects.create(challenge=ch, exercise=ex, duration_weeks=1, frequency_per_week=1)
    Participant.objects.create(user=u, challenge=ch, state=ParticipantState.ACTIVE)

    pe = ProgressEntry.objects.create(user=u, challenge=ch, progress_value=3, duration_minutes=Decimal("15.0"))
    assert pe.logged_at <= timezone.now()
    assert pe.notes in (None, "",)


@pytest.mark.django_db
def test_progress_entry_missing_duration_raises_integrity_error():
    u = baker.make(User)
    ch = baker.make(Challenge, creator=u, challenge_type=ChallengeType.HABIT, threshold_percentage=10)
    ex = baker.make(Exercise)
    HabitChallenge.objects.create(challenge=ch, exercise=ex, duration_weeks=1, frequency_per_week=1)
    Participant.objects.create(user=u, challenge=ch, state=ParticipantState.ACTIVE)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProgressEntry.objects.create(user=u, challenge=ch, progress_value=1)  # duration_minutes is NOT NULL
