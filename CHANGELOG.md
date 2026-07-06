## 2026.7.5

### Fixed


- **OTP "Failed to Connect" still occurring after 2026.5.3** (reopened #21): The 2026.5.3 fix in pyalarmdotcomajax turned out to be a regression, not a fix — it checked for the MFA cookie before trustTwoFactorDevice ran, but Alarm.com reliably sets that cookie on the trust response, not the verify response. Since HA's config flow always provides a device name, this made the failure happen on every login. There was also a second, independent bug: aiohttp only exposes cookies from the last response in a redirect chain, so the cookie could be invisible even when present in the redirect history. Both fixed upstream in pyalarmdotcomajax 2026.7.5 (contributed by @jsight, confirmed independently by @lwimble). Bumped dependency pin accordingly.

## 2026.5.3

### Fixed
- **OTP submission fails for SMS and email 2FA** (#1): After a successful `verifyTwoFactorCode` call, the MFA cookie (`twoFactorAuthenticationId`) is set by Alarm.com on that response. The previous code only checked for the cookie *after* the subsequent `trustTwoFactorDevice` call, so any exception from the trust step — or a response that didn't re-emit the already-set cookie — caused an `UnexpectedResponse` even though the OTP itself was accepted. Fix: the cookie is now checked immediately after `verifyTwoFactorCode`. If it's present there, the login continues regardless of what happens in the trust step.
- **Device trust registration failure silently breaks a successful OTP login**: The `trustTwoFactorDevice` POST is now wrapped in a `try/except` and treated as best-effort. If it fails (network error, Alarm.com rejecting the device name, etc.), a warning is logged and the already-set MFA cookie is returned normally. The device will not be remembered across sessions, but the current login succeeds.
- **`submit_otp` returned `None` when `device_name` was not provided**: When called without a device name (skip device registration), the method returned `None` even though the MFA cookie was already set after a successful OTP verification. Callers that used the return value to store the cookie would silently receive nothing. Fix: the cookie value is now returned in all success paths.
- **`NotAuthorized` (423) from unsupported resource types crashes reconnect refresh** (#23 in ha-alarmdotcom): On websocket reconnect, each controller calls `_refresh()` to re-sync its state. For accounts that don't have image sensors (or other feature-gated resource types), Alarm.com returns a 423 status which propagated as an unhandled `NotAuthorized` exception. Because the event task was fire-and-forget, this appeared as `Task exception was never retrieved` in HA logs and repeated on every reconnect. Fix: `_base_handle_event` now catches `NotAuthorized` on the reconnect-triggered refresh and logs it at DEBUG level, so one unsupported controller no longer pollutes logs or crashes its task.

---

## 2026.4.22

Initial release of the ibasebcast fork of pyalarmdotcomajax.
