# Tasks

## 1. Detect sync-setup, not login

- [x] 1.1 Change `is_bootstrapped` in `entrypoint.sh` to test for an entry under
  `$CONFIG_DIR/sync/`; verify an idle container with only `auth_token` in its
  config keeps polling and does not restart
- [x] 1.2 Verify an interactive `bootstrap` run against the idle container
  completes through `sync-setup`, after which continuous sync starts on the next
  poll with no restart
- [x] 1.3 Verify an already-bootstrapped config volume starts continuous sync
  straight away, as before
