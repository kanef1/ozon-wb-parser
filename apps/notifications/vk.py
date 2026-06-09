import logging
import random

from django.conf import settings

logger = logging.getLogger(__name__)


class VKNotifier:
    """Отправка сообщений от имени VK-сообщества через messages.send.

    Требует:
      - VK_COMMUNITY_TOKEN — токен доступа сообщества (с правами messages)
      - VK_GROUP_ID — ID сообщества (без минуса)

    Ограничение VK: пользователь должен разрешить сообщения от сообщества
    (нажать «Разрешить» при первом контакте). Если разрешения нет — API
    вернёт ошибку 901, которую мы логируем и не ретраим.
    """

    # Коды ошибок VK, при которых ретрай бессмысленен
    _NO_RETRY_CODES = {
        901,   # Can't send messages for users without permission
        902,   # Can't send messages to this user due to their privacy settings
        18,    # User was deleted or banned
    }

    def __init__(self) -> None:
        self._token: str = settings.VK_COMMUNITY_TOKEN
        if not self._token:
            raise RuntimeError(
                "VK_COMMUNITY_TOKEN не задан. Добавьте его в .env"
            )

    def send_message(
        self,
        vk_user_id: int,
        text: str,
        random_id: int | None = None,
    ) -> bool:
        """Отправить личное сообщение пользователю от имени сообщества.

        Args:
            vk_user_id: VK ID получателя.
            text: Текст сообщения.
            random_id: Seed дедупликации VK (None → случайный int).

        Returns:
            True при успехе.

        Raises:
            VKPermissionError: если пользователь не разрешил сообщения.
            vk_api.exceptions.ApiError: любые другие ошибки API.
        """
        import vk_api
        from vk_api.exceptions import ApiError

        session = vk_api.VkApi(token=self._token)
        vk = session.get_api()

        rid = random_id if random_id is not None else random.randint(1, 2 ** 31)

        try:
            vk.messages.send(
                user_id=vk_user_id,
                message=text,
                random_id=rid,
            )
        except ApiError as exc:
            error_code = exc.error.get("error_code", 0)
            if error_code in self._NO_RETRY_CODES:
                logger.warning(
                    "VK: no permission to message user_id=%d (code %d). "
                    "User must allow messages from the community.",
                    vk_user_id, error_code,
                )
                raise VKPermissionError(vk_user_id, error_code) from exc
            raise

        logger.info("VK message sent to user_id=%d", vk_user_id)
        return True


class VKPermissionError(Exception):
    """Пользователь не разрешил сообщения от сообщества."""

    def __init__(self, vk_user_id: int, error_code: int) -> None:
        self.vk_user_id = vk_user_id
        self.error_code = error_code
        super().__init__(f"VK user {vk_user_id} blocked messages (code {error_code})")
