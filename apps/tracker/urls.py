from django.urls import path
from . import views

app_name = "tracker"

urlpatterns = [
    path("dashboard/<str:token>/", views.dashboard, name="dashboard"),
    path("dashboard/<str:token>/chart-data/<int:product_id>/", views.chart_data_api, name="chart_data"),
]
