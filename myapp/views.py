from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.dateparse import parse_date
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import models

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, OutstandingToken
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser


from .serializers import (
    RegisterSerializer, LoginSerializer, ChallengeSerializer,
    ProgressEntrySerializer, ExerciseSerializer
)
from .models import (
    User, Challenge, Participant, ParticipantState, ParticipantRole,
    Exercise, ProgressEntry, PasswordResetToken
)
from .services import ChallengeService, WeatherService
from django.db import IntegrityError

# ----------------------
# HELPERS
# ----------------------
def get_tokens_for_user(user):
    """
    Generate JWT access and refresh tokens for a given user.
    """
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def parse_optional_date(date_str):
    """
    Safely parse a date string into a datetime.date object.
    Returns None if input is empty or invalid.
    """
    try:
        return parse_date(date_str) if date_str else None
    except Exception:
        return None


def error_response(message, code=status.HTTP_400_BAD_REQUEST):
    """
    Return a standardized error response with a message and HTTP status code.
    """
    return Response({'status': 'error', 'message': message}, status=code)


def success_response(data=None, message=None, code=status.HTTP_200_OK):
    """
    Return a standardized success response with optional data and message.
    """
    response = {'status': 'success'}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return Response(response, status=code)


# ----------------------
# PAGINATION
# ----------------------
class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for API views.
    Allows page_size query param and provides default/maximum page limits.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset. Handles both Django querysets and in-memory lists.
        """
        if not hasattr(queryset, 'count'):
            self.count = len(queryset)
            self.request = request
            self.page_size = self.get_page_size(request)
            self.page = queryset[:self.page_size]
            return self.page
        return super().paginate_queryset(queryset, request, view)


# ----------------------
# AUTH VIEWS
# ----------------------
class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            # If two requests slip past the serializer check
            return error_response("A user with this email already exists.", status.HTTP_400_BAD_REQUEST)

        tokens = get_tokens_for_user(user)
        return success_response(
            data={'email': user.email, 'access': tokens['access'], 'refresh': tokens['refresh']},
            message='User registered successfully',
            code=status.HTTP_201_CREATED
        )

class LoginView(APIView):
    """
    API endpoint for user login.
    Accepts credentials and returns JWT tokens on successful authentication.
    """
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        tokens = get_tokens_for_user(user)
        return success_response(
            data={'email': user.email, 'access': tokens['access'], 'refresh': tokens['refresh']}
        )


class LogoutView(APIView):
    """
    API endpoint to logout a user by blacklisting their refresh token.
    Requires the refresh token to be sent in the request body.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return error_response("Refresh token required")
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception as e:
            return error_response(f"Invalid token: {str(e)}")
        return success_response(message="Logged out successfully")

class ProfileMeView(APIView):
    """
    Profile endpoint for user profile management.
    GET  -> returns {email, display_name, avatar}
    PUT  -> updates display_name and avatar
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        user = request.user
        return Response({
            "email": user.email,
            "display_name": getattr(user, "display_name", "") or user.email.split("@")[0],
            "avatar": user.avatar.url if user.avatar else None,
        }, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user
        
        # Update display_name if provided
        display_name = request.data.get("display_name")
        if display_name:
            user.display_name = display_name
        
        # Handle avatar upload if provided
        avatar_file = request.FILES.get("avatar")
        if avatar_file:
            import os
            from django.core.files.storage import default_storage
            import uuid
            
            # Create a unique filename
            file_extension = os.path.splitext(avatar_file.name)[1]
            unique_filename = f"avatars/{user.id}_{uuid.uuid4()}{file_extension}"
            
            # Save the file
            saved_path = default_storage.save(unique_filename, avatar_file)
            user.avatar = saved_path
        
        user.save()
        
        return Response({
            "email": user.email,
            "display_name": user.display_name,
            "avatar": user.avatar.url if user.avatar else None,
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class ChangePasswordAPIView(APIView):
    """
    API endpoint for changing a user's password.
    Validates the current password and new password rules.
    Blacklists all outstanding tokens after successful change.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not user.check_password(current_password):
            return error_response('Current password incorrect')

        try:
            validate_password(new_password)
        except ValidationError as e:
            return error_response(", ".join(e.messages))

        user.set_password(new_password)
        user.save()

        # Blacklist all outstanding tokens
        for token in OutstandingToken.objects.filter(user=user):
            try:
                RefreshToken(token.token).blacklist()
            except Exception:
                continue

        return success_response(message="Password changed successfully. Please login again.")


