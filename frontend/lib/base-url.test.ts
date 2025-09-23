import assert from "node:assert/strict";
import { resolveBaseURLFromConfig, rewritePreviewHostname } from "./base-url";

const FRONT_PORT = "3000";
const BACKEND_PORT = "8000";

const rewriteCases = [
  {
    description: "suffix hostnames ending with the front port and dot segments",
    hostname: "portefeuille-3000.gitpod.io",
    expected: "portefeuille-8000.gitpod.io"
  },
  {
    description: "suffix hostnames continuing with hyphen segments",
    hostname: "portefeuille-3000-12345.gitpod.io",
    expected: "portefeuille-8000-12345.gitpod.io"
  },
  {
    description: "prefix hostnames beginning with the front port",
    hostname: "3000-portefeuille.gitpod.io",
    expected: "8000-portefeuille.gitpod.io"
  },
  {
    description: "hostnames without the front port remain unchanged",
    hostname: "example.gitpod.io",
    expected: "example.gitpod.io"
  }
];

for (const { description, hostname, expected } of rewriteCases) {
  const rewritten = rewritePreviewHostname(hostname, FRONT_PORT, BACKEND_PORT);
  assert.equal(rewritten, expected, description);
}

const baseUrlCases = [
  {
    description: "uses the environment override when provided",
    envBase: "https://example.com",
    location: {
      protocol: "https:",
      hostname: "portefeuille-3000.gitpod.io",
      origin: "https://portefeuille-3000.gitpod.io"
    },
    expected: "https://example.com"
  },
  {
    description: "falls back to localhost when no location is available",
    envBase: undefined,
    location: undefined,
    expected: "http://localhost:8000"
  },
  {
    description: "rewrites gitpod-style suffix hostnames",
    envBase: undefined,
    location: {
      protocol: "https:",
      hostname: "portefeuille-3000-12345.gitpod.io",
      origin: "https://portefeuille-3000-12345.gitpod.io"
    },
    expected: "https://portefeuille-8000-12345.gitpod.io"
  },
  {
    description: "rewrites gitpod-style prefix hostnames",
    envBase: undefined,
    location: {
      protocol: "https:",
      hostname: "3000-portefeuille.gitpod.io",
      origin: "https://3000-portefeuille.gitpod.io"
    },
    expected: "https://8000-portefeuille.gitpod.io"
  },
  {
    description: "preserves localhost but swaps to backend port",
    envBase: undefined,
    location: {
      protocol: "http:",
      hostname: "localhost",
      port: "3000",
      origin: "http://localhost:3000"
    },
    expected: "http://localhost:8000"
  },
  {
    description: "uses backend port when an explicit port is present",
    envBase: undefined,
    location: {
      protocol: "http:",
      hostname: "example.internal",
      port: "3100",
      origin: "http://example.internal:3100"
    },
    expected: "http://example.internal:8000"
  },
  {
    description: "returns the original origin when nothing matches",
    envBase: undefined,
    location: {
      protocol: "https:",
      hostname: "demo.example.com",
      origin: "https://demo.example.com"
    },
    expected: "https://demo.example.com"
  }
];

for (const { description, envBase, location, expected } of baseUrlCases) {
  const resolved = resolveBaseURLFromConfig(envBase, location);
  assert.equal(resolved, expected, description);
}

console.log("All base URL rewrite tests passed.");
