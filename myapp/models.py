from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from decimal import Decimal
import uuid
import secrets


# ----------------------
# ENUMS / CHOICES
# ----------------------

class UserRole(models.IntegerChoices):
    """Roles for users: regular user or admin."""
    USER = 0, 'User'
    ADMIN = 1, 'Admin'


class ChallengeStatus(models.TextChoices):
    """Status of a challenge in the system."""
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'


class ChallengeType(models.IntegerChoices):
    """Type of challenge: habit-based or target-based."""
    HABIT = 0, 'Habit'
    TARGET = 1, 'Target'


class ParticipantState(models.TextChoices):
    """State of a participant in a challenge."""
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    LEFT = 'left', 'Left'


class ParticipantRole(models.IntegerChoices):
    """Role of a participant in a challenge: owner or participant."""
    PARTICIPANT = 0, 'Participant'
    OWNER = 1, 'Owner'


# ----------------------
# USER MODEL + LOGIN THROTTLE
# ----------------------

class UserManager(BaseUserManager):
    """Custom user manager to handle user creation."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create a regular user with email as username."""
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create a superuser with is_staff and is_superuser flags."""
        if not password:
            raise ValueError("Superusers must have a password.")
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model using email as username.
    Supports roles and tracks creation date.
    """
    email = models.EmailField(unique=True, db_index=True)
    display_name = models.CharField(max_length=50)
    role = models.IntegerField(
        choices=UserRole.choices,
        default=UserRole.USER
    )
    created_at = models.DateTimeField(default=timezone.now)
    
    # Avatar field
    avatar = models.FileField(upload_to='avatars/', blank=True, null=True, default='blank_profile_pic.jpg')
    
    # Location fields for weather
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    # Required fields for Django admin
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['display_name']

    objects = UserManager()

    def __str__(self):
        return self.display_name


class LoginThrottle(models.Model):
    """
    Tracks failed login attempts for a given email + IP.
    Locks user out after repeated failures.
    """
    email = models.EmailField(db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    failed_count = models.PositiveSmallIntegerField(default=0)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    # Configurable via settings
    MAX_ATTEMPTS = getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)
    WINDOW_MINUTES = getattr(settings, "LOGIN_WINDOW_MINUTES", 10)
    LOCK_MINUTES = getattr(settings, "LOGIN_LOCK_MINUTES", 15)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['email', 'ip'], name='unique_email_ip_loginthrottle'),
        ]
        indexes = [models.Index(fields=['email', 'ip'])]

    def is_locked(self):
        """Check if login is currently locked."""
        return self.locked_until and self.locked_until > timezone.now()

    def register_failure(self):
        """Register a failed login attempt, increment counter, and lock if exceeded."""
        now = timezone.now()
        if not self.last_failed_at or (now - self.last_failed_at) > timedelta(minutes=self.WINDOW_MINUTES):
            self.failed_count = 1  # reset counter if outside window
        else:
            self.failed_count += 1
        self.last_failed_at = now
        if self.failed_count >= self.MAX_ATTEMPTS:
            self.locked_until = now + timedelta(minutes=self.LOCK_MINUTES)
        self.save()

    def reset(self):
        """Reset failed attempts and lock state on successful login."""
        self.failed_count = 0
        self.last_failed_at = None
        self.locked_until = None
        self.save()


class PasswordResetToken(models.Model):
    """
    Stores password reset tokens for users.
    Tokens expire after a configurable time period.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['token', 'expires_at'])]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(seconds=getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600))
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if the token is valid (not expired and not used)."""
        return not self.used and self.expires_at > timezone.now()

    def mark_as_used(self):
        """Mark the token as used."""
        self.used = True
        self.save(update_fields=['used'])

    def __str__(self):
        return f"Password reset token for {self.user.email}"


# ----------------------
# EXERCISE MODEL
# ----------------------
class Exercise(models.Model):
    """Represents an exercise that can be tracked in challenges."""
    UNIT_CHOICES = [
        ('reps', 'Repetitions'),
        ('km', 'Kilometers'),
    ]
    CATEGORY_CHOICES = [
        ('cardio', 'Cardio'),
        ('strength', 'Strength'),
        ('flexibility', 'Flexibility'),
    ]

    name = models.CharField(max_length=50, unique=True)
    max_sessions_per_day = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    max_rate_per_minute = models.DecimalField(
        max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal('0'))]
    )
    unit_type = models.CharField(max_length=10, choices=UNIT_CHOICES, default='reps')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.unit_type})"


# ----------------------
# CHALLENGE MODEL
# ----------------------
class Challenge(models.Model):
    """Represents a general challenge."""
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="challenges_created")
    title = models.CharField(max_length=100)
    challenge_type = models.IntegerField(choices=ChallengeType.choices)
    status = models.CharField(max_length=20, choices=ChallengeStatus.choices, default=ChallengeStatus.DRAFT)
    description = models.TextField(blank=True)
    threshold_percentage = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    active_participant_count = models.PositiveIntegerField(default=0)
    trending_score = models.IntegerField(default=0)

    def __str__(self):
        return self.title


# ----------------------
# PARTICIPANT MODEL
# ----------------------
class Participant(models.Model):
    """
    Represents a user's participation in a challenge.
    - Uses UUID as primary key.
    - Tracks role and state.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="participations")
    role = models.IntegerField(choices=ParticipantRole.choices, default=ParticipantRole.PARTICIPANT)
    state = models.CharField(max_length=20, choices=ParticipantState.choices, default=ParticipantState.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['challenge', 'user'], name='unique_participant_per_challenge')
        ]

    def __str__(self):
        return f"{self.user.display_name} in {self.challenge.title}"


# ----------------------
# HABIT CHALLENGE
# ----------------------
class HabitChallenge(models.Model):
    """
    Details specific to habit-type challenges.
    - One-to-one with Challenge.
    """
    challenge = models.OneToOneField(
        Challenge, on_delete=models.CASCADE, primary_key=True, related_name="habit_details"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="habit_challenges")
    duration_weeks = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    frequency_per_week = models.PositiveIntegerField(validators=[MinValueValidator(1)])


# ----------------------
# TARGET CHALLENGE
# ----------------------
class TargetChallenge(models.Model):
    """
    Details specific to target-type challenges.
    - One-to-one with Challenge.
    """
    challenge = models.OneToOneField(
        Challenge, on_delete=models.CASCADE, primary_key=True, related_name="target_details"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="target_challenges")
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    target_value = models.PositiveIntegerField(validators=[MinValueValidator(1)])


# ----------------------
# PROGRESS ENTRY
# ----------------------
class ProgressEntry(models.Model):
    """
    Tracks individual user's progress for a challenge.
    - Includes notes, duration, and timestamp.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress_entries')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='progress_entries')
    progress_value = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(500)])
    duration_minutes = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.1'))])
    notes = models.TextField(blank=True, null=True)
    logged_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.display_name} progress in {self.challenge.title}: {self.progress_value}"
