from django.urls import path, include

urlpatterns = [
    path("", include("apps.tracker.urls")),
    path("", include("apps.vkbot.urls")),
]
