# agentwatch field-test recorder image — the system under test.
#
# Builds from the repo root so it can install the SDK:
#   docker compose -f docker-compose.yml \
#     -f scripts/fieldtest/docker-compose.fieldtest.yml build recorder
FROM python:3.12-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# git: session-start VCS snapshot (S16); curl: readiness/log helpers; procps for pkill/ps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Install the SDK + CLI entry points (agentwatch, agentwatch-hook, agentwatch-daemon).
# Extras: signing (checkpoint export/verify) and otlp (export cases) are required
# by the field tests, so install them into the system-under-test image.
COPY packages/python-sdk /work/packages/python-sdk
RUN pip install --no-cache-dir -e "/work/packages/python-sdk[signing,otlp]"

# Harness helpers (also bind-mounted at /ft/scripts at runtime).
COPY scripts/fieldtest /work/fieldtest/scripts

RUN mkdir -p /data/agentwatch /run/agentwatch

CMD ["sleep", "infinity"]
