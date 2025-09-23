import axios from "axios";

const resolveBaseURL = (): string => {
  const envBase = process.env.NEXT_PUBLIC_API_BASE;
  if (envBase) {
    return envBase;
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location;

    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `${protocol}//${hostname}:8000`;
    }

    if (port) {
      return `${protocol}//${hostname}:8000`;
    }

    const frontPort = port || "3000";
    const suffixRegex = new RegExp(`-${frontPort}(?=\\.|$)`);
    const replacedHostname = hostname.replace(suffixRegex, "-8000");

    if (replacedHostname !== hostname) {
      return `${protocol}//${replacedHostname}`;
    }

    const prefixRegex = new RegExp(`^${frontPort}-`);
    const replacedPrefixHostname = hostname.replace(prefixRegex, "8000-");

    if (replacedPrefixHostname !== hostname) {
      return `${protocol}//${replacedPrefixHostname}`;
    }

    return window.location.origin;
  }

  return "http://localhost:8000";
};

export const api = axios.create({
  baseURL: resolveBaseURL()
});