@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequestAPIView(APIView):
    """
    API endpoint for requesting a password reset.
    Sends a reset link to the user's email if the email exists.
    """
    
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return error_response('Email is required')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # For security, don't reveal if email exists or not
            return success_response(message="If that email exists, a reset link was sent.")
        
        # Create a new password reset token
        reset_token = PasswordResetToken.objects.create(user=user)
        
        # Generate localhost reset URL for development
        reset_url = f"http://localhost:5173/reset-password?token={reset_token.token}"
        
        # Return the reset URL in the response
        response_data = {
            "message": f"If that email exists, a reset link was created. Reset URL: {reset_url}"
        }
        
        return success_response(data=response_data)


@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetConfirmAPIView(APIView):
    """
    API endpoint for confirming password reset with a token.
    Validates the token and updates the user's password.
    """
    
    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        if not token:
            return error_response('Reset token is required')
        if not new_password:
            return error_response('New password is required')
        
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            return error_response('Invalid or expired reset token')
        
        if not reset_token.is_valid():
            return error_response('Invalid or expired reset token')
        
        # Validate the new password
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(new_password)
        except ValidationError as e:
            return error_response(", ".join(e.messages))
        
        # Update the user's password
        user = reset_token.user
        user.set_password(new_password)
        user.save()
        
        # Mark the token as used
        reset_token.mark_as_used()
        
        # Blacklist all outstanding tokens for this user
        from rest_framework_simplejwt.tokens import OutstandingToken, RefreshToken
        for token in OutstandingToken.objects.filter(user=user):
            try:
                RefreshToken(token.token).blacklist()
            except Exception:
                continue
        
        return success_response(message="Password changed successfully. You can now log in.")


# ----------------------
# CHALLENGE LIST / DASHBOARD
# ----------------------

