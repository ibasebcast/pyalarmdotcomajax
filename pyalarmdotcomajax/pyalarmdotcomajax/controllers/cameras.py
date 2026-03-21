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

    _resource_url_override = "video/devices/cameras"
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
                    log.debug("Camera list fetch: HTTP %s from %s", rsp.status, url)
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

        log.debug(
            "Camera controller refreshed. Items: %s",
            [f"{getattr(x, 'id', None)}:{getattr(x, 'name', None)}" for x in self.items],
        )

    async def get_live_stream_info(self, id: str) -> dict[str, Any] | None:
        """Fetch live WebRTC stream information for a camera.

        Returns a dict with ICE server config and WebRTC connection attributes
        from the endToEndWebrtcConnectionInfo included resource, or None if
        the stream info could not be retrieved.
        """
        url = f"{API_URL_BASE}video/videoSources/liveVideoHighestResSources/{id}"
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
                    log.debug("Live stream info fetch: HTTP %s for camera %s", rsp.status, id)
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

            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            included = payload.get("included", []) if isinstance(payload, dict) else []

            top_attrs = data.get("attributes", {})
            ice_servers_str = top_attrs.get("iceServers")
            ice_servers = json.loads(ice_servers_str) if ice_servers_str else []

            for inc in included:
                if inc.get("type") == "video/videoSources/endToEndWebrtcConnectionInfo":
                    config = inc.get("attributes", {})
                    config["iceServers"] = ice_servers
                    return config

            log.warning("No endToEndWebrtcConnectionInfo found in live stream response for camera %s", id)
            return None

        return None

    async def send_webrtc_offer(self, id: str, sdp_offer: str) -> str | None:
        """Send a WebRTC SDP offer for a camera stream and return the SDP answer.

        This is the second step of the WebRTC handshake after get_live_stream_info()
        provides ICE server configuration. The SDP offer should be generated by the
        caller (e.g. using aiortc or the HA WebRTC helpers) and this method exchanges
        it with Alarm.com for an SDP answer to complete the peer connection setup.

        Args:
            id: Camera device ID.
            sdp_offer: Local SDP offer string from the WebRTC peer connection.

        Returns:
            Remote SDP answer string, or None if the exchange failed.

        Note:
            The exact endpoint and request/response structure for Alarm.com's WebRTC
            offer/answer exchange has not yet been confirmed. This method is a stub
            and will need to be completed once the endpoint is identified.
            Candidate endpoint: POST video/videoSources/webRtcSessions/{id}

        """
        # TODO: Confirm ADC WebRTC offer/answer endpoint and request body structure.
        # Expected flow:
        #   POST {API_URL_BASE}video/videoSources/webRtcSessions/{id}
        #   Body: {"data": {"type": "video/videoSources/webRtcSession", "attributes": {"sdpOffer": sdp_offer}}}
        #   Response: included resource with type "video/videoSources/webRtcSession" containing "sdpAnswer"
        raise NotImplementedError(
            "WebRTC offer/answer exchange endpoint not yet confirmed. "
            "See method docstring for details."
        )

    async def get_snapshot_url(self, id: str) -> str | None:
        """Fetch a still image snapshot URL for a camera.

        Returns a URL pointing to the most recent snapshot JPEG for the given
        camera, suitable for use as HA's camera_image source.

        Args:
            id: Camera device ID.

        Returns:
            URL string of the snapshot image, or None if unavailable.

        Note:
            The exact Alarm.com snapshot endpoint has not yet been confirmed.
            This method is a stub and will need to be completed once the
            endpoint is identified.
            Candidate endpoint: GET video/cameras/{id}/snapshot
                             or GET video/devices/cameras/{id}/latestImage

        """
        # TODO: Confirm ADC snapshot/still-image endpoint.
        # Expected flow:
        #   GET {API_URL_BASE}video/cameras/{id}/snapshot  (or similar)
        #   Response: redirect or JSON with {"data": {"attributes": {"imageUrl": "https://..."}}}
        raise NotImplementedError(
            "Camera snapshot endpoint not yet confirmed. "
            "See method docstring for details."
        )
