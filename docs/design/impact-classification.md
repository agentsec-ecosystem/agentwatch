# Design — Impact Classification Table

**BLUF:** `agentwatch impact`/`blame`/`denials` classify already-redacted records into **facts** — files
touched, side-effecting commands, network destinations, VCS actions, credential-adjacent touches — with a
deterministic, **published** pattern table. Every entry carries `confidence: exact | heuristic`, and
anything unmatched lands in a surfaced `unclassified` bucket. It is descriptive, never a verdict.

**Status:** published (v0.1.0) · **Version:** `cls1` (`agentwatch.classify.CLASSIFIER_VERSION`) ·
Source: [PRD 33](../prd/33-investigation-and-impact.md) S3/S18/S23/S25.

## Confidence

| Value | Meaning |
|---|---|
| `exact` | A structured argument, e.g. `Write.file_path` — the path is the argument itself. |
| `heuristic` | A token inside a shell command string — a small regex classifier, not a shell parser. |

Shell parsing is a bottomless pit. The classifier is deliberately small, never claims completeness, and
puts everything it does not recognise in `unclassified`.

## Categories

- `file:write`, `file:edit`, `file:delete`, `file:read`
- `command:install`, `command:migration`, `command:service-restart`, `command:destructive`
- `network:destination`, `vcs:action`, `credential:adjacent`
- `unclassified`

## Pattern table (`cls1`)

The normative table is :data:`agentwatch.classify.PATTERNS`; `pattern_table()` renders it for docs and
tests. It is transcribed below by rule id.

| Rule id | Category | Confidence | Match |
|---|---|---|---|
| `install/pip` | command:install | heuristic | `pip`/`uv pip` install |
| `install/npm` | command:install | heuristic | `npm`/`pnpm`/`yarn`/`bun` install/add |
| `install/brew` | command:install | heuristic | `brew`/`port`/`nix-env` install |
| `install/apt` | command:install | heuristic | `apt`/`dnf`/`yum`/`apk`/`pacman` install |
| `install/cargo` | command:install | heuristic | `cargo`/`go`/`gem`/`poetry`/`conda` add/install/get |
| `migrate/alembic` | command:migration | heuristic | `alembic upgrade/downgrade` |
| `migrate/django` | command:migration | heuristic | `manage.py migrate`, `django-admin migrate` |
| `migrate/rails` | command:migration | heuristic | `rails db:migrate`, `prisma migrate`, `flyway`, `sqitch` |
| `service/systemctl` | command:service-restart | heuristic | `systemctl restart/start/stop/reload` |
| `service/service` | command:service-restart | heuristic | `service X restart`, `launchctl`, `pm2`, `supervisorctl` |
| `service/docker` | command:service-restart | heuristic | `docker(-compose) restart/up/down/stop/start/kill` |
| `service/kubectl` | command:service-restart | heuristic | `kubectl rollout/restart/delete/apply`, `helm upgrade/install/uninstall` |
| `destructive/rm` | command:destructive | heuristic | `rm -rf`/`-fr` |
| `destructive/sql` | command:destructive | heuristic | `drop database/table/schema`, `truncate table`, `delete from` |
| `destructive/disk` | command:destructive | heuristic | `mkfs`, `shred`, `dd if=/dev/zero|urandom` |
| `destructive/git` | command:destructive | heuristic | `git reset --hard`, `git clean -f`, `git push --force`, `git branch -D` |
| `destructive/process` | command:destructive | heuristic | `kill -9`, `pkill`, `chmod -R`, `chown -R` |
| `file/redirect` | file:write | heuristic | `>`/`>>` target |
| `file/tee` | file:write | heuristic | `tee` target |
| `file/sed` | file:edit | heuristic | `sed -i` target |
| `file/cp` | file:write | heuristic | `cp` destination |
| `file/mv` | file:write | heuristic | `mv` destination |
| `file/touch` | file:write | heuristic | `touch` target |
| `file/rm` | file:delete | heuristic | `rm` target |
| `file/rmdir` | file:delete | heuristic | `rmdir` target |
| `net/curl` | network:destination | heuristic | host after `curl`/`wget` |
| `net/scp` | network:destination | heuristic | host after `ssh`/`scp`/`rsync`/`nc`/`telnet` |
| `vcs/git` | vcs:action | heuristic | `git <verb>` |
| `vcs/gh` | vcs:action | heuristic | `gh <verb>` |
| `cred/env`, `cred/aws`, `cred/ssh`, `cred/misc` | credential:adjacent | heuristic | `.env`, `~/.aws`, `~/.ssh`/keys, `.netrc`/`.pypirc`/`.npmrc`/docker/kube config/keychain |

Structured tools map exactly: `Write`/`NotebookEdit` → `file:write`, `Edit`/`MultiEdit` → `file:edit`,
`Read`/`Glob`/`Grep` → `file:read`, all with the path argument as the target.

## Widest action

The blast-radius summary's single line uses this priority (most consequential first), then falls back to
counts: `command:destructive`, `file:delete`, `command:service-restart`, `command:migration`,
`command:install`, `file:write`, `file:edit`, `credential:adjacent`, `network:destination`, `vcs:action`,
`file:read`, `unclassified`.

## What it is not

- No score, no severity, no ranking, no "exfiltration" verdict — that is agentpolicy's or a human's
  judgement (PRD 14).
- A `metadata-only` record has no arguments; the classifier says `arguments not captured`, never guesses.
