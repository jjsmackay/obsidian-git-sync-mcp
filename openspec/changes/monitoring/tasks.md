## 1. Config

- [ ] 1.1 Add `VAULT_GITSYNC_HEARTBEAT_URL` (raw string, default empty = disabled) + a `heartbeat_url()` accessor
- [ ] 1.2 Extend `validate_gitsync()` (enabled only): when the heartbeat URL is non-empty it must be an http(s) URL with a host; fail closed otherwise (mirror upstream `validate_heartbeat` scheme/host check; never echo the URL)

## 2. Ping helper

- [ ] 2.1 Add `heartbeat.py` porting the upstream ping discipline: a no-redirect `urllib` opener, single GET, `read(<small cap>)`, short timeout, log host + exception type only (never the URL). One `ping(url)` function, fail-soft (never raises)

## 3. Worker integration

- [ ] 3.1 The worker holds the configured heartbeat URL (via `from_config`); on `push.ok` in `_push_once`, call `heartbeat.ping(url)` when a URL is configured
- [ ] 3.2 No ping on failed push or in commit-only mode (no remote → no push path)

## 4. Deployment surface

- [ ] 4.1 Add `VAULT_GITSYNC_HEARTBEAT_URL` to `.env.example` (disabled by default, one-line comment)

## 5. Tests

- [ ] 5.1 Successful push fires exactly one ping to the configured URL (monkeypatch `heartbeat.ping` / the opener; assert called with the URL)
- [ ] 5.2 Failed push fires no ping; commit-only mode fires no ping
- [ ] 5.3 No URL configured → never pings
- [ ] 5.4 `ping` follows no redirects and reads only a bounded amount (test against a tiny local handler or a mocked opener); a failing endpoint is swallowed (no raise)
- [ ] 5.5 `validate_gitsync()` rejects a non-http(s) heartbeat URL when enabled; empty URL is valid

## 6. Validation

- [ ] 6.1 `openspec validate monitoring --strict`
- [ ] 6.2 `uv run pytest` green (all prior + new)
