# Runbook — Upgrade & Rollback

## Upgrade (v0.1.0 → v0.2.0 example)

```sh
pip install --upgrade agentwatch
agentwatch migrate        # applies any store-format migration
agentwatch status         # confirm recording
```

If a store-format change is breaking, `agentwatch migrate` emits a backup and a documented migration
(record-format spec §Versioning).

## Rollback

```sh
pip install agentsec-agentwatch==0.1.0
agentwatch migrate --rollback    # restore the pre-migration store
```

## Uninstall

```sh
agentwatch uninstall            # remove hooks, stop daemon
# optional: rm -rf ~/.local/share/agentwatch   # purge records
```

## Principle

Upgrades preserve records; rollbacks restore them. No silent format changes.