class DashboardAPIView(APIView):
    """
    API endpoint to retrieve dashboard data including user info and challenges.
    Returns user information and a list of challenges with participation status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"Dashboard API - User authenticated: {request.user.is_authenticated}")
        print(f"Dashboard API - User: {request.user}")
        print(f"Dashboard API - Auth header: {request.META.get('HTTP_AUTHORIZATION', 'No auth header')}")
        
        # Get user information
        user_data = {
            'id': request.user.id,
            'email': request.user.email,
            'display_name': getattr(request.user, 'display_name', request.user.email.split('@')[0]),
            'first_name': getattr(request.user, 'first_name', ''),
            'last_name': getattr(request.user, 'last_name', ''),
            'role': request.user.get_role_display(),
            'is_staff': request.user.is_staff,
        }

        # Get challenges with participation status
        challenges = ChallengeService.get_filtered_challenges()
        challenges = challenges.filter(status='published', is_deleted=False)
        
        # Add participation status for each challenge
        challenge_data = []
        for challenge in challenges:
            is_participating = Participant.objects.filter(
                user=request.user,
                challenge=challenge,
                state=ParticipantState.ACTIVE
            ).exists()
            
            challenge_serializer = ChallengeSerializer(challenge)
            challenge_dict = challenge_serializer.data
            challenge_dict['is_participating'] = is_participating
            challenge_data.append(challenge_dict)

        return success_response(data={
            'user': user_data,
            'challenges': challenge_data
        })


class PublicChallengeListAPIView(APIView):
    """
    API endpoint to retrieve publicly available challenges.
    Supports filtering by category, duration, and exclusion of already joined challenges.
    Paginated response is returned.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        category = request.query_params.get('category')
        min_duration = request.query_params.get('min_duration')
        max_duration = request.query_params.get('max_duration')
        exclude_joined = request.query_params.get('exclude_joined', 'true').lower() == 'true'

        # Type-cast durations to integers
        min_duration = int(min_duration) if min_duration else None
        max_duration = int(max_duration) if max_duration else None

        # Get filtered challenges from service
        qs = ChallengeService.get_filtered_challenges(
            category=category,
            min_duration=min_duration,
            max_duration=max_duration
        )

        # Exclude challenges user is already participating in
        if exclude_joined:
            qs = qs.exclude(
                participants__user=request.user,
                participants__state=ParticipantState.ACTIVE
            )

        # Ensure consistent ordering
        qs = qs.order_by('created_at', 'id')

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ChallengeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ----------------------
# JOIN / LEAVE CHALLENGE
# ----------------------
class JoinChallengeAPIView(APIView):
    """
    API endpoint for joining a challenge.
    Creates or activates a Participant record.
    Updates trending score for the challenge.
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(csrf_exempt)
    def post(self, request, challenge_id):
        challenge = get_object_or_404(
            Challenge, id=challenge_id, status='published', is_deleted=False
        )

        participation, created = Participant.objects.get_or_create(
            user=request.user,
            challenge=challenge,
            defaults={'role': ParticipantRole.PARTICIPANT, 'state': ParticipantState.ACTIVE}
        )

        if not created and participation.state == ParticipantState.ACTIVE:
            return error_response('Already participating', status.HTTP_400_BAD_REQUEST)

        participation.state = ParticipantState.ACTIVE
        participation.joined_at = timezone.now()
        participation.save(update_fields=['state', 'joined_at'])

        trending_score = ChallengeService.update_trending_score(challenge)
        return success_response(
            message='Joined challenge successfully',
            data={'trending_score': trending_score}
        )


class LeaveChallengeAPIView(APIView):
    """
    API endpoint for leaving a challenge.
    Only non-owner participants can leave.
    Updates trending score for the challenge.
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(csrf_exempt)
    def post(self, request, challenge_id):
        participation = Participant.objects.filter(
            user=request.user,
            challenge_id=challenge_id,
            state=ParticipantState.ACTIVE
        ).first()

        if not participation:
            return error_response('Not participating', status.HTTP_400_BAD_REQUEST)
        
        # If user is the owner, check if they're the only participant
        if participation.role == ParticipantRole.OWNER:
            # Count active participants
            active_participants = Participant.objects.filter(
                challenge_id=challenge_id,
                state=ParticipantState.ACTIVE
            ).count()
            
            if active_participants == 1:
                # Owner is the only participant, delete the challenge
                challenge = participation.challenge
                challenge.delete()
                return success_response(
                    message='Challenge deleted successfully (no other participants)',
                    data={'challenge_deleted': True}
                )
            else:
                return error_response(
                    f'Cannot leave challenge. There are {active_participants - 1} other participant(s) in this challenge.',
                    status.HTTP_403_FORBIDDEN
                )

        # Regular participant leaving
        participation.state = ParticipantState.LEFT
        participation.save(update_fields=['state'])

        trending_score = ChallengeService.update_trending_score(participation.challenge)
        return success_response(
            message='Left challenge successfully',
            data={'trending_score': trending_score}
        )


# ----------------------
# CHALLENGE CRUD
# ----------------------
@method_decorator(csrf_exempt, name='dispatch')
class ChallengeCreateAPIView(APIView):
    """
    API endpoint to create a new challenge.
    Accepts challenge data and optionally force_create context.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChallengeSerializer(
            data=request.data,
            context={'request': request, 'force_create': bool(request.data.get('force_create'))}
        )
        serializer.is_valid(raise_exception=True)
        challenge = serializer.save()
        return success_response(
            data=ChallengeSerializer(challenge).data,
            code=status.HTTP_201_CREATED
        )


@method_decorator(csrf_exempt, name='dispatch')
class ChallengeUpdateAPIView(APIView):
    """
    API endpoint to update an existing challenge.
    Only the creator of the challenge can update it.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, challenge_id):
        challenge = get_object_or_404(Challenge, id=challenge_id, is_deleted=False)

        # Only creator can update
        if challenge.creator != request.user:
            return error_response('Not authorized', status.HTTP_403_FORBIDDEN)

        serializer = ChallengeSerializer(
            challenge,
            data=request.data,
            context={'request': request, 'force_create': bool(request.data.get('force_create'))}
        )
        serializer.is_valid(raise_exception=True)
        updated_challenge = serializer.save()
        return success_response(data=ChallengeSerializer(updated_challenge).data)


