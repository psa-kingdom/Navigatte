/**
 * Canonical Date & Timezone Utilities for Navigatte Admin & Communications.
 *
 * Guarantees:
 * 1. Safely parses ISO-8601 strings from the backend, treating lack of timezone suffix
 *    as UTC ('Z') so browser never erroneously interprets UTC dates as local time.
 * 2. Formats date and time in the administrator's local browser timezone.
 * 3. Provides clean relative time ("2 mins ago", "1 hour ago") with full timestamp tooltip.
 */

export function parseUtcIso(isoStr) {
  if (!isoStr) return null;
  let s = String(isoStr).trim();
  if (!s) return null;
  // If string lacks 'Z' or timezone offset (+00:00 or -05:00), append 'Z' to force UTC parsing
  if (!s.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(s) && !/[+-]\d{4}$/.test(s)) {
    s += "Z";
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

export function formatLocalDateTime(isoStr, options = {}) {
  const d = parseUtcIso(isoStr);
  if (!d) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    ...options,
  });
}

export function formatLocalDate(isoStr, options = {}) {
  const d = parseUtcIso(isoStr);
  if (!d) return "—";
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...options,
  });
}

export function formatLocalTime(isoStr, options = {}) {
  const d = parseUtcIso(isoStr);
  if (!d) return "—";
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    ...options,
  });
}

export function formatRelativeTime(isoStr) {
  const d = parseUtcIso(isoStr);
  if (!d) return "—";
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);

  if (diffSec < 0) return "just now";
  if (diffSec < 45) return "just now";
  if (diffSec < 90) return "1 min ago";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} mins ago`;
  if (diffSec < 7200) return "1 hour ago";
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hours ago`;
  if (diffSec < 172800) return "yesterday";
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)} days ago`;

  return formatLocalDateTime(isoStr, { month: "short", day: "numeric" });
}

export function getFullTimezoneTooltip(isoStr) {
  const d = parseUtcIso(isoStr);
  if (!d) return "";
  const tzName = Intl.DateTimeFormat().resolvedOptions().timeZone || "Local";
  return `${formatLocalDateTime(isoStr)} (${tzName})`;
}
