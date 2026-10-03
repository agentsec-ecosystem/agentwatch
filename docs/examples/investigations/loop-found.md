# The loop no one noticed

**The question:** did the agent get stuck re-reading the same file?

Seed the store and look at the session:

```sh
python3 scripts/seed-investigations.py --store /tmp/agentwatch-demo
agentwatch --set store.path=/tmp/agentwatch-demo view sess-loop
```

You get the ordered timeline — the same `Read` four times:

```sh
agentwatch --set store.path=/tmp/agentwatch-demo search --tool Read --session sess-loop
```

Reconstruct it step by step, or ask for the deterministic summary:

```sh
agentwatch --set store.path=/tmp/agentwatch-demo replay sess-loop
agentwatch --set store.path=/tmp/agentwatch-demo explain sess-loop
```

`explain` prints the facts (record count, outcomes, tools, tokens, duration)
with no model call — so it is safe to run on a machine that never reaches the
network. Add a narrator only when you have opted in (see PRD 29).

**What to look for:** a repeated tool with identical arguments in a short window.
The analytics detectors flag the same shape fleet-wide as `loop`/`pattern_loop`.
