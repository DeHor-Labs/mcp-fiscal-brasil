#!/usr/bin/env node
/**
 * Bin entry point — proxies all args to the Python `mcp-fiscal` CLI.
 *
 * Requires the Python package `mcp-fiscal-brasil` to be installed and
 * `mcp-fiscal` on PATH (via pipx, uv tool, or pip --user).
 */
import { spawn } from "node:child_process";

const args = process.argv.slice(2);
const proc = spawn("mcp-fiscal", args, { stdio: "inherit" });

proc.on("error", (err: Error) => {
  console.error(`[mcp-fiscal] Failed to spawn Python CLI: ${err.message}`);
  console.error(
    "[mcp-fiscal] Install the Python package first: `pipx install mcp-fiscal-brasil` or `uv tool install mcp-fiscal-brasil`",
  );
  process.exit(127);
});

proc.on("close", (code: number | null) => {
  process.exit(code ?? 0);
});
