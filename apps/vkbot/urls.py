from django.urls import path
from . import views

urlpatterns = [
    path("vkbot/callback/", views.callback, name="vkbot-callback"),
]
