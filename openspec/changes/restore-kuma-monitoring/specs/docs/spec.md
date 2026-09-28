# Spec Delta

## MODIFIED Requirements

### Requirement: Exposure and monitoring are documented

The README SHALL state that only the MCP port is published and document safe
remote exposure (reverse proxy / Cloudflare Tunnel / Tailscale) including
`VAULT_MCP_ALLOWED_HOSTS` / `VAULT_MCP_PUBLIC_URL`, and SHALL describe the five
monitoring layers (the mcp container port healthcheck, the sidecar sync-freshness
healthcheck, upstream liveness heartbeat, git-sync push heartbeat, and the
sidecar sync-freshness heartbeat), distinguishing what each one can and cannot
detect.

#### Scenario: Exposure guidance is present

- **WHEN** a reader looks for how to reach the server remotely
- **THEN** the README documents putting it behind a proxy/tunnel and setting the
  allowed-hosts / public-URL variables, with no tunnel baked into the project

#### Scenario: Monitoring layers are distinguished

- **WHEN** a reader looks for monitoring
- **THEN** the README distinguishes the mcp container port healthcheck, the
  sidecar sync-freshness healthcheck, the upstream server-liveness heartbeat,
  the git-sync push heartbeat, and the sidecar sync-freshness heartbeat

#### Scenario: Healthcheck and heartbeat are distinguished for the sidecar

- **WHEN** a reader compares the sidecar's two monitoring layers
- **THEN** the README states that they share one signal and one cadence, and
  that the healthcheck reports into Docker while the heartbeat is what reaches
  anything outside the container

#### Scenario: Detection is not presented as recovery

- **WHEN** a reader looks for what happens when a healthcheck fails
- **THEN** the README states that an unhealthy container is not restarted by
  Docker or Compose on its own, and names what an operator must add for
  automatic recovery

## ADDED Requirements

### Requirement: Push-monitor wiring is documented

The documentation SHALL give an operator everything needed to point a push-style
monitor at the deployment without reading the code: for each of the three
heartbeats, the variable that carries it, what a beat asserts, and what silence
means. It SHALL note that the endpoint must be reachable from inside the
container, so a monitor fronted by an authenticating proxy must be addressed by
its internal address rather than its public one, and that heartbeat URLs are
commonly capability URLs carrying a secret in the path and therefore belong in
the deployment's environment file rather than in committed configuration.
`.env.example` SHALL carry an entry for every heartbeat variable an operator
sets, including the upstream server's own, which this package does not read but
an operator configuring monitoring must set.

#### Scenario: Each heartbeat's meaning is documented

- **WHEN** a reader looks up any of the three heartbeats
- **THEN** the docs name its variable, state what a beat asserts, and state what
  silence indicates

#### Scenario: Reachability caveat is present

- **WHEN** a reader configures a heartbeat URL
- **THEN** the docs state that the container must be able to reach the endpoint,
  and warn that a public hostname behind an authenticating proxy will reject
  the beats

#### Scenario: Secret handling is stated

- **WHEN** a reader looks for where to put a heartbeat URL
- **THEN** the docs state that it may carry a secret in its path and belongs in
  the environment file, not in committed configuration

#### Scenario: Env-example covers every heartbeat variable

- **WHEN** `.env.example` is compared with the heartbeat variables an operator
  can set across both images
- **THEN** each one appears there, including the upstream server's, with the
  upstream one attributed to the upstream server rather than to this package
