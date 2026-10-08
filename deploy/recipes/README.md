# Alert-routing recipes (M30 NTF-1)

**Routing lives in your stack.** agentwatch deliberately forwards security events **rule-free** — no
thresholds, no suppression, no severity — and leaves alerting to your policy layer (agentpolicy). These three
recipes are the missing "how do I get a Slack ping?" half: copy, adapt, and route however you want.

Each recipe reads the security-event NDJSON stream (the same events the
[`file://` / webhook / syslog sinks](../../docs/design/observability.md) forward), maps each event to the target
stack's payload, and posts it through the **shipped** `agentwatch.sinks.WebhookSink` — no second HTTP client, no
new dependency, and **no built-in rules**. Every event is forwarded; filtering and paging are yours.

| Recipe | Target | Endpoint |
|---|---|---|
| [`slack_webhook.py`](slack_webhook.py) | Slack incoming webhook | `https://hooks.slack.com/services/...` |
| [`pagerduty.py`](pagerduty.py) | PagerDuty Events API v2 | `https://events.pagerduty.com/v2/enqueue` |
| [`alertmanager.py`](alertmanager.py) | Prometheus Alertmanager | `.../api/v2/alerts` |

## Run one

```sh
export INPUT=examples/fixtures/events.ndjson      # or: agentwatch ... --format ndjson > events.ndjson

python deploy/recipes/slack_webhook.py --input "$INPUT" --url "$SLACK_WEBHOOK_URL"
python deploy/recipes/pagerduty.py --input "$INPUT" --routing-key "$PAGERDUTY_ROUTING_KEY"
python deploy/recipes/alertmanager.py --input "$INPUT" --url "$ALERTMANAGER_URL/api/v2/alerts"
```

The event→urgency/severity defaults in the PagerDuty and Alertmanager recipes are **presentation choices you
own** — edit them. The Alertmanager recipe also carries the OCSF path: point an OCSF consumer or a webhook sink
at these recipes the same way.

## Oversight and capability changes

Security events are the primary stream (a `denied`, `secret-detected`, `policy-fired`, `mode-transition`, or the
forward-compatible `capability-changed` placeholder). For **oversight thresholds** (APV-3) or **capability drift**
(CAP-2), evaluate the `agentwatch oversight` / capability output in your own job and emit an event into the same
stream — the recipe shape is unchanged. agentwatch still defines no rule.

## CI

`packages/python-sdk/tests/test_alert_recipes.py` loads each recipe, maps the M27 SIEM fixture events, and asserts
the payload shape and that an injected transport receives one request per event — offline, with zero network.
