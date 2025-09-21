export function formatCurrency(value: number | null | undefined) {
  const numeric = typeof value === "number" ? value : value ?? 0;
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(numeric);
}

export function formatSignedCurrency(value: number | null | undefined) {
  const numeric = typeof value === "number" ? value : value ?? 0;
  const formatted = formatCurrency(Math.abs(numeric));
  return numeric >= 0 ? formatted : `-${formatted}`;
}

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return value.toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatPercentage(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${value.toFixed(digits)}%`;
}

export function formatDate(value: string) {
  const date = new Date(value);
  return date.toLocaleDateString("fr-FR");
}

export function formatDateTime(value: string) {
  const date = new Date(value);
  return date.toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "short"
  });
}

export function toDateTimeLocalInput(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export function fromDateTimeLocalInput(value: string | null | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  return date.toISOString();
}
