import re
import bleach
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.conf import settings

from .models import (
    User, UserRole, LoginThrottle, ChallengeType, Exercise, Challenge,
    Participant, ParticipantState, HabitChallenge, TargetChallenge,
    ProgressEntry, ParticipantRole, ChallengeStatus
)
from .services import ChallengeService

CLASS_MINUTES_PER_DAY = getattr(settings, "CLASS_MINUTES_PER_DAY", 24*60)  # Default minutes in a day if not in settings


# ----------------------
# AUTH SERIALIZERS
# ----------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8, label="Confirm password")

    class Meta:
        model = User
        fields = ['email', 'display_name', 'role', 'password', 'password2']
        extra_kwargs = {'role': {'default': UserRole.USER}}

    def validate(self, data):
        # normalize email first
        email = (data.get('email') or "").strip().lower()
        data['email'] = email

        # duplicate email -> 400 (not 500)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Passwords must match."})

        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return data

    def create(self, validated_data):
        # keep your existing logic
        validated_data.pop('password2', None)
        validated_data.pop('role', None)
        password = validated_data.pop('password')
        email = validated_data.pop('email').lower()
        return User.objects.create_user(email=email, password=password, **validated_data)

class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    Handles authentication and login throttling based on email and IP.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def _get_ip(self, request):
        """
        Extracts the client's IP address from request headers.
        Prefers HTTP_X_FORWARDED_FOR if behind proxy, else REMOTE_ADDR.
        """
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def validate(self, data):
        """
        Validates user credentials.
        Checks for login throttling, authenticates user, and raises errors if locked or invalid.
        Resets throttle count on successful login.
        """
        email = data.get('email').lower()
        password = data.get('password')
        request = self.context.get('request')
        ip = self._get_ip(request) if request else None

        throttle, _ = LoginThrottle.objects.get_or_create(email=email, ip=ip)
        if throttle.is_locked():
            raise serializers.ValidationError(f"Account locked until {throttle.locked_until}")

        user = authenticate(request=request, email=email, password=password)
        if not user:
            throttle.register_failure()
            raise serializers.ValidationError("Invalid email or password.")

        throttle.reset()
        data['user'] = user
        return data


# ----------------------
# BASIC SERIALIZERS
# ----------------------
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for basic user info.
    Handles read-only email and creation date.
    Validates display name immutability and role changes (staff only).
    """
    role = serializers.ChoiceField(choices=UserRole.choices)

    class Meta:
        model = User
        fields = ['id', 'email', 'display_name', 'role', 'created_at']
        read_only_fields = ['created_at', 'email']

    def validate_display_name(self, value):
        """
        Ensures the display name cannot be changed once set.
        """
        if self.instance and self.instance.display_name != value:
            raise serializers.ValidationError("Display name cannot be changed once registered.")
        return value

    def validate_role(self, value):
        """
        Only allows staff to modify the user's role.
        """
        request = self.context.get('request')
        if self.instance and 'role' in self.initial_data:
            if not request or not request.user.is_staff:
                raise serializers.ValidationError("Only staff may change user roles.")
        return value

    def update(self, instance, validated_data):
        """
        Updates allowed user fields with validated data.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class ExerciseSerializer(serializers.ModelSerializer):
    """
    Serializer for Exercise objects.
    Handles basic exercise info like name, session limits, and category.
    """
    class Meta:
        model = Exercise
        fields = ['id', 'name', 'max_sessions_per_day', 'max_rate_per_minute', 'unit_type', 'category']


class ParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for Participant objects.
    Includes nested user info and allows setting user via user_id.
    Validates role and state fields.
    """
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True,
        required=False
    )
    role = serializers.ChoiceField(choices=ParticipantRole.choices)
    state = serializers.ChoiceField(choices=ParticipantState.choices)

    class Meta:
        model = Participant
        fields = ['id', 'user', 'user_id', 'role', 'state', 'joined_at']


# ----------------------
# CHALLENGE SUB-SERIALIZERS
# ----------------------
class HabitChallengeSerializer(serializers.ModelSerializer):
    """
    Serializer for HabitChallenge details.
    Maps exercise using exercise_id and exposes a read-only exercise_id_read.
    """
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(),
        source='exercise',
        write_only=True
    )
    exercise_id_read = serializers.IntegerField(source='exercise.id', read_only=True)
    exercise_name = serializers.CharField(source='exercise.name', read_only=True)
    exercise_category = serializers.CharField(source='exercise.category', read_only=True)

    class Meta:
        model = HabitChallenge
        fields = ['exercise_id', 'exercise_id_read', 'exercise_name', 'exercise_category', 'duration_weeks', 'frequency_per_week']


class TargetChallengeSerializer(serializers.ModelSerializer):
    """
    Serializer for TargetChallenge details.
    Maps exercise using exercise_id.
    """
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(),
        source='exercise'
    )
    exercise_name = serializers.CharField(source='exercise.name', read_only=True)
    exercise_category = serializers.CharField(source='exercise.category', read_only=True)

    class Meta:
        model = TargetChallenge
        fields = ['exercise_id', 'exercise_name', 'exercise_category', 'duration_days', 'target_value']


# ----------------------
# PROGRESS ENTRY SERIALIZER
# ----------------------
class ProgressEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for progress entries.
    Validates that user is an active participant and progress value meets challenge rules.
    Sanitizes notes to remove scripts and HTML.
    """
    challenge = serializers.PrimaryKeyRelatedField(
        queryset=Challenge.objects.filter(is_deleted=False)
    )
    progress_value = serializers.IntegerField()
    duration_minutes = serializers.DecimalField(max_digits=8, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ProgressEntry
        fields = ['challenge', 'progress_value', 'duration_minutes', 'logged_at', 'notes']
        read_only_fields = ['logged_at']

    def get_exercise_and_duration(self, challenge):
        """
        Retrieves the exercise and duration for the given challenge.
        Returns tuple (exercise, duration).
        Raises ValidationError if details are missing.
        """
        if challenge.challenge_type == ChallengeType.HABIT:
            habit = getattr(challenge, 'habit_details', None)
            if not habit:
                raise serializers.ValidationError({"challenge": "Habit challenge details not found."})
            return habit.exercise, habit.duration_weeks
        else:
            target = getattr(challenge, 'target_details', None)
            if not target:
                raise serializers.ValidationError({"challenge": "Target challenge details not found."})
            return target.exercise, target.duration_days

    def validate(self, attrs):
        """
        Validates that the user is an active participant in the challenge.
        Validates the progress value using ChallengeService.
        """
        challenge = attrs.get('challenge')
        user = self.context['request'].user
        progress_value = attrs.get('progress_value', 0)

        if not challenge.participants.filter(user=user, state=ParticipantState.ACTIVE).exists():
            raise serializers.ValidationError({"challenge": "You are not an active participant in this challenge."})

        try:
            ChallengeService.check_progress(challenge, progress_value)
        except ValidationError as e:
            raise serializers.ValidationError({"progress_value": str(e)})

        return attrs

    def validate_notes(self, value):
        """
        Sanitizes notes by removing scripts and HTML tags.
        """
        if value:
            value = re.sub(r'<script.*?>.*?</script>', '', value, flags=re.DOTALL | re.IGNORECASE)
            value = bleach.clean(value, tags=[], strip=True)
        return value

    def create(self, validated_data):
        """
        Assigns the logged-in user to the progress entry before creation.
        """
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


# ----------------------
# MAIN CHALLENGE SERIALIZER
# ----------------------
class ChallengeSerializer(serializers.ModelSerializer):
    """
    Serializer for Challenge objects.
    Handles creator info, participants, habit/target details, and validation of challenge type.
    """
    creator = UserSerializer(read_only=True)
    creator_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='creator',
        write_only=True,
        required=False
    )
    participants = ParticipantSerializer(many=True, read_only=True)
    participants_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    habit_details = HabitChallengeSerializer(required=False, allow_null=True)
    target_details = TargetChallengeSerializer(required=False, allow_null=True)
    challenge_type = serializers.ChoiceField(choices=ChallengeType.choices)
    status = serializers.ChoiceField(choices=ChallengeStatus.choices)
    trending_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Challenge
        fields = [
            'id', 'title', 'creator', 'creator_id', 'challenge_type', 'status',
            'description', 'threshold_percentage', 'created_at', 'published_at',
            'is_deleted', 'participants', 'participants_data',
            'habit_details', 'target_details', 'trending_score'
        ]
        read_only_fields = ['created_at', 'published_at', 'is_deleted', 'trending_score']

    def validate(self, attrs):
        """
        Validates challenge updates and ensures that only the creator can set participant data.
        Prevents changing the challenge type inappropriately.
        """
        if self.instance:
            if 'habit_details' in attrs and self.instance.challenge_type != ChallengeType.HABIT:
                raise serializers.ValidationError("Cannot update type from target to habit.")
            if 'target_details' in attrs and self.instance.challenge_type != ChallengeType.TARGET:
                raise serializers.ValidationError("Cannot update type from habit to target.")

        user = self.context['request'].user
        participants_data = attrs.get('participants_data', [])
        if participants_data and attrs.get('creator') != user:
            attrs['participants_data'] = [p for p in participants_data if p.get('user') == user.id]

        return attrs

    def to_representation(self, instance):
        """
        Custom representation to include habit_details, target_details, and additional fields for frontend.
        """
        data = super().to_representation(instance)
        
        # Add participant count
        data['participant_count'] = instance.participants.filter(state=ParticipantState.ACTIVE).count()
        
        # Add habit_details if it's a habit challenge
        if instance.challenge_type == ChallengeType.HABIT:
            try:
                habit_challenge = instance.habit_details
                data['habit_details'] = HabitChallengeSerializer(habit_challenge).data
                # Add fields for frontend compatibility
                data['duration_weeks'] = habit_challenge.duration_weeks
                data['exercise'] = habit_challenge.exercise.name if habit_challenge.exercise else "N/A"
                data['exercise_unit_type'] = habit_challenge.exercise.unit_type if habit_challenge.exercise else "units"
                data['max_rate_per_minute'] = float(habit_challenge.exercise.max_rate_per_minute) if habit_challenge.exercise else 100
            except Exception as e:
                print(f"Error accessing habit challenge for {instance.id}: {e}")
                data['habit_details'] = None
                data['duration_weeks'] = None
                data['exercise'] = "N/A"
                data['exercise_unit_type'] = "units"
                data['max_rate_per_minute'] = 100
        
        # Add target_details if it's a target challenge
        elif instance.challenge_type == ChallengeType.TARGET:
            try:
                target_challenge = instance.target_details
                data['target_details'] = TargetChallengeSerializer(target_challenge).data
                # Add fields for frontend compatibility
                data['duration_days'] = target_challenge.duration_days
                data['exercise'] = target_challenge.exercise.name if target_challenge.exercise else "N/A"
                data['exercise_unit_type'] = target_challenge.exercise.unit_type if target_challenge.exercise else "units"
                data['max_rate_per_minute'] = float(target_challenge.exercise.max_rate_per_minute) if target_challenge.exercise else 100
            except Exception as e:
                print(f"Error accessing target challenge for {instance.id}: {e}")
                data['target_details'] = None
                data['duration_days'] = None
                data['exercise'] = "N/A"
                data['exercise_unit_type'] = "units"
                data['max_rate_per_minute'] = 100
        
        return data

    def create(self, validated_data):
        """
        Creates a new Challenge along with optional habit or target details.
        Assigns the creator to the logged-in user if not explicitly provided.
        Automatically enrolls the creator as a participant with owner role.
        """
        creator = validated_data.pop('creator', None) or self.context['request'].user
        habit_data = validated_data.pop('habit_details', None)
        target_data = validated_data.pop('target_details', None)

        challenge = Challenge.objects.create(creator=creator, **validated_data)

        if habit_data:
            HabitChallenge.objects.create(challenge=challenge, **habit_data)
        if target_data:
            TargetChallenge.objects.create(challenge=challenge, **target_data)

        # Automatically enroll the creator as a participant with owner role
        from .models import Participant, ParticipantRole, ParticipantState
        Participant.objects.create(
            challenge=challenge,
            user=creator,
            role=ParticipantRole.OWNER,
            state=ParticipantState.ACTIVE
        )

        return challenge
