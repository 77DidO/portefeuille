export function formatErrorDetail(detail: unknown, fallback = "Une erreur est survenue"): string {
  const messages = extractMessages(detail);
  if (messages.length > 0) {
    const uniqueMessages = Array.from(new Set(messages.map((msg) => msg.trim()).filter(Boolean)));
    if (uniqueMessages.length > 0) {
      return uniqueMessages.join("\n");
    }
  }
  return fallback;
}

function extractMessages(detail: unknown, seen = new Set<unknown>()): string[] {
  if (detail === null || detail === undefined) {
    return [];
  }

  if (typeof detail === "string") {
    return detail.trim() ? [detail.trim()] : [];
  }

  if (typeof detail === "number" || typeof detail === "boolean") {
    return [String(detail)];
  }

  if (typeof detail !== "object") {
    return [];
  }

  if (seen.has(detail)) {
    return [];
  }

  seen.add(detail);

  if (Array.isArray(detail)) {
    return detail.flatMap((item) => extractMessages(item, seen));
  }

  const obj = detail as Record<string, unknown>;

  if ("msg" in obj) {
    const msg = extractMessages(obj.msg, seen);
    if (msg.length > 0) {
      return msg;
    }
  }

  if ("detail" in obj) {
    const nested = extractMessages(obj.detail, seen);
    if (nested.length > 0) {
      return nested;
    }
  }

  return Object.values(obj).flatMap((value) => extractMessages(value, seen));
}