@method_decorator(csrf_exempt, name='dispatch')
class ChallengeDeleteAPIView(APIView):
    """
    API endpoint to delete a challenge.
    Only the creator can delete and only if there are no other active participants.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, challenge_id):
        challenge = get_object_or_404(Challenge, id=challenge_id, is_deleted=False)

        if not self._is_creator(challenge, request.user):
            return error_response('Not authorized', status.HTTP_403_FORBIDDEN)

        active_participants = challenge.participants.filter(
            state=ParticipantState.ACTIVE
        ).exclude(user=request.user)
        if active_participants.exists():
            return error_response(
                'Cannot delete challenge with other active participants',
                status.HTTP_400_BAD_REQUEST
            )

        challenge.is_deleted = True
        challenge.save(update_fields=['is_deleted'])
        return success_response(message='Challenge deleted successfully')

    def _is_creator(self, challenge, user):
        """
        Helper method to check if a user is the creator of a challenge.
        """
        return challenge.creator == user


# ----------------------
# PROGRESS ENTRY
# ----------------------
class ProgressEntryCreateAPIView(APIView):
    """
    API endpoint to create a progress entry for a challenge.
    User must be an active participant in the challenge.
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(csrf_exempt)
    def post(self, request):
        serializer = ProgressEntrySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        challenge = serializer.validated_data['challenge']
        if not Participant.objects.filter(
            user=request.user, challenge=challenge, state=ParticipantState.ACTIVE
        ).exists():
            return error_response('Not participating', status.HTTP_400_BAD_REQUEST)

        # Validate rate per minute
        progress_value = serializer.validated_data['progress_value']
        duration_minutes = float(serializer.validated_data['duration_minutes'])
        rate_per_minute = progress_value / duration_minutes
        
        # Get max rate from exercise
        max_rate_per_minute = 100  # Default
        if challenge.challenge_type == 0:  # Habit challenge
            try:
                habit_challenge = challenge.habitchallenge
                max_rate_per_minute = float(habit_challenge.exercise.max_rate_per_minute)
            except:
                max_rate_per_minute = 30
        elif challenge.challenge_type == 1:  # Target challenge
            try:
                target_challenge = challenge.targetchallenge
                max_rate_per_minute = float(target_challenge.exercise.max_rate_per_minute)
            except:
                max_rate_per_minute = 20
        
        if rate_per_minute > max_rate_per_minute:
            return error_response(
                f'Rate too high! Maximum {max_rate_per_minute} units per minute allowed. Your rate: {rate_per_minute:.2f} units/minute',
                status.HTTP_400_BAD_REQUEST
            )

        entry = serializer.save(user=request.user)
        return success_response(data=ProgressEntrySerializer(entry).data, code=status.HTTP_201_CREATED)


class ProgressEntryListAPIView(APIView):
    """
    API endpoint to list all progress entries for the authenticated user.
    Supports filtering by challenge.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, challenge_id=None):
        qs = ProgressEntry.objects.filter(user=request.user)
        if challenge_id:
            qs = qs.filter(challenge_id=challenge_id)

        qs = qs.order_by('logged_at', 'id')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProgressEntrySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ----------------------
# EXERCISES
# ----------------------
class ExerciseListAPIView(APIView):
    """
    API endpoint to retrieve a paginated list of exercises.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        exercises = Exercise.objects.all().order_by('id')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(exercises, request)
        serializer = ExerciseSerializer(page, many=True)
        paginated_response = paginator.get_paginated_response(serializer.data)
        
        # Wrap the paginated response in our custom format
        return success_response(data=paginated_response.data)


