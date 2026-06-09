import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .tasks import handle_vk_event

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def callback(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponse("bad request", status=400)

    event_type = data.get("type")

    # VK требует подтверждения адреса сервера
    if event_type == "confirmation":
        code = getattr(settings, "VK_CONFIRMATION_CODE", "")
        return HttpResponse(code, content_type="text/plain")

    # Все прочие события обрабатываем асинхронно
    if event_type:
        handle_vk_event.delay(data)

    return HttpResponse("ok", content_type="text/plain")
