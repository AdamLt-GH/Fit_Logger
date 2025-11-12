import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.cache import cache
from model_bakery import baker

from myapp.models import (
    User, Exercise, Challenge, HabitChallenge, TargetChallenge,
    Participant, ParticipantState, ChallengeType
)
from myapp.services import ChallengeService, MAX_DURATION_DAYS

# ==========================================================
# Habit / Target Validation
# ==========================================================

@pytest.mark.django_db
def test_habit_limits_success():
    exercise = baker.make(Exercise, max_sessions_per_day=3)
    ChallengeService.check_habit_limits(exercise, frequency_per_week=3, duration_weeks=2)

@pytest.mark.django_db
def test_habit_limits_fail_conditions():
    exercise = baker.make(Exercise, max_sessions_per_day=3)

    # Zero values
    with pytest.raises(ValidationError):
        ChallengeService.check_habit_limits(exercise, frequency_per_week=0, duration_weeks=2)
    with pytest.raises(ValidationError):
        ChallengeService.check_habit_limits(exercise, frequency_per_week=2, duration_weeks=0)

    # Exceeds daily limit
    # 3 sessions/day × 7 days × 2 weeks = 42 allowed total
    with pytest.raises(ValidationError):
        ChallengeService.check_habit_limits(exercise, frequency_per_week=22, duration_weeks=2)


@pytest.mark.django_db
def test_target_limits_success():
    exercise = baker.make(Exercise, max_sessions_per_day=25, max_rate_per_minute=1)
    ChallengeService.check_target_limits(exercise, target_value=100, duration_days=5)

@pytest.mark.django_db
def test_target_limits_fail_conditions():
    exercise = baker.make(Exercise, max_sessions_per_day=5, max_rate_per_minute=1)

    # Invalid duration or excessive targets
    with pytest.raises(ValidationError):
        ChallengeService.check_target_limits(exercise, target_value=10, duration_days=0)
    with pytest.raises(ValidationError):
        ChallengeService.check_target_limits(exercise, target_value=10, duration_days=MAX_DURATION_DAYS + 1)
    with pytest.raises(ValidationError):
        ChallengeService.check_target_limits(exercise, target_value=1000, duration_days=1)

# ==========================================================
# Challenge Creation / Update
# ==========================================================

@pytest.mark.django_db
def test_create_habit_challenge_creates_related_objects():
    creator = baker.make(User)
    exercise = baker.make(Exercise, max_sessions_per_day=5)

    data = {
        "title": "Habit Test",
        "challenge_type": ChallengeType.HABIT,
        "status": "draft",
        "threshold_percentage": 50,
        "habit_details": {
            "exercise": exercise,
            "duration_weeks": 2,
            "frequency_per_week": 5
        }
    }

    challenge = ChallengeService.create_challenge(creator, data)
    assert challenge.creator == creator
    assert challenge.habit_details.exercise == exercise
    assert challenge.habit_details.duration_weeks == 2
    assert challenge.habit_details.frequency_per_week == 5

@pytest.mark.django_db
def test_update_habit_challenge_adds_participant():
    creator = baker.make(User)
    exercise = baker.make(Exercise)
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=2, frequency_per_week=3)
    participant = baker.make(User)

    update_data = {
        "title": "Updated Title",
        "participants_data": [{"user": participant.pk, "state": ParticipantState.ACTIVE}]
    }
    updated = ChallengeService.update_challenge(challenge, update_data, user=creator)

    assert updated.title == "Updated Title"
    assert updated.participants.filter(user=participant).exists()

@pytest.mark.django_db
def test_update_challenge_type_switch_raises_error():
    creator = baker.make(User)
    exercise = baker.make(Exercise)
    habit = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=habit, exercise=exercise, duration_weeks=2, frequency_per_week=3)

    # Attempt invalid type switch
    with pytest.raises(ValidationError):
        ChallengeService.update_challenge(
            habit,
            {"target_details": {"exercise": exercise, "duration_days": 2, "target_value": 10}},
            user=creator
        )

# ==========================================================
# Progress Validation
# ==========================================================

@pytest.mark.django_db
def test_check_progress_invalid_inputs_raise():
    creator = baker.make(User)
    exercise = baker.make(Exercise, max_sessions_per_day=5)
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=2, frequency_per_week=3)

    # Non-integer progress
    with pytest.raises(ValidationError):
        ChallengeService.check_progress(challenge, "abc")

    # Exceeds valid max
    with pytest.raises(ValidationError):
        ChallengeService.check_progress(challenge, 100)

