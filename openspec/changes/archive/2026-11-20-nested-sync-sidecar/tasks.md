# Tasks

## 1. Nested service

- [x] 1.1 Add `obsidian-sync-nested` to `docker-compose.yml` behind profile
  `nested`, own `nested_config` volume, settings sync off; verify
  `docker compose config` without the profile does not list it and with
  `--profile obsidian --profile nested` resolves `VAULT_PATH` to the folder
- [x] 1.2 Add `nested-guard` to the image and call it from `entrypoint.sh` and
  `bootstrap.sh`; verify it passes for an existing subfolder and refuses an
  empty subpath and `../` escapes, and is a no-op with `NESTED_PARENT` unset

## 2. Bootstrap settings

- [x] 2.1 Read `SYNC_DEVICE_NAME`, `SYNC_CONFIGS` and `SYNC_FILE_TYPES` in
  `bootstrap.sh`; verify the device name and settings appear in
  `ob sync-status` after a real bootstrap, and that unset variables leave the
  defaults alone

## 3. Verification

- [x] 3.1 Run an outer and a nested sidecar against two real remote vaults;
  verify a write in the outer remote reaches the nested remote and the reverse,
  including a delete
- [x] 3.2 Verify the nested client's `.obsidian` lock folder never reaches the
  outer remote
- [x] 3.3 Document the nested sidecar in `obsidian-sync/README.md`
