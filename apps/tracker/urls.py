from django.urls import path
from . import views

app_name = "tracker"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("subscriptions/add/", views.subscription_add, name="subscription_add"),
    path("subscriptions/<int:pk>/edit/", views.subscription_edit, name="subscription_edit"),
    path("subscriptions/<int:pk>/delete/", views.subscription_delete, name="subscription_delete"),
    path("dashboard/<str:token>/", views.dashboard, name="dashboard"),
    path("dashboard/<str:token>/chart-data/<int:product_id>/", views.chart_data_api, name="chart_data"),
]
