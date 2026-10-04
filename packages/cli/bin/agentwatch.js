#!/usr/bin/env node
"use strict";

// Thin launcher: `npx @agentsec-ecosystem/cli <command>` forwards straight to
// the Python CLI (`python3 -m agentwatch.cli`), sharing the same exit code.

const { spawnSync } = require("node:child_process");

const python = process.env.AGENTWATCH_PYTHON || "python3";
const result = spawnSync(
  python,
  ["-m", "agentwatch.cli", ...process.argv.slice(2)],
  { stdio: "inherit" }
);

if (result.error) {
  console.error(
    `agentwatch: failed to launch '${python}': ${result.error.message}\n` +
      "Install the Python CLI (pip install agentwatch) or set AGENTWATCH_PYTHON."
  );
  process.exit(127);
}

process.exit(result.status === null ? 1 : result.status);
