import uuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    vk_user_id = models.BigIntegerField(
        null=True, blank=True, help_text="ID пользователя ВКонтакте для уведомлений"
    )
    # Токен для доступа к дашборду без логина — передаётся в VK-уведомлении
    dashboard_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self) -> str:
        return f"Профиль {self.user.username}"


@receiver(post_save, sender=User)
def create_profile(sender, instance: User, created: bool, **kwargs) -> None:
    """Автоматически создаёт профиль при регистрации пользователя."""
    if created:
        UserProfile.objects.create(user=instance)
