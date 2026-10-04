import type { Locale } from "../config";
import { ar } from "./ar";
import { en, type Messages } from "./en";

export type { Messages };
export const MESSAGES: Record<Locale, Messages> = { en, ar };
