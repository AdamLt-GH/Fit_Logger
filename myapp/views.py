from django.shortcuts import render

# Create your views here.


# til_app/views.py
from django.http import HttpResponse
from django.template import loader


def index(request):
   return HttpResponse("Hello, world. You're at the index page of myapp - since we cant think of a name for it yet.")

def view_home(request):
    context = {"name": "ELEC3609", "week": 3}
    return render(request, 'home.html', context)

def page1(request):
    return render(request, 'page1.html')

def page2(request):
    return render(request, 'page2.html')
