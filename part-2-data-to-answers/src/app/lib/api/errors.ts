import type { Messages } from "@/lib/i18n/messages";
import { ApiError } from "./types";

/** A message in the visitor's language for any failure from the API. Server messages are English, so they are never shown directly. */
export function describeError(err: unknown, t: Messages): string {
  if (err instanceof ApiError) {
    switch (err.code) {
      case "agent_error": return t.errors.agent;
      case "busy": return t.errors.busy;
      case "stream_interrupted": return t.errors.streamBroken;
      case "upstream_error": return t.errors.upstream;
      case "invalid_request": return t.errors.rejected;
    }
    if (err.status === 401) return t.errors.sessionExpired;
    if (err.status === 403) return t.errors.forbidden;
    if (err.status === 409) return t.errors.conflict;
    if (err.status === 429) return t.errors.busy;
    if (err.status >= 500) return t.errors.upstream;
    if (err.status >= 400) return t.errors.rejected;
  }
  if (err instanceof TypeError) return t.errors.network; // fetch rejects with TypeError when the network is down
  return t.errors.generic;
}
