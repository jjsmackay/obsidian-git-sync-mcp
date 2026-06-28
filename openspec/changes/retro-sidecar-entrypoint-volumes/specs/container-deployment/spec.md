## ADDED Requirements

### Requirement: Named vault volume must be seeded and chowned

A fresh Docker named volume used for the vault SHALL mount root-owned, so it cannot
be cloned into on the host and the uid-10001 container user cannot commit until it is
fixed. The deployment SHALL document seeding such a volume with a one-off container
that clones the repo into it and runs `chown -R 10001:10001` on the vault path, so the
non-root container user can commit. Unlike the sidecar's `config` volume, the vault
volume has no image-side ownership fix; the seed step is the documented remedy.

#### Scenario: Fresh named vault volume is seeded for the container user

- **WHEN** the vault is a fresh Docker named volume rather than a host directory
- **THEN** the docs describe a one-off container that clones the repo into the volume
  and runs `chown -R 10001:10001` on the vault path so uid 10001 can commit