class ExerciseCreateAPIView(APIView):
    """
    API endpoint to create a new exercise.
    Only staff users are allowed to create exercises.
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(csrf_exempt)
    def post(self, request):
        if not request.user.is_staff:
            return error_response('Not authorized', status.HTTP_403_FORBIDDEN)

        serializer = ExerciseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=serializer.data)


# ----------------------
# CHALLENGE DETAIL
# ----------------------
class ChallengeDetailAPIView(APIView):
    """
    API endpoint to retrieve detailed information about a specific challenge.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, challenge_id):
        try:
            challenge = Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return error_response("Challenge not found", status.HTTP_404_NOT_FOUND)
        
        # Get participants with their progress
        participants = challenge.participants.all()
        participant_data = []
        from .models import ProgressEntry
        
        for participant in participants:
            # Get user's total progress for this challenge
            user_progress_entries = ProgressEntry.objects.filter(
                challenge=challenge, 
                user=participant.user
            )
            total_progress = sum(entry.progress_value for entry in user_progress_entries)
            
            # Calculate user's progress percentage based on challenge type
            user_progress_percentage = 0
            if challenge.challenge_type == 0:  # Habit challenge
                try:
                    habit_challenge = challenge.habit_details
                    # For habit challenges, progress is based on frequency * duration
                    target_total = habit_challenge.frequency_per_week * habit_challenge.duration_weeks
                    user_progress_percentage = min(100, (total_progress / target_total) * 100) if target_total > 0 else 0
                except:
                    user_progress_percentage = 0
            elif challenge.challenge_type == 1:  # Target challenge
                try:
                    target_challenge = challenge.target_details
                    # For target challenges, progress is based on target value
                    user_progress_percentage = min(100, (total_progress / target_challenge.target_value) * 100) if target_challenge.target_value > 0 else 0
                except:
                    user_progress_percentage = 0
            
            participant_data.append({
                'id': participant.user.id,
                'display_name': participant.user.display_name,
                'role': participant.role,
                'state': participant.state,
                'joined_at': participant.joined_at,
                'total_progress': total_progress,
                'progress_percentage': round(user_progress_percentage, 2)
            })
        
        # Calculate time-based progress (how much of the challenge duration has elapsed)
        from datetime import datetime, timedelta
        now = datetime.now()
        created_at = challenge.created_at.replace(tzinfo=None)
        
        # Get challenge duration
        duration_days = 0
        if challenge.challenge_type == 0:  # Habit challenge
            try:
                habit_challenge = challenge.habit_details
                duration_days = habit_challenge.duration_weeks * 7
            except:
                duration_days = 28  # Default 4 weeks
        elif challenge.challenge_type == 1:  # Target challenge
            try:
                target_challenge = challenge.target_details
                duration_days = target_challenge.duration_days
            except:
                duration_days = 30  # Default 30 days
        
        end_date = created_at + timedelta(days=duration_days)
        
        # Calculate time-based progress percentage
        total_duration = (end_date - created_at).total_seconds()
        elapsed_time = (now - created_at).total_seconds()
        time_progress_percentage = min(100, max(0, (elapsed_time / total_duration) * 100)) if total_duration > 0 else 0
        
        # Check if user is participating
        user_participation = participants.filter(user=request.user).first()
        is_participating = user_participation is not None
        user_role = user_participation.role if user_participation else None
        user_state = user_participation.state if user_participation else None
        
        # Get exercise unit type and max rate for display
        exercise_unit_type = 'units'
        max_rate_per_minute = 100
        if challenge.challenge_type == 0:  # Habit challenge
            try:
                habit_challenge = challenge.habit_details
                exercise_unit_type = habit_challenge.exercise.unit_type
                max_rate_per_minute = float(habit_challenge.exercise.max_rate_per_minute)
            except:
                exercise_unit_type = 'units'
                max_rate_per_minute = 100
        elif challenge.challenge_type == 1:  # Target challenge
            try:
                target_challenge = challenge.target_details
                exercise_unit_type = target_challenge.exercise.unit_type
                max_rate_per_minute = float(target_challenge.exercise.max_rate_per_minute)
            except:
                exercise_unit_type = 'units'
                max_rate_per_minute = 100

        challenge_data = {
            'id': challenge.id,
            'title': challenge.title,
            'description': challenge.description,
            'challenge_type': challenge.challenge_type,
            'creator': {
                'id': challenge.creator.id,
                'display_name': challenge.creator.display_name
            },
            'participants': participant_data,
            'participant_count': participants.count(),
            'duration_days': duration_days,
            'created_at': challenge.created_at,
            'progress_percentage': round(time_progress_percentage, 2),
            'is_participating': is_participating,
            'user_role': user_role,
            'user_state': user_state,
            'days_remaining': max(0, (end_date - now).days),
            'exercise_unit_type': exercise_unit_type,
            'max_rate_per_minute': max_rate_per_minute
        }
        
        return success_response(data=challenge_data)


