from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import UserProfile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("vk_user_id",)
        labels = {"vk_user_id": "VK User ID"}
        help_texts = {
            "vk_user_id": (
                "Ваш числовой ID ВКонтакте. Узнать его можно на vk.com/id0 "
                "или через vk.com/page-{группа}. Нужен для отправки уведомлений."
            )
        }
