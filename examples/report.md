## Acceptance criteria coverage

**3/5 mapped to code and tests** · 1 code only · 0 tests only · 1 unmapped

| ID | Status | Criterion | Code | Tests |
|----|--------|-----------|------|-------|
| AC-1 | ✅ MAPPED | After 5 failed login attempts from the same IP within 15 minutes, `POST /login` returns H… | `app/auth.py:14` `login`<br>`app/ratelimit.py:1`<br>`app/ratelimit.py:6` `FailedLoginLimiter` | `tests/test_auth.py:10` `test_login_returns_429_after_five_failed_attempts` |
| AC-2 | ✅ MAPPED | The 429 response includes a `Retry-After` header with the seconds until the window resets | `app/auth.py:15` `login`<br>`app/auth.py:14` `login`<br>`app/ratelimit.py:9` `__init__` | `tests/test_auth.py:21` `test_429_response_has_retry_after_header` |
| AC-3 | ✅ MAPPED | A successful login resets the failed-attempt counter for that IP | `app/ratelimit.py:1`<br>`app/auth.py:14` `login`<br>`app/auth.py:20` `login` | `tests/test_auth.py:24` `test_successful_login_resets_failed_attempts`<br>`tests/test_auth.py:10` `test_login_returns_429_after_five_failed_attempts` |
| AC-4 | 🟡 CODE-ONLY | The limit and window are configurable via `LOGIN_MAX_ATTEMPTS` and `LOGIN_WINDOW_SECONDS` | `app/auth.py:8`<br>`app/settings.py:5`<br>`app/settings.py:6` | — |
| AC-5 | ❌ UNMAPPED | Every lockout is written to the audit log with the IP and a timestamp | — | — |

### Unmapped criteria

- **AC-5** Every lockout is written to the audit log with the IP and a timestamp — no changed line matched (terms: lockout, written, audit, log, ip, timestamp)

<details><summary>Evidence</summary>

**AC-1** After 5 failed login attempts from the same IP within 15 minutes, `POST /login` returns HTTP 429

- code `app/auth.py:14` — `return Response(429, {"error": "too many failed login attempts"},` (failed, login, attempts, 429)
- code `app/ratelimit.py:1` — `"""Sliding-window counter of failed login attempts per client IP."""` (failed, login, attempts, ip)
- code `app/ratelimit.py:6` — `class FailedLoginLimiter:` (failed, login)
- test `tests/test_auth.py:10` — `def test_login_returns_429_after_five_failed_attempts():` (failed, login, attempts, 429, ip)

**AC-2** The 429 response includes a `Retry-After` header with the seconds until the window resets

- code `app/auth.py:15` — `headers={"Retry-After": str(limiter.retry_after(ip))})` (literal; retry, header)
- code `app/auth.py:14` — `return Response(429, {"error": "too many failed login attempts"},` (429, response)
- code `app/ratelimit.py:9` — `self.window_seconds = window_seconds` (seconds, window)
- test `tests/test_auth.py:21` — `assert int(resp.headers["Retry-After"]) > 0` (literal; 429, response, retry, header)

**AC-3** A successful login resets the failed-attempt counter for that IP

- code `app/ratelimit.py:1` — `"""Sliding-window counter of failed login attempts per client IP."""` (login, failed, attempt, counter, ip)
- code `app/auth.py:14` — `return Response(429, {"error": "too many failed login attempts"},` (login, failed, attempt)
- code `app/auth.py:20` — `limiter.reset(ip)` (resets, ip)
- test `tests/test_auth.py:24` — `def test_successful_login_resets_failed_attempts():` (successful, login, resets, failed, attempt, ip)
- test `tests/test_auth.py:10` — `def test_login_returns_429_after_five_failed_attempts():` (login, failed, attempt, ip)

**AC-4** The limit and window are configurable via `LOGIN_MAX_ATTEMPTS` and `LOGIN_WINDOW_SECONDS`

- code `app/auth.py:8` — `limiter = FailedLoginLimiter(settings.LOGIN_MAX_ATTEMPTS, settings.LOGIN_WINDOW_SECONDS)` (literal; limit, window, login, max, attempts, seconds)
- code `app/settings.py:5` — `LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))` (literal; login, max, attempts)
- code `app/settings.py:6` — `LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "900"))` (literal; window, login, seconds)

</details>

<sub>acceptmap 0.1.0 · heuristic term matching; review before relying on it.</sub>
