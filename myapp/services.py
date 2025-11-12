import logging
import math
import requests
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional, Tuple, List

from django.db.models import Sum, Avg, Count, Q
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import (
    Challenge, HabitChallenge, TargetChallenge, Exercise,
    ChallengeType, Participant, ParticipantRole, ParticipantState
)

# -------------------------
# Constants
# -------------------------
MAX_DURATION_DAYS = getattr(settings, "CHALLENGE_MAX_DURATION_DAYS", 365)
TOP_SIMILAR_LIMIT = getattr(settings, "CHALLENGE_SIMILAR_TOP_N", 3)
SIMILAR_CACHE_TTL = getattr(settings, "CHALLENGE_SIMILAR_CACHE_TTL_SECONDS", 300)


# -------------------------
# Challenge Service
# -------------------------
class ChallengeService:
    """
    Service layer for challenge-related operations.

    Responsibilities:
    - Validate challenge payloads (data-level validation).
    - Create / update challenge records and nested details atomically.
    - Compute similarity and trending metrics.

    NOTE: Permission checks (who may create/update/delete) MUST be performed by callers (views / DRF permissions).
    This service only performs domain validation.
    """

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _get_exercise_from_data(data: Optional[Dict]):
        """
        Extract the 'exercise' object from a nested habit or target data dictionary.
        Returns None if no data is provided.
        """
        if not data:
            return None
        return data.get("exercise")

    @staticmethod
    def _derive_summary(challenge_type: int, habit: Optional[Dict] = None, target: Optional[Dict] = None) -> Dict:
        """
        Derive a summary dictionary for a challenge containing essential fields for validation
        and similarity scoring.

        Args:
            challenge_type: Integer representing challenge type (HABIT or TARGET)
            habit: Optional habit challenge data dictionary
            target: Optional target challenge data dictionary

        Returns:
            Dictionary containing summarized fields like type, category, frequency, duration, target value, and exercise ID.
        """
        exercise = ChallengeService._get_exercise_from_data(habit or target)

        def safe_int(v):
            return int(v) if v is not None else None

        return {
            "type": challenge_type,
            "category": getattr(exercise, "category", None) if exercise else None,
            "frequency": safe_int(habit.get("frequency_per_week")) if habit else None,
            "duration_weeks": safe_int(habit.get("duration_weeks")) if habit else None,
            "target_value": safe_int(target.get("target_value")) if target else None,
            "duration_days": safe_int(target.get("duration_days")) if target else None,
            "exercise_id": getattr(exercise, "id", None) if exercise else None,
        }

    # -------------------------
    # Validation
    # -------------------------
    @staticmethod
    def check_habit_limits(exercise: Exercise, frequency_per_week: int, duration_weeks: int):
        """
        Validate habit challenge limits against exercise constraints.

        Raises:
            ValidationError if limits are violated.
        """
        if not exercise:
            raise ValidationError("Exercise is required for habit challenge validation.")
        frequency_per_week = int(frequency_per_week)
        duration_weeks = int(duration_weeks)
        if frequency_per_week < 1 or duration_weeks < 1:
            raise ValidationError("frequency_per_week and duration_weeks must be >= 1.")
        total_sessions = frequency_per_week * duration_weeks
        max_allowed = exercise.max_sessions_per_day * 7 * duration_weeks
        if total_sessions > max_allowed:
            raise ValidationError(f"Total sessions ({total_sessions}) exceed max allowed ({max_allowed}).")

    @staticmethod
    def check_target_limits(exercise: Exercise, target_value: int, duration_days: int):
        """
        Validate target challenge limits against exercise constraints.

        Raises:
            ValidationError if limits are violated.
        """
        if not exercise:
            raise ValidationError("Exercise is required for target challenge validation.")
        target_value = int(target_value)
        duration_days = int(duration_days)
        if duration_days < 1 or duration_days > MAX_DURATION_DAYS:
            raise ValidationError(f"duration_days must be between 1 and {MAX_DURATION_DAYS}.")
        avg_per_day = math.ceil(Decimal(target_value) / Decimal(duration_days))
        if avg_per_day > exercise.max_sessions_per_day:
            raise ValidationError(f"Target per day ({avg_per_day}) exceeds max/day ({exercise.max_sessions_per_day}).")
        max_total = int((Decimal(exercise.max_rate_per_minute) * Decimal(24 * 60) * Decimal(duration_days)).to_integral_value())
        if target_value > max_total:
            raise ValidationError(f"Target value ({target_value}) exceeds allowed maximum ({max_total}).")

    # -------------------------
    # Similarity / Duplicate Detection
    # -------------------------
    @staticmethod
    def score_against_existing(new_summary: Dict, existing_challenge: Challenge) -> int:
        """
        Compute a similarity score between a new challenge summary and an existing challenge.

        Returns:
            Integer score (higher => more similar)
        """
        logger = logging.getLogger(__name__)
        if existing_challenge.challenge_type != new_summary["type"]:
            return 0

        details = getattr(existing_challenge, "habit_details", None) \
            if new_summary["type"] == ChallengeType.HABIT \
            else getattr(existing_challenge, "target_details", None)

        if not details or not getattr(details, "exercise", None):
            return 0

        score = 0
        if new_summary.get("category") and new_summary.get("category") == getattr(details.exercise, "category", None):
            score += 1

        if new_summary["type"] == ChallengeType.HABIT:
            new_freq = new_summary.get("frequency") or 0
            existing_freq = getattr(details, "frequency_per_week", 0) or 0
            if abs(new_freq - existing_freq) <= 2:
                score += 1
            new_dur = new_summary.get("duration_weeks") or 0
            existing_dur = getattr(details, "duration_weeks", 0) or 0
            if abs(new_dur - existing_dur) <= 5:
                score += 1
        else:
            new_tv = new_summary.get("target_value") or 0
            existing_tv = getattr(details, "target_value", 0) or 0
            if existing_tv:
                try:
                    pct_diff = int(round(abs(new_tv - existing_tv) / existing_tv * 100))
                except Exception:
                    pct_diff = 100
                if pct_diff <= 5:
                    score += 1
            new_days = new_summary.get("duration_days") or 0
            existing_days = getattr(details, "duration_days", 0) or 0
            if abs(new_days - existing_days) <= 5:
                score += 1

        logger.debug("Scoring challenge %s vs new summary => %s", existing_challenge.pk, score)
        return score

    @classmethod
    def find_similar(cls, new_summary: Dict, exclude_pk: Optional[int] = None) -> List[Tuple[Challenge, int]]:
        """
        Find similar challenges based on summary, with optional caching.

        Returns:
            List of tuples (Challenge, similarity score)
        """
        cache_key = f"similar:{new_summary['type']}:{new_summary.get('category','all')}:{new_summary.get('frequency',0)}:{new_summary.get('duration_weeks',0)}:{new_summary.get('target_value',0)}:{new_summary.get('duration_days',0)}"
        cached = cache.get(cache_key)
        scored: List[Tuple[Challenge, int]] = []

        if cached:
            for item in cached:
                try:
                    c = Challenge.objects.select_related(
                        "habit_details__exercise", "target_details__exercise"
                    ).get(pk=item["id"], is_deleted=False)
                    scored.append((c, int(item["score"])))
                except Challenge.DoesNotExist:
                    continue
        else:
            qs = Challenge.objects.filter(is_deleted=False, challenge_type=new_summary["type"]).select_related(
                "habit_details__exercise", "target_details__exercise"
            )
            if new_summary.get("category"):
                if new_summary["type"] == ChallengeType.HABIT:
                    qs = qs.filter(habit_details__exercise__category=new_summary["category"])
                else:
                    qs = qs.filter(target_details__exercise__category=new_summary["category"])

            for challenge in qs:
                score = cls.score_against_existing(new_summary, challenge)
                if score > 0:
                    scored.append((challenge, score))

            scored.sort(key=lambda x: x[1], reverse=True)
            scored = scored[:TOP_SIMILAR_LIMIT]
            cache.set(cache_key, [{"id": c.pk, "score": s} for c, s in scored], timeout=SIMILAR_CACHE_TTL)

        if exclude_pk:
            scored = [(c, s) for c, s in scored if c.pk != exclude_pk]

        return scored

    @classmethod
    def is_exact_duplicate(cls, new_summary: Dict) -> Optional[Challenge]:
        """
        Determine if a new challenge summary exactly matches an existing challenge.

        Returns:
            The existing Challenge if found, otherwise None.
        """
        exercise_id = new_summary.get("exercise_id")
        if not exercise_id:
            return None

        qs = Challenge.objects.filter(is_deleted=False, challenge_type=new_summary["type"]).select_related(
            "habit_details__exercise", "target_details__exercise"
        )

        for c in qs:
            if new_summary["type"] == ChallengeType.HABIT:
                details = getattr(c, "habit_details", None)
                if not details or not details.exercise:
                    continue
                if details.exercise.id == exercise_id and details.duration_weeks == new_summary.get("duration_weeks") and details.frequency_per_week == new_summary.get("frequency"):
                    return c
            else:
                details = getattr(c, "target_details", None)
                if not details or not details.exercise:
                    continue
                if details.exercise.id == exercise_id and details.duration_days == new_summary.get("duration_days") and details.target_value == new_summary.get("target_value"):
                    return c
        return None

    # -------------------------
    # Persistence Helpers
    # -------------------------
    @classmethod
    def _save_nested_data(cls, challenge: Challenge, habit_data: Optional[Dict] = None, target_data: Optional[Dict] = None, participants_data: Optional[List[Dict]] = None):
        """
        Save or update nested habit/target details and participants for a challenge atomically.
        Updates active participant count on the challenge.
        """
        from .serializers import HabitChallengeSerializer, TargetChallengeSerializer
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        logger = logging.getLogger(__name__)

        if habit_data:
            habit_obj, created = HabitChallenge.objects.get_or_create(challenge=challenge, defaults=habit_data)
            if not created:
                serializer = HabitChallengeSerializer(habit_obj, data=habit_data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()

        if target_data:
            target_obj, created = TargetChallenge.objects.get_or_create(challenge=challenge, defaults=target_data)
            if not created:
                serializer = TargetChallengeSerializer(target_obj, data=target_data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
        else:
            if hasattr(challenge, "target_details") and challenge.target_details:
                challenge.target_details.delete()

        if participants_data:
            for p_data in participants_data:
                user = p_data.get("user")
                if user and not hasattr(user, "id"):
                    try:
                        user = UserModel.objects.get(pk=user)
                    except UserModel.DoesNotExist:
                        logger.warning("Participant user id %s not found, skipping", user)
                        continue
                if not user:
                    continue

                participant, created = Participant.objects.get_or_create(
                    challenge=challenge,
                    user=user,
                    defaults={"role": ParticipantRole.PARTICIPANT, "state": ParticipantState.ACTIVE}
                )
                if not created:
                    changed = False
                    new_state = p_data.get("state")
                    if new_state is not None and participant.state != new_state:
                        participant.state = new_state
                        changed = True
                    participant.role = participant.role
                    if changed:
                        participant.save()

        active_count = challenge.participants.filter(state=ParticipantState.ACTIVE).count()
        if challenge.active_participant_count != active_count:
            challenge.active_participant_count = active_count
            challenge.save(update_fields=["active_participant_count"])

    # -------------------------
    # Public APIs: validate, create, update
    # -------------------------
    @classmethod
    def validate_challenge_data(cls, attrs: Dict, force_create: bool = False, exclude_challenge: Optional[Challenge] = None):
        """
        Validate the top-level challenge data and nested details.
        Raises ValidationError on any validation failure.
        Checks for exact duplicates and similar challenges if force_create is False.
        """
        habit = attrs.get("habit_details")
        target = attrs.get("target_details")
        challenge_type = attrs.get("challenge_type")

        if habit and not habit.get("exercise"):
            raise ValidationError({"habit_details": "Exercise must be provided."})
        if target and not target.get("exercise"):
            raise ValidationError({"target_details": "Exercise must be provided."})

        summary = cls._derive_summary(challenge_type, habit, target)

        if summary["type"] == ChallengeType.HABIT:
            cls.check_habit_limits(cls._get_exercise_from_data(habit), habit.get("frequency_per_week"), habit.get("duration_weeks"))
        elif summary["type"] == ChallengeType.TARGET:
            cls.check_target_limits(cls._get_exercise_from_data(target), target.get("target_value"), target.get("duration_days"))

        if not force_create:
            duplicate = cls.is_exact_duplicate(summary)
            if duplicate and (not exclude_challenge or duplicate.pk != exclude_challenge.pk):
                raise ValidationError(f"An identical challenge already exists: {duplicate.title}")

            similar = cls.find_similar(summary, exclude_pk=getattr(exclude_challenge, "pk", None))
            if similar:
                raise ValidationError({
                    "duplicate_alert": "Similar challenge exists.",
                    "matches": [{"id": c.pk, "title": c.title, "score": s} for c, s in similar]
                })

    @classmethod
    @transaction.atomic
    def create_challenge(cls, creator, validated_data: Dict, force_create: bool = False):
        """
        Create a challenge along with nested habit/target details and participants.
        Ensures creator is added as OWNER. Validates all data before creation.
        Returns:
            The created Challenge object.
        """
        from .serializers import HabitChallengeSerializer, TargetChallengeSerializer
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        logger = logging.getLogger(__name__)

        try:
            cls.validate_challenge_data(validated_data, force_create=force_create)

            participants_data = validated_data.pop("participants_data", [])
            habit_data = validated_data.pop("habit_details", None)
            target_data = validated_data.pop("target_details", None)
            validated_data["creator"] = creator

            if habit_data and "exercise" in habit_data and hasattr(habit_data["exercise"], "id"):
                habit_data["exercise_id"] = habit_data.pop("exercise").id
                habit_serializer = HabitChallengeSerializer(data=habit_data)
                habit_serializer.is_valid(raise_exception=True)
                habit_data = habit_serializer.validated_data

            if target_data and "exercise" in target_data and hasattr(target_data["exercise"], "id"):
                target_data["exercise_id"] = target_data.pop("exercise").id
                target_serializer = TargetChallengeSerializer(data=target_data)
                target_serializer.is_valid(raise_exception=True)
                target_data = target_serializer.validated_data

            for p_data in participants_data:
                user_id = p_data.get("user")
                if user_id and not UserModel.objects.filter(pk=user_id).exists():
                    raise ValueError(f"Participant user ID {user_id} does not exist")

            challenge = Challenge.objects.create(**validated_data)
            logger.info("Challenge created: %s (ID %s)", challenge.title, challenge.id)

            Participant.objects.get_or_create(
                challenge=challenge,
                user=creator,
                defaults={"role": ParticipantRole.OWNER, "state": ParticipantState.ACTIVE}
            )

            cls._save_nested_data(challenge, habit_data, target_data, participants_data)
            return challenge

        except Exception as e:
            logger.error("Failed to create challenge: %s", str(e), exc_info=True)
            raise

    @classmethod
    @transaction.atomic
    def update_challenge(cls, challenge: Challenge, validated_data: Dict, user=None):
        """
        Update an existing challenge along with nested habit/target details and participants.
        Raises ValidationError if trying to change challenge type or unauthorized user.
        Returns:
            The updated Challenge object.
        """
        if user:
            cls.assert_user_is_creator(user, challenge)

        validated_data.pop("creator", None)
        habit_data = validated_data.pop("habit_details", None)
        target_data = validated_data.pop("target_details", None)
        participants_data = validated_data.pop("participants_data", None)

        if habit_data and challenge.challenge_type != ChallengeType.HABIT:
            raise ValidationError("Cannot update type from target to habit.")
        if target_data and challenge.challenge_type != ChallengeType.TARGET:
            raise ValidationError("Cannot update type from habit to target.")

        for field, value in validated_data.items():
            setattr(challenge, field, value)
        challenge.save()

        cls._save_nested_data(challenge, habit_data, target_data, participants_data)
        return challenge

    # -------------------------
    # Trending and Progress Validation
    # -------------------------
    @classmethod
    def update_trending_score(cls, challenge: Challenge) -> int:
        """
        Compute and update trending score based on active participants and total progress.
        Returns:
            Computed trending score (int)
        """
        active_count = challenge.participants.filter(state=ParticipantState.ACTIVE).count()
        total_progress = challenge.progress_entries.aggregate(total=Sum("progress_value"))["total"] or 0
        trending_score = active_count * 10 + int(total_progress)
        challenge.trending_score = trending_score
        challenge.save(update_fields=["trending_score"])
        return trending_score

    @staticmethod
    def check_progress(challenge: Challenge, progress_value: int):
        """
        Validate that a given progress value is within allowed limits for the challenge.
        Raises:
            ValidationError if value exceeds limits.
        """
        try:
            progress_value = int(progress_value)
        except (TypeError, ValueError):
            raise ValidationError("progress_value must be an integer.")

        if challenge.challenge_type == ChallengeType.HABIT:
            habit = getattr(challenge, "habit_details", None)
            if not habit:
                raise ValidationError("Habit challenge details not found.")
            ChallengeService.check_habit_limits(habit.exercise, frequency_per_week=progress_value, duration_weeks=habit.duration_weeks)
        elif challenge.challenge_type == ChallengeType.TARGET:
            target = getattr(challenge, "target_details", None)
            if not target:
                raise ValidationError("Target challenge details not found.")
            ChallengeService.check_target_limits(target.exercise, target_value=progress_value, duration_days=target.duration_days)
        else:
            raise ValidationError("Unknown challenge type.")

    # -------------------------
    # Convenience Retrievals
    # -------------------------
    @staticmethod
    def get_filtered_challenges(category: Optional[str] = None, min_duration: Optional[int] = None, max_duration: Optional[int] = None):
        """
        Retrieve published challenges optionally filtered by category and duration ranges.
        Returns:
            Django QuerySet of matching Challenge objects
        """
        qs = Challenge.objects.filter(is_deleted=False, status="published")
        if category:
            qs = qs.filter(
                Q(habit_details__exercise__category=category) |
                Q(target_details__exercise__category=category)
            )
        if min_duration:
            qs = qs.filter(
                Q(habit_details__duration_weeks__gte=min_duration) |
                Q(target_details__duration_days__gte=min_duration)
            )
        if max_duration:
            qs = qs.filter(
                Q(habit_details__duration_weeks__lte=max_duration) |
                Q(target_details__duration_days__lte=max_duration)
            )
        return qs

    # -------------------------
    # Permission helper
    # -------------------------
    @staticmethod
    def assert_user_is_creator(user, challenge: Challenge):
        """
        Raise ValidationError if the given user is not the creator of the challenge.
        """
        if not user or challenge.creator_id != getattr(user, "pk", None):
            raise ValidationError("Only the creator may perform this action.")

    # -------------------------
    # Challenge Analytics
    # -------------------------
    @staticmethod
    def get_challenge_analytics(challenge: Challenge, start_date=None, end_date=None) -> dict:
        """
        Return analytics for a given challenge, including participant counts, progress metrics,
        per-user progress, completion percentage, and trending score.
        """
        participants_qs = challenge.participants.all()
        if start_date:
            participants_qs = participants_qs.filter(joined_at__date__lte=end_date or timezone.now())

        total_participants = participants_qs.count()
        active_count = participants_qs.filter(state=ParticipantState.ACTIVE).count()
        left_count = participants_qs.filter(state=ParticipantState.LEFT).count()
        owner_count = participants_qs.filter(role=ParticipantRole.OWNER).count()

        progress_qs = challenge.progress_entries.all()
        if start_date:
            progress_qs = progress_qs.filter(created_at__date__gte=start_date)
        if end_date:
            progress_qs = progress_qs.filter(created_at__date__lte=end_date)

        total_progress = progress_qs.aggregate(total=Sum('progress_value'))['total'] or 0
        avg_progress = progress_qs.aggregate(avg=Avg('progress_value'))['avg'] or 0
        entry_count = progress_qs.count()

        per_user_progress = progress_qs.values('user__id', 'user__email').annotate(
            total=Sum('progress_value'),
            avg=Avg('progress_value'),
            entries=Count('id')
        ).order_by('-total')

        completion_percentage = None

        if challenge.challenge_type == ChallengeType.HABIT:
            habit = getattr(challenge, "habit_details", None)
            if habit:
                planned_total = (habit.frequency_per_week or 0) * (habit.duration_weeks or 0)
                try:
                    completion_percentage = (
                        float(Decimal(total_progress) / Decimal(planned_total) * 100)
                        if planned_total else 0.0
                    )
                except (InvalidOperation, ZeroDivisionError):
                    completion_percentage = 0.0

        elif challenge.challenge_type == ChallengeType.TARGET:
            target = getattr(challenge, "target_details", None)
            if target:
                target_value = target.target_value or 0
                try:
                    completion_percentage = (
                        float(Decimal(total_progress) / Decimal(target_value) * 100)
                        if target_value else 0.0
                    )
                except (InvalidOperation, ZeroDivisionError):
                    completion_percentage = 0.0

        analytics = {
            "challenge_id": challenge.pk,
            "title": getattr(challenge, "title", None),
            "participants": {
                "total": total_participants,
                "active": active_count,
                "left": left_count,
                "owners": owner_count
            },
            "progress": {
                "total_value": total_progress,
                "average_value": float(avg_progress),
                "entries_count": entry_count,
                "per_user": list(per_user_progress),
                "completion_percentage": completion_percentage
            },
            "trending_score": getattr(challenge, "trending_score", 0)
        }

        return analytics


# -------------------------
# Weather Service
# -------------------------
class WeatherService:
    """
    Service for handling weather-related operations.
    Provides location geocoding and weather forecast functionality.
    """
    
    # WeatherAPI.com configuration
    API_KEY = getattr(settings, 'WEATHERAPI_API_KEY', '')
    BASE_URL = 'http://api.weatherapi.com/v1'
    
    @classmethod
    def geocode_location(cls, location: str) -> Optional[Dict]:
        """
        Convert location string to coordinates using WeatherAPI.com autocomplete.
        
        Args:
            location: Location string (e.g., "London, UK" or "New York")
            
        Returns:
            Dictionary with city, country, latitude, longitude or None if not found
        """
        if not cls.API_KEY:
            return None
            
        try:
            params = {
                'q': location,
                'key': cls.API_KEY
            }
            
            response = requests.get(f"{cls.BASE_URL}/search.json", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                location_data = data[0]
                return {
                    'city': location_data.get('name', ''),
                    'country': location_data.get('country', ''),
                    'latitude': location_data.get('lat'),
                    'longitude': location_data.get('lon')
                }
        except Exception as e:
            logging.getLogger(__name__).error(f"Geocoding failed for location '{location}': {str(e)}")
            
        return None
    
    @classmethod
    def get_weather_forecast(cls, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Get weather forecast for given coordinates using WeatherAPI.com.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Dictionary with current weather and forecast data or None if failed
        """
        if not cls.API_KEY:
            return None
            
        try:
            # WeatherAPI.com uses coordinates in "lat,lon" format
            location_query = f"{latitude},{longitude}"
            
            # Get current weather and forecast in one call
            params = {
                'q': location_query,
                'key': cls.API_KEY,
                'days': 3,  # 3 days forecast
                'aqi': 'no',  # No air quality data
                'alerts': 'no'  # No alerts
            }
            
            response = requests.get(f"{cls.BASE_URL}/forecast.json", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Process current weather
            current = data['current']
            location = data['location']
            
            current_weather = {
                'temperature': current['temp_c'],
                'feels_like': current['feelslike_c'],
                'humidity': current['humidity'],
                'description': current['condition']['text'],
                'icon': current['condition']['icon'],
                'wind_speed': current['wind_kph'] / 3.6,  # Convert km/h to m/s
                'city': location['name'],
                'country': location['country']
            }
            
            # Process forecast (next 24 hours)
            forecast_list = []
            for day in data['forecast']['forecastday']:
                for hour in day['hour'][:8]:  # Next 24 hours (8 hours per day for 3 days)
                    forecast_list.append({
                        'datetime': hour['time'],
                        'temperature': hour['temp_c'],
                        'description': hour['condition']['text'],
                        'icon': hour['condition']['icon'],
                        'humidity': hour['humidity'],
                        'wind_speed': hour['wind_kph'] / 3.6  # Convert km/h to m/s
                    })
            
            return {
                'current': current_weather,
                'forecast': forecast_list[:8],  # Limit to next 8 hours
                'location': {
                    'city': location['name'],
                    'country': location['country'],
                    'latitude': location['lat'],
                    'longitude': location['lon']
                }
            }
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Weather forecast failed for coordinates {latitude}, {longitude}: {str(e)}")
            return None
    
    @classmethod
    def get_weather_by_location(cls, location: str) -> Optional[Dict]:
        """
        Get weather forecast for a location string using WeatherAPI.com.
        
        Args:
            location: Location string (e.g., "London, UK")
            
        Returns:
            Dictionary with weather data or None if failed
        """
        if not cls.API_KEY:
            return None
            
        try:
            # WeatherAPI.com can handle location strings directly
            params = {
                'q': location,
                'key': cls.API_KEY,
                'days': 3,  # 3 days forecast
                'aqi': 'no',  # No air quality data
                'alerts': 'no'  # No alerts
            }
            
            response = requests.get(f"{cls.BASE_URL}/forecast.json", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Process current weather
            current = data['current']
            location_data = data['location']
            
            current_weather = {
                'temperature': current['temp_c'],
                'feels_like': current['feelslike_c'],
                'humidity': current['humidity'],
                'description': current['condition']['text'],
                'icon': current['condition']['icon'],
                'wind_speed': current['wind_kph'] / 3.6,  # Convert km/h to m/s
                'city': location_data['name'],
                'country': location_data['country']
            }
            
            # Process forecast (next 24 hours)
            forecast_list = []
            for day in data['forecast']['forecastday']:
                for hour in day['hour'][:8]:  # Next 24 hours (8 hours per day for 3 days)
                    forecast_list.append({
                        'datetime': hour['time'],
                        'temperature': hour['temp_c'],
                        'description': hour['condition']['text'],
                        'icon': hour['condition']['icon'],
                        'humidity': hour['humidity'],
                        'wind_speed': hour['wind_kph'] / 3.6  # Convert km/h to m/s
                    })
            
            return {
                'current': current_weather,
                'forecast': forecast_list[:8],  # Limit to next 8 hours
                'location': {
                    'city': location_data['name'],
                    'country': location_data['country'],
                    'latitude': location_data['lat'],
                    'longitude': location_data['lon']
                }
            }
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Weather forecast failed for location '{location}': {str(e)}")
            return None
