"""Alarm.com controller for cameras."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from pyalarmdotcomajax.const import API_URL_BASE, ResponseTypes
from pyalarmdotcomajax.controllers.base import BaseController
from pyalarmdotcomajax.exceptions import (
    AuthenticationFailed,
    ServiceUnavailable,
    UnexpectedResponse,
)
from pyalarmdotcomajax.models.base import ResourceType
from pyalarmdotcomajax.models.camera import Camera
from pyalarmdotcomajax.models.jsonapi import Resource

from .base import device_controller

log = logging.getLogger(__name__)


@device_controller(ResourceType.CAMERA, Camera)
class CameraController(BaseController[Camera]):
    """Controller for cameras."""

    _resource_url_override = "video/devices/cameras"
    _is_device_controller = True

    def _device_filter(
        self, data: list[Resource] | Resource
    ) -> list[Resource] | Resource:
        """Return all supported cameras reported by the Alarm.com endpoint."""
        log.warning("=== CAMERA _device_filter RAW DATA === %s", data)
        return data

    async def _refresh(
        self,
        pre_fetched: list[Resource] | None = None,
        resource_id: str | None = None,
    ) -> None:
        """Refresh controller with extra logging.

        If the bridge passes an empty prefetched list, force a direct fetch from the
        camera endpoint instead of accepting the empty cache.
        """
        log.warning(
            "=== CAMERA _refresh called === pre_fetched=%s resource_id=%s target_ids=%s",
            pre_fetched,
            resource_id,
            getattr(self, "_target_device_ids", None),
        )

        if pre_fetched == []:
            log.warning(
                "=== CAMERA forcing direct endpoint fetch because pre_fetched was empty ==="
            )
            pre_fetched = None

        await super()._refresh(pre_fetched=pre_fetched, resource_id=resource_id)
        log.warning("=== CAMERA CONTROLLER ITEMS AFTER REFRESH === %s", self.items)

    async def get_live_stream_info(self, id: str) -> dict[str, Any]:
        """Fetch live WebRTC stream information for a camera."""

        if not self.get(id):
            raise UnexpectedResponse(f"Camera {id} not found in controller cache.")

        url = f"{API_URL_BASE}video/videoSources/liveVideoHighestResSources/{id}"
        text_rsp = ""

        for attempt in range(2):
            try:
                async with self._bridge.create_request(
                    "get",
                    url,
                    accept_types=ResponseTypes.JSON,
                    use_ajax_key=True,
                ) as rsp:
                    text_rsp = await rsp.text()
                    log.warning("=== CAMERA STREAM RAW RESPONSE === %s", text_rsp)
                    rsp.raise_for_status()
                    payload = json.loads(text_rsp)
            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403) and attempt == 0:
                    await self._bridge.login()
                    continue
                raise ServiceUnavailable(
                    f"Failed to fetch camera stream info for {id}. HTTP {err.status}."
                ) from err
            except json.JSONDecodeError as err:
                raise UnexpectedResponse(
                    f"Camera stream info response was not valid JSON: {text_rsp[:500]}"
                ) from err
            except AuthenticationFailed:
                if attempt == 0:
                    await self._bridge.login()
                    continue
                raise

            data = payload.get("data") if isinstance(payload, dict) else None
            attrs = data.get("attributes") if isinstance(data, dict) else None
            if not isinstance(attrs, dict):
                raise UnexpectedResponse(
                    f"Camera stream info response missing attributes payload: {text_rsp[:500]}"
                )

            required_keys = (
                "signallingServerUrl",
                "signallingServerToken",
                "cameraAuthToken",
            )
            if not all(attrs.get(key) for key in required_keys):
                raise UnexpectedResponse(
                    f"Camera stream info response missing required token fields: {text_rsp[:500]}"
                )

            return attrs

        raise ServiceUnavailable(f"Failed to fetch camera stream info for {id}.")
