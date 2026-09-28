# Spec Delta

## ADDED Requirements

### Requirement: Sidecar beats to a push monitor while sync is fresh

When a sidecar heartbeat URL is configured, the sidecar SHALL send a single GET
to it each time its sync-freshness check passes, and SHALL NOT send one when the
check fails. When no URL is configured, no heartbeat SHALL ever be sent. The URL
SHALL be supplied through an environment variable following the sidecar's
existing convention for its own settings, and SHALL be passed through by the
Compose service so an operator configures it the same way as every other
deployment value.

This gives the sync-freshness verdict — which otherwise reaches no further than
the container's Docker health state — a path to an external monitor. Silence
means the sidecar is wedged, stopped, un-bootstrapped, or its host is gone; a
push-style monitor treats all of those as down, which is correct in every case.
The beat rides the healthcheck's existing cadence, so no additional process or
timer is introduced.

#### Scenario: Fresh sync beats

- **WHEN** the freshness check passes and a heartbeat URL is configured
- **THEN** a single GET is sent to that URL

#### Scenario: Wedged sync goes silent

- **WHEN** the freshness check fails because the sync log has gone stale
- **THEN** no heartbeat is sent, so the monitor stops receiving beats

#### Scenario: Un-bootstrapped sidecar goes silent

- **WHEN** the sidecar has no configuration and therefore no sync log
- **THEN** no heartbeat is sent

#### Scenario: Disabled by default

- **WHEN** no heartbeat URL is configured
- **THEN** the sidecar behaves exactly as it does today and never sends a
  heartbeat

### Requirement: Health reporting never changes the health verdict

The reporting path SHALL exit with exactly the status the sync-freshness check
produced and SHALL preserve that check's output, so the container's health state
is decided by sync liveness alone. A heartbeat that fails — unreachable monitor,
DNS failure, timeout, error response — SHALL be swallowed and SHALL NOT make a
healthy sidecar report unhealthy. The freshness check itself SHALL remain free of
outbound network calls, so an operator can run it by hand as a pure diagnostic
without emitting a beat that misrepresents the sidecar's state.

#### Scenario: An unreachable monitor does not fail the container

- **WHEN** the freshness check passes but the heartbeat endpoint cannot be
  reached
- **THEN** the health verdict is still success, and the container stays healthy

#### Scenario: Running the check by hand sends no beat

- **WHEN** an operator runs the freshness check directly
- **THEN** it reports the age and threshold as before and no heartbeat is sent

#### Scenario: A failing check still reports its reason

- **WHEN** the freshness check fails
- **THEN** the reporting path exits non-zero and the output still names the
  observed age and the threshold

### Requirement: Sidecar heartbeat follows the safe ping discipline

The sidecar ping SHALL follow no redirects, read at most a small bounded number
of bytes of the response, and use a timeout short enough to complete within the
healthcheck's own timeout, so a hanging monitor can never stall the health
verdict. It SHALL never log the full URL — only the host and the error type —
because the URL may be a capability URL carrying a secret in its path. It SHALL
require no package beyond what the sidecar image already installs.

#### Scenario: Redirects are not followed

- **WHEN** the heartbeat URL responds with a redirect
- **THEN** the ping does not follow it to the redirect target

#### Scenario: A failure is logged without the URL

- **WHEN** the heartbeat endpoint is unreachable or errors
- **THEN** the failure is reported with the host and error type only, and the
  URL does not appear in the output

#### Scenario: A hanging monitor cannot stall the health verdict

- **WHEN** the heartbeat endpoint accepts the connection but never responds
- **THEN** the ping gives up in time for the health verdict to be reported
  within the healthcheck timeout

#### Scenario: No new package is installed

- **WHEN** the sidecar image is built
- **THEN** the heartbeat adds no package to the image
