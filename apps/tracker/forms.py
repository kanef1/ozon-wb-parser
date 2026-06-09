from django import forms

from .models import Marketplace, UserSubscription


class SubscriptionAddForm(forms.Form):
    marketplace = forms.ChoiceField(
        choices=Marketplace.choices,
        label="Маркетплейс",
    )
    article = forms.CharField(
        max_length=64,
        label="Артикул / SKU",
        help_text="Числовой артикул товара (например: 12345678 для WB или 1234567890 для Ozon)",
    )
    target_price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        label="Порог цены (руб.)",
        help_text="Уведомить, когда цена упадёт ниже этого значения. Оставьте пустым, если не нужен.",
    )
    notify_on_any_drop = forms.BooleanField(
        required=False,
        label="Уведомлять при любом снижении",
        help_text="Присылать уведомление при каждом снижении, не только при достижении порога.",
    )

    def clean_article(self) -> str:
        article = self.cleaned_data["article"].strip()
        if not article.isdigit():
            raise forms.ValidationError("Артикул должен содержать только цифры.")
        return article


class SubscriptionEditForm(forms.ModelForm):
    class Meta:
        model = UserSubscription
        fields = ("target_price", "notify_on_any_drop", "is_active")
        labels = {
            "target_price": "Порог цены (руб.)",
            "notify_on_any_drop": "Уведомлять при любом снижении",
            "is_active": "Активна",
        }
