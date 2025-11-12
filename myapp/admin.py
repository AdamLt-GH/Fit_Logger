from django.contrib import admin

# Register your models here.
from .models import Exercise, User, Challenge, HabitChallenge, TargetChallenge, Participant

# Register models to make them appear in Django admin
admin.site.register(Exercise)
admin.site.register(User)
admin.site.register(Challenge)
admin.site.register(HabitChallenge)
admin.site.register(TargetChallenge)
admin.site.register(Participant)