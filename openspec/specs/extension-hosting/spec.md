# extension-hosting Specification

## Purpose
TBD - created by archiving change load-additional-extensions. Update Purpose after archive.
## Requirements
### Requirement: Additional extensions load from an operator-declared list

The console entry point SHALL accept a list of additional `extensions.Extension`
implementations declared by the operator in the `VAULT_MCP_EXTENSIONS`
environment variable, and SHALL pass them to the upstream server after
`GitSyncExtension` in a single `serve(...)` call. The variable SHALL be a
comma-separated list of import specs of the form `module.path:ClassName`.
Surrounding whitespace around an entry SHALL be ignored, and an empty entry
produced by a trailing or repeated comma SHALL be skipped rather than treated as
an error.

#### Scenario: A declared extension is loaded alongside git-sync

- **WHEN** `VAULT_MCP_EXTENSIONS` names one resolvable `Extension` subclass
- **THEN** the server is started with both that extension and `GitSyncExtension`
- **AND** the declared extension participates in the server lifecycle

#### Scenario: Several extensions are declared

- **WHEN** `VAULT_MCP_EXTENSIONS` names more than one resolvable subclass,
  separated by commas
- **THEN** every named extension is instantiated once and passed to the server
- **AND** they appear in the order they were declared

#### Scenario: Whitespace and empty entries are tolerated

- **WHEN** an entry carries leading or trailing whitespace, or the list contains
  a trailing or repeated comma
- **THEN** the whitespace is ignored, empty entries are skipped, and the
  remaining entries load normally

### Requirement: Unset or empty declares no additional extensions

The entry point SHALL treat an unset, empty, or whitespace-only
`VAULT_MCP_EXTENSIONS` as declaring no additional extensions, and SHALL then
behave exactly as it does without this capability — starting the upstream server
with `GitSyncExtension` alone. No import machinery SHALL run in that case.

#### Scenario: Unset is today's behaviour

- **WHEN** the server starts with `VAULT_MCP_EXTENSIONS` unset
- **THEN** the server starts with `GitSyncExtension` as the only extension
- **AND** no additional extension is imported or instantiated

#### Scenario: Empty or whitespace-only is treated as unset

- **WHEN** `VAULT_MCP_EXTENSIONS` is set to an empty or whitespace-only value
- **THEN** the server starts with `GitSyncExtension` as the only extension

### Requirement: Extension resolution fails closed at startup

Resolution of every declared import spec SHALL happen once at startup, before
the upstream server is handed the extension list, and SHALL fail closed. When an
entry is malformed, names a module that cannot be imported, names an attribute
the module does not define, or names a target that is not an
`extensions.Extension` subclass, the entry point SHALL refuse to start, SHALL
report an error identifying the offending entry and why it was rejected, and
SHALL exit non-zero. The server SHALL NOT start with a partially-resolved
extension list.

#### Scenario: Malformed import spec refuses to start

- **WHEN** an entry is missing the `:ClassName` separator, or names an empty
  module or attribute
- **THEN** startup fails with an error naming that entry
- **AND** the process exits non-zero without starting the server

#### Scenario: Unimportable module refuses to start

- **WHEN** an entry names a module that cannot be imported
- **THEN** startup fails with an error naming that entry and the import failure
- **AND** the process exits non-zero without starting the server

#### Scenario: Missing attribute refuses to start

- **WHEN** an entry names a module that imports but does not define the named
  attribute
- **THEN** startup fails with an error naming that entry
- **AND** the process exits non-zero without starting the server

#### Scenario: Target that is not an Extension subclass refuses to start

- **WHEN** an entry resolves to an object that is not a subclass of
  `extensions.Extension`
- **THEN** startup fails with an error naming that entry and what it resolved to
- **AND** the process exits non-zero without starting the server

#### Scenario: One bad entry rejects the whole list

- **WHEN** a list contains both resolvable entries and one that cannot be
  resolved
- **THEN** the server does not start
- **AND** no extension from that list is loaded

### Requirement: The git-sync extension loads first

The entry point SHALL place `GitSyncExtension` first in the list handed to
`serve(...)`, ahead of every operator-declared extension, so that its hook runs
before any additional extension's at each stage of the upstream lifecycle.

#### Scenario: Git-sync precedes declared extensions

- **WHEN** the server is started with one or more declared extensions
- **THEN** `GitSyncExtension` is the first element of the extension list passed
  to `serve(...)`

### Requirement: Loading is explicit opt-in, never implicit discovery

Additional extensions SHALL be loaded only from the operator's explicit
`VAULT_MCP_EXTENSIONS` declaration. The entry point SHALL NOT discover
extensions from installed-package metadata, entry-point groups, or filesystem
scanning, because an extension is fully-trusted in-process code holding the
server's full privileges and mere installation is not consent to load it. The
documented configuration surface SHALL state that trust position.

#### Scenario: An installed but undeclared extension is not loaded

- **WHEN** a package providing an `Extension` subclass is installed but named
  nowhere in `VAULT_MCP_EXTENSIONS`
- **THEN** that extension is not imported, instantiated, or loaded

#### Scenario: The trust position is documented

- **WHEN** the documented configuration surface for `VAULT_MCP_EXTENSIONS` is
  read
- **THEN** it states that a declared extension runs in-process with the server's
  full privileges and is loaded only by explicit declaration

