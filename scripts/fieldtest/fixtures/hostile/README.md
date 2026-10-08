# Hostile fixtures (ADR-0024, RSK-1, COR-4)

Shape-synthesized weaponized payloads; **content is data, never executed**.
The Codex backtick payload models public report #36937 (HOME-deletion via a
tool-argument backtick). Every parser must contain these and quarantine them;
no shell/eval/pipe may run. Absent a real secret, nothing here is sensitive.
