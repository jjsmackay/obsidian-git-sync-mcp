## ADDED Requirements

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
- **THEN** it runs continuous sync if the config dir is already populated
- **AND** otherwise prints the bootstrap instructions and idles/polls rather than
  exiting or crash-looping

#### Scenario: Bootstrap is never auto-run on a TTY

- **WHEN** the entry point starts with no explicit command and a TTY attached
- **THEN** it does not start bootstrap; bootstrap runs only on an explicit
  `bootstrap` arg or `BOOTSTRAP` env

### Requirement: Config named volume inherits ob ownership

The sidecar image SHALL pre-create the `ob` config directory
(`/home/ob/.config/obsidian-headless`) as uid 10001 before the named `config`
volume is mounted there, so that a fresh named volume inherits `ob` ownership on
first use and no host-side chown is required for the sidecar's config volume.

#### Scenario: Fresh config volume is writable by ob

- **WHEN** the sidecar first starts with a fresh named `config` volume mounted at
  the `ob` config directory
- **THEN** the directory is owned by uid 10001 (`ob`) and `ob` can write its
  credentials and sync state without a host-side chown
