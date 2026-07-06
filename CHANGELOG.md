## 2026.7.6

### Fixed
- **Periodic "safety net" full-state refresh was a silent no-op** (ha-alarmdotcom#42, misreported as "Smart arming breaks the integration"): `fetch_full_state()` calls each resource controller's `initialize()`, which returns immediately if the controller has already been initialized once — which every controller has been, after the integration's initial startup. So any code calling `fetch_full_state()` a second time (e.g. a periodic poll meant to catch state missed by a dropped WebSocket event) did nothing at all: no error, no log line, no refreshed state. If a WebSocket event was ever missed — during a reconnect, a brief drop, or any other transient blip — state could stay stale indefinitely, correcting only on a full integration reload. This affected any state change, not just "smart arming": manual arm/disarm from the Alarm.com app or even from Home Assistant itself could go unreflected once this occurred. Added `refresh_all_resources()`, a new bridge method that calls each controller's `_refresh()` directly (the same mechanism already used when the WebSocket reconnects), bypassing the one-time `initialize()` guard so it can safely be called repeatedly.

---

## 2026.7.5

### Fixed
- **OTP still fails after 2026.5.3 (reopened #1 / ha-alarmdotcom#21)** — fix contributed by @jsight in #2. Two compounding bugs, not one:
  1. **The 5.3 "fix" was actually a regression.** It moved the MFA-cookie check to run immediately after `verifyTwoFactorCode`, *before* `trustTwoFactorDevice` — but Alarm.com reliably sets the `twoFactorAuthenticationId` cookie on the *trust* response, not the verify response. Since Home Assistant's config flow always supplies a device name, this made the "Could not find MFA cookie" failure happen on every single login instead of intermittently. Fix: `trustTwoFactorDevice` now always runs (best-effort, wrapped in try/except) when a device name is provided, and the cookie is checked only after both requests have had a chance to set it.
  2. **Cookie capture itself was unreliable.** aiohttp follows redirects by default, and `ClientResponse.cookies` only exposes the `Set-Cookie` headers of the *last* response in a redirect chain — so a cookie set on an earlier hop could be invisible no matter when it was checked. Fix: `create_request` now falls back to the session's `cookie_jar` (which accumulates cookies across every hop) when the cookie isn't present on the immediate response.
- Thanks to @lwimble for independently confirming both root causes and testing an equivalent patch in production.

---

## 2026.5.3

### Fixed
- **OTP submission fails for SMS and email 2FA** (#1): After a successful `verifyTwoFactorCode` call, the MFA cookie (`twoFactorAuthenticationId`) is set by Alarm.com on that response. The previous code only checked for the cookie *after* the subsequent `trustTwoFactorDevice` call, so any exception from the trust step — or a response that didn't re-emit the already-set cookie — caused an `UnexpectedResponse` even though the OTP itself was accepted. Fix: the cookie is now checked immediately after `verifyTwoFactorCode`. If it's present there, the login continues regardless of what happens in the trust step.
- **Device trust registration failure silently breaks a successful OTP login**: The `trustTwoFactorDevice` POST is now wrapped in a `try/except` and treated as best-effort. If it fails (network error, Alarm.com rejecting the device name, etc.), a warning is logged and the already-set MFA cookie is returned normally. The device will not be remembered across sessions, but the current login succeeds.
- **`submit_otp` returned `None` when `device_name` was not provided**: When called without a device name (skip device registration), the method returned `None` even though the MFA cookie was already set after a successful OTP verification. Callers that used the return value to store the cookie would silently receive nothing. Fix: the cookie value is now returned in all success paths.
- **`NotAuthorized` (423) from unsupported resource types crashes reconnect refresh** (#23 in ha-alarmdotcom): On websocket reconnect, each controller calls `_refresh()` to re-sync its state. For accounts that don't have image sensors (or other feature-gated resource types), Alarm.com returns a 423 status which propagated as an unhandled `NotAuthorized` exception. Because the event task was fire-and-forget, this appeared as `Task exception was never retrieved` in HA logs and repeated on every reconnect. Fix: `_base_handle_event` now catches `NotAuthorized` on the reconnect-triggered refresh and logs it at DEBUG level, so one unsupported controller no longer pollutes logs or crashes its task.

---

## 2026.4.22

Initial release of the ibasebcast fork of pyalarmdotcomajax.
