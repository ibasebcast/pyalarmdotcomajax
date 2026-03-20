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

    _resource_url_override = "video/devices/cameras?filterByLiveViewDisplayable=true"
    _is_device_controller = True

    def _device_filter(
        self, data: list[Resource] | Resource
    ) -> list[Resource] | Resource:
        """Return all supported cameras reported by the Alarm.com endpoint."""
        return data

    async def _refresh(
        self,
        pre_fetched: list[Resource] | None = None,
        resource_id: str | None = None,
    ) -> None:
        """Refresh controller directly from the camera endpoint."""
        url = f"{API_URL_BASE}{self._resource_url_override}"
        text_rsp = ""

        for attempt in range(2):
            try:
                async with self._bridge.create_request(
                    "get",
                    url,
                    accept_types=ResponseTypes.JSON,
                    use_ajax_key=False,
                ) as rsp:
                    text_rsp = await rsp.text()
                    log.warning("=== CAMERA FETCH STATUS === %s", rsp.status)
                    log.warning("=== CAMERA FETCH URL === %s", url)
                    log.warning("=== CAMERA FETCH RAW RESPONSE === %s", text_rsp[:2000])
                    rsp.raise_for_status()
                    payload = json.loads(text_rsp)
                    break
            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403) and attempt == 0:
                    await self._bridge.login()
                    continue

                log.warning(
                    "Alarm.com camera list endpoint failed with HTTP %s, leaving camera controller empty.",
                    err.status,
                )
                self._resources.clear()
                return
            except json.JSONDecodeError:
                log.warning(
                    "Alarm.com camera list response was not valid JSON, leaving camera controller empty. Response: %s",
                    text_rsp[:500],
                )
                self._resources.clear()
                return
            except AuthenticationFailed:
                if attempt == 0:
                    await self._bridge.login()
                    continue

                log.warning(
                    "Authentication failed while fetching camera list, leaving camera controller empty."
                )
                self._resources.clear()
                return
            except Exception as err:
                log.warning(
                    "Unexpected error while fetching camera list: %s. Leaving camera controller empty.",
                    err,
                )
                self._resources.clear()
                return
        else:
            log.warning(
                "Alarm.com camera list endpoint could not be fetched, leaving camera controller empty."
            )
            self._resources.clear()
            return

        data = payload.get("data") if isinstance(payload, dict) else None
        included = payload.get("included") if isinstance(payload, dict) else None

        if data is None:
            self._resources.clear()
            return

        filtered = self._device_filter(data)

        self._resources.clear()

        if isinstance(filtered, list):
            for item in filtered:
                try:
                    self._register_or_update_resource(item, included)
                except Exception as err:
                    log.error("Failed to register camera resource %s: %s", item, err)
        else:
            try:
                self._register_or_update_resource(filtered, included)
            except Exception as err:
                log.error("Failed to register camera resource %s: %s", filtered, err)

        log.warning(
            "=== CAMERA CONTROLLER ITEMS AFTER REFRESH === %s",
            [f"{getattr(x, 'id', None)}:{getattr(x, 'name', None)}" for x in self.items],
        )

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
                    rsp.raise_for_status()
                    payload = json.loads(text_rsp)
            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403) and attempt == 0:
                    await self._bridge.login()
                    continue
                raise UnexpectedResponse(
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

        raise UnexpectedResponse(f"Failed to fetch camera stream info for {id}.")