# ----------------------
# PROGRESS HISTORY
# ----------------------
class ChallengeProgressHistoryAPIView(APIView):
    """
    API endpoint to retrieve progress history for a specific challenge.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, challenge_id):
        try:
            challenge = Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return error_response("Challenge not found", status.HTTP_404_NOT_FOUND)
        
        # Check if user is participating in the challenge
        from .models import Participant, ParticipantState
        if not Participant.objects.filter(
            user=request.user, 
            challenge=challenge, 
            state=ParticipantState.ACTIVE
        ).exists():
            return error_response("Not participating in this challenge", status.HTTP_403_FORBIDDEN)
        
        # Get progress entries for this challenge
        progress_entries = ProgressEntry.objects.filter(
            challenge=challenge,
            user=request.user
        ).order_by('-logged_at')
        
        progress_data = []
        for entry in progress_entries:
            progress_data.append({
                'id': entry.id,
                'progress_value': entry.progress_value,
                'notes': entry.notes,
                'logged_at': entry.logged_at
            })
        
        return success_response(data={
            'challenge_id': challenge.id,
            'challenge_title': challenge.title,
            'progress_entries': progress_data,
            'total_entries': len(progress_data)
        })


# ----------------------
# USER CHALLENGES
# ----------------------
class UserChallengesAPIView(APIView):
    """
    API endpoint to retrieve challenges the user is participating in.
    Can filter by participation status and returns a paginated response.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        participation_status = request.query_params.get('status')
        
        # Get challenges where the user is a participant
        from .models import Participant, ParticipantState
        participant_queryset = Participant.objects.filter(user=request.user)
        
        if participation_status:
            participant_queryset = participant_queryset.filter(state=participation_status)
        
        # Get the challenges from the participants
        challenge_ids = participant_queryset.values_list('challenge_id', flat=True)
        qs = Challenge.objects.filter(id__in=challenge_ids, is_deleted=False)

        qs = qs.order_by('created_at', 'id')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ChallengeSerializer(page, many=True)
        paginated_response = paginator.get_paginated_response(serializer.data)
        
        # Wrap the paginated response in our custom format
        return success_response(data=paginated_response.data)


# ----------------------
# CHALLENGE ANALYTICS
# ----------------------
class ChallengeAnalyticsAPIView(APIView):
    """
    API endpoint to retrieve analytics for a specific challenge.
    Only accessible by participants or staff.
    Supports filtering by date range and limiting top users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, challenge_id):
        challenge = get_object_or_404(Challenge, id=challenge_id, is_deleted=False)

        # Permission check: either participant or staff
        is_participant = Participant.objects.filter(user=request.user, challenge=challenge).exists()
        if not (is_participant or request.user.is_staff):
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)

        start_date = parse_optional_date(request.query_params.get('start_date'))
        end_date = parse_optional_date(request.query_params.get('end_date'))

        if start_date and end_date and start_date > end_date:
            return error_response("start_date cannot be after end_date")

        top_n = int(request.query_params.get("top_n", 10))

        analytics = ChallengeService.get_challenge_analytics(
            challenge=challenge,
            start_date=start_date,
            end_date=end_date
        )

        analytics['progress']['per_user'] = analytics['progress']['per_user'][:top_n]
        analytics['filter'] = {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "top_n": top_n
        }

        return success_response(data=analytics)


# ----------------------
# ADMIN API
# ----------------------
class AdminUserSearchAPIView(APIView):
    """
    API endpoint for admin to search users.
    Only accessible by staff users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        search_query = request.query_params.get('q', '')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Search users by email or display name
        users = User.objects.all()
        if search_query:
            users = users.filter(
                models.Q(email__icontains=search_query) | 
                models.Q(display_name__icontains=search_query)
            )
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size
        users_page = users[start:end]
        
        user_data = []
        for user in users_page:
            user_data.append({
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'role': user.get_role_display(),
                'created_at': user.created_at,
                'is_active': user.is_active,
                'city': user.city,
                'country': user.country,
            })
        
        return success_response(data={
            'users': user_data,
            'total': users.count(),
            'page': page,
            'page_size': page_size,
            'has_next': end < users.count(),
            'has_previous': page > 1
        })


