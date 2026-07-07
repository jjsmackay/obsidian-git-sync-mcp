## 1. Compose

- [ ] 1.1 Add `vault:` to the top-level `volumes:` block in `docker-compose.yml`

## 2. Docs

- [ ] 2.1 Add a note to README's "Named volumes (orchestrators)" section that
      `VAULT_HOST_PATH` as a bare name now resolves to the declared `vault`
      volume

## 3. Verify

- [ ] 3.1 `docker compose config` validates with `VAULT_HOST_PATH` set to a
      bare name (e.g. `vault`)
- [ ] 3.2 `docker compose config` validates unchanged with the default
      `VAULT_HOST_PATH=./vault`
