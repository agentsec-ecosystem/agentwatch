# Reference — Adapter API (plugin contract)

**BLUF:** A harness adapter is a small module that maps native harness events to agentwatch records and
passes the shared conformance runner. This is the **published plugin contract** community harnesses build
against (M10 #79/#203); it is versioned with `agentwatch.protocol.PROTOCOL_VERSION`.

Status: **experimental** (v0.1.0). Compatibility: additive minor, breaking major + deprecation.

## What an adapter declares

| Name | Type | Meaning |
|---|---|---|
| `HARNESS_ID` | `str` | stable harness id (e.g. `claude-code`, `sample-harness`) |
| `CAPABILITIES` | `frozenset[str]` | capability classes implemented (e.g. `pre-tool-use`) |
| `DOCUMENTED_GAPS` | `tuple[str, ...]` | classes **not** implemented, declared honestly (R3) |
| `normalize(message)` | `Mapping -> list[AgentRecord]` | map one native event to records |
| error class | `type[Exception]` | raised for a declared gap or unknown phase |

`CAPABILITIES` and `DOCUMENTED_GAPS` must be disjoint. A declared gap or unknown phase presented to
`normalize` must raise the adapter's error class — never be silently dropped or coerced (F8).

## Registering + running conformance

```python
from agentwatch import conformance

spec = conformance.AdapterSpec(
    name=my.HARNESS_ID,
    normalize=my.normalize,
    capabilities=my.CAPABILITIES,
    documented_gaps=my.DOCUMENTED_GAPS,
    error_cls=my.AdapterError,
    fixtures_dir=Path(__file__).parent / "fixtures",
)
conformance.register(spec)
conformance.assert_registered_conform()   # blocks CI on any failure
```

The runner (`agentwatch.conformance.run`) checks: registration, capability/gap disjointness, a populated
fixture pack (`message` + `expected`), fixture replay, explicit gap rejection, unknown-phase rejection,
record validation on every output, and dedup/idempotency. See
[adapter-conformance.md](adapter-conformance.md).

## Fixture pack

One JSON file per case in `fixtures_dir`:

```json
{ "message": { "phase": "…", "event": { … } }, "expected": [ { "schema_version": "0.1.0", … } ] }
```

`expected` is the exact `to_dict()` output; the runner also asserts `normalize` did not mutate `message`.

## Reference implementation

`packages/python-sdk/tests/community_adapter.py` is a minimal out-of-tree adapter built with only this
public contract plus the stdlib; `tests/test_community_adapter.py` asserts it conforms and that a
deliberately broken copy fails.

## Compatibility

Additive fields/phases bump the minor; renames or removals bump the major with a deprecation cycle. A
community adapter built to an older spec is reported by the runner rather than silently accepted.
