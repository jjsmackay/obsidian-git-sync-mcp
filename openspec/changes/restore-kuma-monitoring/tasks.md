# Tasks

> Depends on `surface-stage-failures`. Do not start group 2 until that change has
> landed — task 2.2 reads the degraded flag it introduces.

## 1. Git-sync heartbeat config

- [ ] 1.1 Add `VAULT_GIT_HEARTBEAT_INTERVAL` (default `60`) to `config.py` as a
  raw env string with a module docstring comment matching the file's existing
  style, plus a `heartbeat_interval()` accessor; verify by importing the module
  with the variable unset and asserting the accessor returns 60
- [ ] 1.2 Extend `validate_gitsync()` to parse-and-check the interval as a
  positive integer, failing closed; verify with unit tests covering a
  non-integer value, a zero/negative value, and the unset default

## 2. Git-sync heartbeat trigger

- [ ] 2.1 Move the beat out of the `push.ok` branch in `_push_once()` and into
  the end of the push cycle, gated on a remote being configured and nothing
  being left unpushed; verify with unit tests asserting a beat after a
  successful push and no beat after a failed push
- [ ] 2.2 Make an idle cycle (remote configured, nothing unpushed, early return)
  eligible to beat, but only while the worker is not degraded; verify with unit
  tests that a clean idle worker pings and that a degraded one does not ping
  despite owing nothing to the remote
- [ ] 2.3 Verify the beat resumes after recovery; unit-test that a degraded
  worker which then completes a clean cycle pings again
- [ ] 2.4 Add the monotonic cadence floor using `heartbeat_interval()`; verify
  with unit tests that several eligible cycles inside one interval produce
  exactly one ping, that the first eligible cycle pings immediately, and that an
  interval of only-ineligible cycles produces none
- [ ] 2.5 Confirm commit-only mode still never beats; verify with a unit test
  that a worker configured with no remote never pings regardless of the URL
- [ ] 2.6 Run the full suite with `uv run --extra dev python -m pytest` and
  verify it passes with no regressions in the existing heartbeat tests

## 3. Sidecar heartbeat

- [ ] 3.1 Add `obsidian-sync/report.sh` — runs `healthcheck`, captures its exit
  code and output, emits the output, pings only on success, and exits with the
  captured code; verify by running it with no heartbeat URL set and confirming
  the output and exit code match `healthcheck` run alone
- [ ] 3.2 Implement the ping as a `node -e` one-liner with no redirect
  following, a bounded read, a short timeout, and host-only error reporting;
  verify against a local listener that a 302 is not followed and that an
  unreachable endpoint prints no URL
- [ ] 3.3 Install `report.sh` as `/usr/local/bin/report` in the sidecar
  `Dockerfile` (mode 0755, alongside the existing scripts) and point
  `HEALTHCHECK` at it, raising `--timeout` to leave clear margin above the ping
  timeout; verify `docker build` succeeds and `docker inspect` shows the new
  test and timeout
- [ ] 3.4 Confirm `healthcheck.sh` is unchanged and still network-free; verify
  `git diff` touches no line of it and that running `healthcheck` by hand emits
  no beat
- [ ] 3.5 Pass `SYNC_HEARTBEAT_URL` through to the `obsidian-sync` service in
  `docker-compose.yml` with a comment explaining it is optional; verify
  `docker compose --profile obsidian config` resolves the variable

## 4. Verification against a live monitor

- [ ] 4.1 Verify the sidecar path end to end against a local HTTP listener: a
  fresh sync log produces one request per healthcheck interval, and touching the
  freshness window so the check fails stops the requests while the container's
  health output still names the age and threshold
- [ ] 4.2 Verify reporting cannot flip the verdict: point the heartbeat at a
  closed port and at a hanging listener, and confirm the container stays healthy
  in both cases and the check completes inside the healthcheck timeout

## 5. Documentation

- [ ] 5.1 Add `VAULT_GIT_HEARTBEAT_INTERVAL` to `.env.example` and update the
  `VAULT_GIT_HEARTBEAT_URL` comment to describe the new beat semantics; verify
  every `VAULT_GIT_*` name the code reads appears there
- [ ] 5.2 Add `VAULT_MCP_HEARTBEAT_URL` and `VAULT_MCP_HEARTBEAT_INTERVAL` to
  `.env.example` in the upstream section, attributed to the upstream server
  rather than to this package; verify the attribution is explicit in the comment
- [ ] 5.3 Update the README monitoring section from four layers to five, adding
  the sidecar heartbeat and stating how it relates to the sidecar healthcheck
  (same signal, same cadence, one reports into Docker and the other reaches
  outside it); verify all five layers are distinguished
- [ ] 5.4 Document, for each of the three heartbeats, its variable, what a beat
  asserts and what silence means; include the reachability caveat (the container
  must be able to reach the endpoint, so a monitor behind an authenticating
  proxy needs its internal address) and the capability-URL warning; verify each
  point is present
- [ ] 5.5 Document `SYNC_HEARTBEAT_URL` in `obsidian-sync/README.md` alongside
  the existing health section, including that an un-bootstrapped sidecar never
  beats by design; verify the section names the variable and the default-off
  behaviour
- [ ] 5.6 Note in the README that automatic recovery from a stalled sidecar
  remains out of scope and what an operator would need to add; verify the
  existing "detection is not recovery" wording still reads correctly next to the
  new heartbeat

## 6. Deployment (operator step, outside the repo)

- [ ] 6.1 Set the three heartbeat URLs in the deployment's environment file
  using the monitor's internal address, never the public one, and never in
  committed configuration; verify each monitor goes green after a restart
- [ ] 6.2 Verify each monitor alerts on silence: stop the sidecar and confirm
  its monitor goes down within its configured interval and retries
