import axios from "axios";
import { resolveBaseURLFromConfig } from "./base-url";

const resolveBaseURL = (): string => {
  const envBase = process.env.NEXT_PUBLIC_API_BASE;

  if (typeof window !== "undefined") {
    const { protocol, hostname, port, origin } = window.location;

    return resolveBaseURLFromConfig(
      envBase,
      {
        protocol,
        hostname,
        port,
        origin
      }
    );
  }

  return resolveBaseURLFromConfig(envBase);
};

export const api = axios.create({
  baseURL: resolveBaseURL()
});
