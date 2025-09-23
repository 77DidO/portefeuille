export interface LocationLike {
  protocol: string;
  hostname: string;
  port?: string;
  origin?: string;
}

const DEFAULT_FRONT_PORT = "3000";
const DEFAULT_BACKEND_PORT = "8000";

export const rewritePreviewHostname = (
  hostname: string,
  frontPort: string = DEFAULT_FRONT_PORT,
  backendPort: string = DEFAULT_BACKEND_PORT
): string => {
  const suffixRegex = new RegExp(`-${frontPort}(?=(?:-|\\.|$))`);
  const suffixReplaced = hostname.replace(suffixRegex, `-${backendPort}`);

  if (suffixReplaced !== hostname) {
    return suffixReplaced;
  }

  const prefixRegex = new RegExp(`^${frontPort}-`);
  const prefixReplaced = hostname.replace(prefixRegex, `${backendPort}-`);

  if (prefixReplaced !== hostname) {
    return prefixReplaced;
  }

  return hostname;
};

export const resolveBaseURLFromConfig = (
  envBase: string | undefined,
  location?: LocationLike,
  backendPort: string = DEFAULT_BACKEND_PORT,
  frontPort: string = DEFAULT_FRONT_PORT
): string => {
  if (envBase) {
    return envBase;
  }

  if (!location) {
    return `http://localhost:${backendPort}`;
  }

  const { protocol, hostname, port, origin } = location;

  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return `${protocol}//${hostname}:${backendPort}`;
  }

  if (port) {
    return `${protocol}//${hostname}:${backendPort}`;
  }

  const rewrittenHostname = rewritePreviewHostname(hostname, frontPort, backendPort);

  if (rewrittenHostname !== hostname) {
    return `${protocol}//${rewrittenHostname}`;
  }

  return origin ?? `${protocol}//${hostname}`;
};