@pytest.mark.django_db
def test_check_progress_missing_details_raise():
    creator = baker.make(User)
    ch1 = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    ch2 = baker.make(Challenge, challenge_type=ChallengeType.TARGET, creator=creator)

    with pytest.raises(ValidationError):
        ChallengeService.check_progress(ch1, 1)
    with pytest.raises(ValidationError):
        ChallengeService.check_progress(ch2, 1)

# ==========================================================
# Duplicate / Similar Challenge Detection
# ==========================================================

@pytest.mark.django_db
def test_is_exact_duplicate_detects_and_none_case():
    creator = baker.make(User)
    exercise = baker.make(Exercise)
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=2, frequency_per_week=3)

    same = {
        "type": ChallengeType.HABIT,
        "exercise_id": exercise.id,
        "duration_weeks": 2,
        "frequency": 3
    }
    diff = {**same, "frequency": 4}

    assert ChallengeService.is_exact_duplicate(same) == challenge
    assert ChallengeService.is_exact_duplicate(diff) is None

@pytest.mark.django_db
def test_find_similar_returns_and_uses_cache(monkeypatch):
    cache.clear()
    creator = baker.make(User)
    exercise = baker.make(Exercise, category="strength")
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=3, frequency_per_week=4)

    summary = {
        "type": ChallengeType.HABIT,
        "category": "strength",
        "exercise_id": exercise.id,
        "duration_weeks": 3,
        "frequency": 4
    }

    first = ChallengeService.find_similar(summary)
    assert first

    # Cache validation
    def fake_qs(*args, **kwargs):
        raise AssertionError("Queryset call should be cached")
    monkeypatch.setattr(ChallengeService, "score_against_existing", fake_qs)

    cached = ChallengeService.find_similar(summary)
    assert cached == first

# ==========================================================
# Analytics
# ==========================================================

@pytest.mark.django_db
def test_analytics_habit_and_target_types():
    creator = baker.make(User)
    exercise = baker.make(Exercise)

    # Habit
    habit = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=habit, exercise=exercise, duration_weeks=2, frequency_per_week=5)
    baker.make(Participant, challenge=habit, user=creator, state=ParticipantState.ACTIVE)
    baker.make("myapp.ProgressEntry", challenge=habit, progress_value=5, user=creator)

    a1 = ChallengeService.get_challenge_analytics(habit)
    assert a1["progress"]["total_value"] >= 5
    assert "completion_percentage" in a1["progress"]

    # Target
    target = baker.make(Challenge, challenge_type=ChallengeType.TARGET, creator=creator)
    baker.make(TargetChallenge, challenge=target, exercise=exercise, duration_days=2, target_value=20)
    baker.make(Participant, challenge=target, user=creator, state=ParticipantState.ACTIVE)
    baker.make("myapp.ProgressEntry", challenge=target, progress_value=10, user=creator)

    a2 = ChallengeService.get_challenge_analytics(target)
    assert a2["progress"]["completion_percentage"] == 50.0

@pytest.mark.django_db
def test_analytics_handles_empty_cases():
    creator = baker.make(User)
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)

    # No progress entries
    analytics = ChallengeService.get_challenge_analytics(challenge)
    assert analytics["progress"]["total_value"] == 0
    assert analytics["progress"]["completion_percentage"] is None

    # Zero-planned total
    exercise = baker.make(Exercise, max_sessions_per_day=5)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=0, frequency_per_week=0)

    analytics = ChallengeService.get_challenge_analytics(challenge)
    assert analytics["progress"]["completion_percentage"] == 0.0

# ==========================================================
# Participants
# ==========================================================

@pytest.mark.django_db
def test_participant_invalid_user_is_safely_skipped():
    creator = baker.make(User)
    exercise = baker.make(Exercise)
    challenge = baker.make(Challenge, challenge_type=ChallengeType.HABIT, creator=creator)
    baker.make(HabitChallenge, challenge=challenge, exercise=exercise, duration_weeks=2, frequency_per_week=3)

    ChallengeService._save_nested_data(challenge, participants_data=[{"user": 9999, "state": ParticipantState.ACTIVE}])
    assert challenge.participants.count() == 0
