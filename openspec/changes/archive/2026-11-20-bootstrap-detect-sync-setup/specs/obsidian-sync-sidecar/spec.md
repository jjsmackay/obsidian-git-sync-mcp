# Spec Delta

## MODIFIED Requirements

### Requirement: Idle sidecar auto-starts sync once bootstrapped

When the sidecar starts un-bootstrapped (no vault configured by `ob sync-setup` in the persisted config dir) and no explicit command is given, the entry point SHALL print the bootstrap instructions once and then poll for config rather than idling forever. As soon
as a vault is configured — i.e. an operator has run the explicit `bootstrap`
against the running container through to `sync-setup` — the entry point SHALL start
continuous sync itself (`ob sync --path "$VAULT_PATH" --continuous`) without a
manual container restart. The poll interval SHALL default to a few seconds and
SHALL be overridable via an environment variable. The entry point SHALL NOT
auto-run bootstrap: it only auto-starts sync once config exists, preserving the
explicit-only bootstrap contract (a detected TTY must not trigger an interactive
login). The existing branches — explicit `bootstrap` arg / `BOOTSTRAP` env,
explicit passthrough command, and already-bootstrapped → continuous sync — SHALL
be unchanged. Login alone SHALL NOT count as bootstrapped: `ob login` writes its
credential into the config dir before `sync-setup` runs, and treating that as
bootstrapped starts `ob sync` with no vault configured.

#### Scenario: Idle entry point begins syncing after bootstrap without a restart

- **WHEN** the sidecar starts with no config and no explicit command, an operator
  then runs the explicit `bootstrap` against the running container through to
  `sync-setup`
- **THEN** the entry point detects the config on its next poll and execs
  `ob sync --path "$VAULT_PATH" --continuous`, with no manual container restart

#### Scenario: Instructions are printed once, then the loop idles quietly

- **WHEN** the sidecar starts un-bootstrapped
- **THEN** the bootstrap instructions are printed a single time
- **AND** the entry point sleeps the poll interval between `is_bootstrapped`
  checks rather than executing `sleep infinity`

#### Scenario: Poll interval is overridable

- **WHEN** the poll-interval environment variable is set
- **THEN** the entry point waits that interval between config checks
- **AND** when it is unset the entry point uses its built-in default of a few
  seconds

#### Scenario: Bootstrap is never auto-run

- **WHEN** the sidecar is idle and un-bootstrapped, even with a TTY attached
- **THEN** the entry point only ever auto-starts sync after config appears
- **AND** it never invokes `bootstrap` itself

#### Scenario: Existing start branches are preserved

- **WHEN** a `bootstrap` arg / `BOOTSTRAP` env, an explicit passthrough command,
  or an already-populated config dir is present at start
- **THEN** the entry point behaves exactly as before — interactive bootstrap, the
  verbatim command, or continuous sync respectively — without entering the poll
  loop

#### Scenario: Login alone does not start sync

- **WHEN** an operator's interactive `bootstrap` has completed `ob login` but not
  yet `sync-setup`, so the config dir holds a credential and no configured vault
- **THEN** the idle entry point keeps polling and does not start `ob sync`
- **AND** the operator's interactive bootstrap session is not interrupted by a
  sync failure or a container restart

### Requirement: Entry point dispatches the run mode explicitly

The sidecar entry point SHALL choose what to run from an explicit command and the
bootstrap state, and SHALL NOT ever auto-run bootstrap. An explicit `bootstrap`
argument or a set `BOOTSTRAP` environment variable SHALL run the interactive
bootstrap (the `bootstrap` arg forwarding any remaining arguments, e.g. `--reset`).
Any other explicit command SHALL be exec'd verbatim as a passthrough escape hatch,
without being second-guessed. With no explicit command the entry point SHALL make a
four-way start decision: bootstrap when requested; otherwise the verbatim command;
otherwise continuous sync when already bootstrapped; otherwise idle-and-poll when not
yet bootstrapped. Bootstrap SHALL remain explicit-only and SHALL NOT be triggered by
a detected TTY, because compose's `tty: true` makes stdin a TTY even with nobody
attached and would hang at the `ob login` prompt.

#### Scenario: Explicit bootstrap request runs bootstrap

- **WHEN** the entry point is invoked with a `bootstrap` argument, or with the
  `BOOTSTRAP` environment variable set
- **THEN** it runs the interactive bootstrap, forwarding any remaining arguments to
  it

#### Scenario: Any other explicit command is passed through verbatim

- **WHEN** the entry point is invoked with an explicit command that is not
  `bootstrap` (e.g. `sh`)
- **THEN** it execs that command verbatim without altering it

#### Scenario: No command falls through to the start decision

- **WHEN** the entry point is invoked with no explicit command
- **THEN** it runs continuous sync if a vault is already configured by `sync-setup`
- **AND** otherwise prints the bootstrap instructions and idles/polls rather than
  exiting or crash-looping

#### Scenario: Bootstrap is never auto-run on a TTY

- **WHEN** the entry point starts with no explicit command and a TTY attached
- **THEN** it does not start bootstrap; bootstrap runs only on an explicit
  `bootstrap` arg or `BOOTSTRAP` env
