# Rate-limit failed logins (#118)

Credential-stuffing traffic is hitting `POST /login`. Slow it down per client IP.

## Acceptance criteria

- [ ] After 5 failed login attempts from the same IP within 15 minutes, `POST /login` returns HTTP 429
- [ ] The 429 response includes a `Retry-After` header with the seconds until the window resets
- [ ] A successful login resets the failed-attempt counter for that IP
- [ ] The limit and window are configurable via `LOGIN_MAX_ATTEMPTS` and `LOGIN_WINDOW_SECONDS`
- [ ] Every lockout is written to the audit log with the IP and a timestamp

## Out of scope

- Per-account lockouts
