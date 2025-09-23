import axios from "axios";

const resolveBaseURL = (): string => {
  const envBase = process.env.NEXT_PUBLIC_API_BASE;
  if (envBase) {
    return envBase;
  }

  if (typeof window !== "undefined") {
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
      return "http://localhost:8000";
    }
    return window.location.origin;
  }

  return "http://localhost:8000";
};

export const api = axios.create({
  baseURL: resolveBaseURL()
});
