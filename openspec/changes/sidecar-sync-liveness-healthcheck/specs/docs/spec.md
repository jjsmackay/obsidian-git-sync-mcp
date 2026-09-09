## MODIFIED Requirements

### Requirement: Exposure and monitoring are documented

The README SHALL state that only the MCP port is published and document safe
remote exposure (reverse proxy / Cloudflare Tunnel / Tailscale) including
`VAULT_MCP_ALLOWED_HOSTS` / `VAULT_MCP_PUBLIC_URL`, and SHALL describe the four
monitoring layers (the mcp container port healthcheck, the sidecar sync-freshness
healthcheck, upstream liveness heartbeat, and git-sync push heartbeat),
distinguishing what each one can and cannot detect.

#### Scenario: Exposure guidance is present

- **WHEN** a reader looks for how to reach the server remotely
- **THEN** the README documents putting it behind a proxy/tunnel and setting the
  allowed-hosts / public-URL variables, with no tunnel baked into the project

#### Scenario: Monitoring layers are distinguished

- **WHEN** a reader looks for monitoring
- **THEN** the README distinguishes the mcp container port healthcheck, the
  sidecar sync-freshness healthcheck, the upstream server-liveness heartbeat,
  and the git-sync push heartbeat

#### Scenario: Detection is not presented as recovery

- **WHEN** a reader looks for what happens when a healthcheck fails
- **THEN** the README states that an unhealthy container is not restarted by
  Docker or Compose on its own, and names what an operator must add for
  automatic recovery