class AdminUserDetailAPIView(APIView):
    """
    API endpoint for admin to view detailed user information.
    Only accessible by staff users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response("User not found", status.HTTP_404_NOT_FOUND)
        
        # Get user's challenges
        user_challenges = Challenge.objects.filter(participants__user=user).distinct()
        challenge_data = []
        for challenge in user_challenges:
            participation = challenge.participants.filter(user=user).first()
            challenge_data.append({
                'id': challenge.id,
                'title': challenge.title,
                'status': challenge.status,
                'role': participation.get_role_display() if participation else 'Unknown',
                'state': participation.get_state_display() if participation else 'Unknown',
                'joined_at': participation.joined_at if participation else None,
            })
        
        # Get user's progress entries
        progress_entries = ProgressEntry.objects.filter(user=user).order_by('-logged_at')[:10]
        progress_data = []
        for entry in progress_entries:
            progress_data.append({
                'id': entry.id,
                'challenge_title': entry.challenge.title,
                'progress_value': entry.progress_value,
                'notes': entry.notes,
                'logged_at': entry.logged_at,
            })
        
        return success_response(data={
            'user': {
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'role': user.get_role_display(),
                'created_at': user.created_at,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'city': user.city,
                'country': user.country,
                'latitude': float(user.latitude) if user.latitude else None,
                'longitude': float(user.longitude) if user.longitude else None,
            },
            'challenges': challenge_data,
            'recent_progress': progress_data
        })

    def delete(self, request, user_id):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response("User not found", status.HTTP_404_NOT_FOUND)
        
        # Prevent admin from deleting themselves
        if user.id == request.user.id:
            return error_response("Cannot delete your own account", status.HTTP_400_BAD_REQUEST)
        
        # Check if user has active challenges
        active_participations = Participant.objects.filter(user=user, state='active')
        if active_participations.exists():
            return error_response("Cannot delete user with active challenge participations", status.HTTP_400_BAD_REQUEST)
        
        user.delete()
        return success_response(message="User deleted successfully")


class AdminExerciseManagementAPIView(APIView):
    """
    API endpoint for admin to manage exercises.
    Only accessible by staff users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        exercises = Exercise.objects.all().order_by('name')
        serializer = ExerciseSerializer(exercises, many=True)
        return success_response(data=serializer.data)

    def post(self, request):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        serializer = ExerciseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exercise = serializer.save()
        return success_response(
            data=ExerciseSerializer(exercise).data,
            code=status.HTTP_201_CREATED
        )

    def put(self, request, exercise_id):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        try:
            exercise = Exercise.objects.get(id=exercise_id)
        except Exercise.DoesNotExist:
            return error_response("Exercise not found", status.HTTP_404_NOT_FOUND)
        
        serializer = ExerciseSerializer(exercise, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_exercise = serializer.save()
        return success_response(data=ExerciseSerializer(updated_exercise).data)

    def delete(self, request, exercise_id):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        try:
            exercise = Exercise.objects.get(id=exercise_id)
        except Exercise.DoesNotExist:
            return error_response("Exercise not found", status.HTTP_404_NOT_FOUND)
        
        # Check if exercise is being used in any challenges
        if exercise.habit_challenges.exists() or exercise.target_challenges.exists():
            return error_response("Cannot delete exercise that is being used in challenges", status.HTTP_400_BAD_REQUEST)
        
        exercise.delete()
        return success_response(message="Exercise deleted successfully")


class AdminChallengeManagementAPIView(APIView):
    """
    API endpoint for admin to manage challenges.
    Only accessible by staff users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        search_query = request.query_params.get('q', '')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Search challenges by title or description
        challenges = Challenge.objects.all()
        if search_query:
            challenges = challenges.filter(
                models.Q(title__icontains=search_query) | 
                models.Q(description__icontains=search_query)
            )
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size
        challenges_page = challenges[start:end]
        
        challenge_data = []
        for challenge in challenges_page:
            # Get participant count
            participant_count = challenge.participants.count()
            
            challenge_data.append({
                'id': challenge.id,
                'title': challenge.title,
                'description': challenge.description,
                'status': challenge.status,
                'challenge_type': challenge.get_challenge_type_display(),
                'created_at': challenge.created_at,
                'participant_count': participant_count,
                'owner': {
                    'id': challenge.creator.id,
                    'email': challenge.creator.email,
                    'display_name': challenge.creator.display_name,
                } if challenge.creator else None,
            })
        
        return success_response(data={
            'challenges': challenge_data,
            'total': challenges.count(),
            'page': page,
            'page_size': page_size,
            'has_next': end < challenges.count(),
            'has_previous': page > 1
        })

    def delete(self, request, challenge_id):
        if not request.user.is_staff:
            return error_response("Not authorized", status.HTTP_403_FORBIDDEN)
        
        try:
            challenge = Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return error_response("Challenge not found", status.HTTP_404_NOT_FOUND)
        
        # Remove all participants from the challenge first
        participants = challenge.participants.all()
        participant_count = participants.count()
        
        if participant_count > 0:
            # Remove all participants
            participants.delete()
        
        # Now delete the challenge
        challenge.delete()
        
        message = f"Challenge deleted successfully. Removed {participant_count} participant(s)."
        return success_response(message=message)


# ----------------------
# WEATHER API
# ----------------------
class LocationUpdateAPIView(APIView):
    """
    API endpoint to update user's location information.
    Accepts city, country, latitude, and longitude.
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(csrf_exempt)
    def post(self, request):
        user = request.user
        city = request.data.get('city')
        country = request.data.get('country')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        if not city:
            return error_response('City is required')

        # Update user location
        user.city = city
        user.country = country or ''
        if latitude is not None:
            user.latitude = latitude
        if longitude is not None:
            user.longitude = longitude
        user.save()

        return success_response(
            data={
                'city': user.city,
                'country': user.country,
                'latitude': float(user.latitude) if user.latitude else None,
                'longitude': float(user.longitude) if user.longitude else None
            },
            message='Location updated successfully'
        )


class WeatherForecastAPIView(APIView):
    """
    API endpoint to get weather forecast for user's location or a specific location.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        location = request.query_params.get('location')
        latitude = request.query_params.get('lat')
        longitude = request.query_params.get('lon')
        
        # If coordinates provided, use them directly
        if latitude and longitude:
            try:
                lat = float(latitude)
                lon = float(longitude)
                weather_data = WeatherService.get_weather_forecast(lat, lon)
            except ValueError:
                return error_response('Invalid latitude or longitude values')
        # If location string provided, use geocoding
        elif location:
            weather_data = WeatherService.get_weather_by_location(location)
        # If no location provided, use user's saved location
        else:
            user = request.user
            if not user.city:
                return error_response('No location provided and user has no saved location')
            
            location = f"{user.city}, {user.country}" if user.country else user.city
            weather_data = WeatherService.get_weather_by_location(location)
        
        if not weather_data:
            return error_response('Unable to fetch weather data for the specified location')

        return success_response(data=weather_data)


class LocationSearchAPIView(APIView):
    """
    API endpoint to search for locations using geocoding.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q')
        if not query:
            return error_response('Query parameter "q" is required')

        # Geocode the location
        geocoded = WeatherService.geocode_location(query)
        
        if not geocoded:
            return error_response('Location not found')

        return success_response(data=geocoded)
