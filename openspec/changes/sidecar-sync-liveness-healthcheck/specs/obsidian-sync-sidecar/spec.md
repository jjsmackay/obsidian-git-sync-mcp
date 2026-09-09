## ADDED Requirements

### Requirement: Healthcheck asserts current sync liveness

The sidecar image `HEALTHCHECK` SHALL report unhealthy when continuous sync has
stopped making progress, including the case where the `ob` process is still
running. It SHALL derive its verdict from the freshness of the most recently
written per-vault `sync.log` under the `ob` config directory, because continuous
sync appends to that log on a fixed interval and stops appending the moment it
stalls, whereas the process itself, its configuration directory, and its local
change-tracking database all persist unchanged through a stall. The config
directory SHALL be derived the same way the entry point derives it. The check
SHALL require no package beyond what the image already installs, and SHALL NOT
depend on reaching the sync service over the network.

#### Scenario: Actively syncing sidecar is healthy

- **WHEN** the sidecar is running continuous sync and has written to its
  `sync.log` within the freshness window
- **THEN** the healthcheck command succeeds (exit 0)

#### Scenario: Wedged but running sync reports unhealthy

- **WHEN** the `ob` process is still alive but has written nothing to its
  `sync.log` for longer than the freshness window
- **THEN** the healthcheck command fails (non-zero exit)
- **AND** the failure output names the observed age and the threshold

#### Scenario: Un-bootstrapped sidecar still reports unhealthy

- **WHEN** the sidecar has no `ob` configuration, and therefore no `sync.log`
- **THEN** the healthcheck command fails (non-zero exit), preserving the
  behaviour of the previous config-directory check

#### Scenario: Most recently active vault decides the verdict

- **WHEN** the config directory holds sync state for more than one vault
- **THEN** the healthcheck uses the newest `sync.log` across them

#### Scenario: Start-up is not mistaken for a stall

- **WHEN** the container has only just started and has not yet written its first
  log line
- **THEN** the configured start period suppresses the failure rather than
  counting it toward the retry budget

### Requirement: Freshness window is configurable

The freshness window SHALL default to a value that tolerates several missed log
intervals without flapping, and SHALL be overridable via an environment
variable, following the same convention as the entry point's existing poll
interval. A shorter window SHALL make the check stricter and a longer one more
tolerant, with no rebuild required.

#### Scenario: Default window tolerates a missed interval

- **WHEN** a single expected log write is late but sync is otherwise progressing
- **THEN** the healthcheck still succeeds

#### Scenario: Override is honoured

- **WHEN** the freshness-window environment variable is set to a value shorter
  than the observed log age
- **THEN** the healthcheck fails, showing the override took effect
