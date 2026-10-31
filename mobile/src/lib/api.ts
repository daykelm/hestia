export const BASE = "https://hestia.trading";

export type Factor = {
  name: string;
  points: number;
  of: number;
  checked?: boolean;
  sources?: string[];
  note: string;
  flag?: string;
};

export type Diligence = {
  point?: [number, number];
  version?: number;
  score: number;
  band?: Band;
  band_label?: string;
  reason?: string;
  checked?: number;
  flags?: string[];
  identity?: { ok: boolean; note: string };
  house?: string;
  factors: Factor[];
};

export type Band = "excellent" | "good" | "fair" | "risky" | "thin";

export type Costs = {
  rows: { item: string; best: number; worst: number }[];
  best: number;
  worst: number;
  notes: string[];
  verdict: string;
  tone: "good" | "warn" | "stop" | "unknown";
  why: string;
  ceiling?: number;
  market_note?: string;
  value?: number;
  value_label?: string;
  value_note?: string;
};

export type Deal = {
  id: number;
  address: string;
  location: string;
  price: number | null;
  estimated_value: number | null;
  spread: number | null;
  source: string;
  notes: string;
  link: string;
  status: string;
  card?: { label: string; text: string }[];
  costs?: Partial<Costs>;
  street?: { name: string; url: string }[];
  street_view?: string;
  photo?: string;
  metadata: {
    county?: string;
    kind?: string;
    sale_date?: string;
    case?: string;
    parcel?: string;
    price_basis?: string;
    roll_value?: number | null;
    diligence?: Diligence;
    max_bid?: number;
    bid_url?: string;
    won_price?: number;
    buyer?: string;
    fee?: number;
  };
};

export type Guide = {
  steps: string[];
  step_guide: Record<string, string>;
  step_fields: Record<string, string[]>;
  bands: Record<Band, string>;
  help: Record<string, { title: string; text: string }>;
  factor_help: Record<string, string>;
  check_links: Record<string, { name: string; url: string }[]>;
  rules_version: number;
};

/** Cloudflare Access answers with its login page instead of JSON once the session runs out. */
export class SignedOut extends Error {}

async function read<T>(response: Response): Promise<T> {
  const type = response.headers.get("content-type") || "";
  if (response.url.includes("cloudflareaccess.com") || !type.includes("application/json")) {
    throw new SignedOut("Sign in again to reach hestia.trading.");
  }
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Hestia answered ${response.status}.`);
  return body as T;
}

export async function getJSON<T>(path: string): Promise<T> {
  return read<T>(await fetch(`${BASE}${path}`, { credentials: "include", headers: { Accept: "application/json" } }));
}

export async function postForm<T>(path: string, fields: Record<string, string | number | boolean | null | undefined> = {}): Promise<T> {
  const body = Object.entries(fields)
    .filter(([, value]) => value !== undefined && value !== null && value !== false && value !== "")
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value === true ? "1" : String(value))}`)
    .join("&");
  return read<T>(
    await fetch(`${BASE}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body,
    }),
  );
}

export const money = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

const UPPER = new Set(["N", "S", "E", "W", "NE", "NW", "SE", "SW", "FL", "US"]);

export function displayName(text: string) {
  return (text || "")
    .split(/\s+/)
    .map((word) => {
      const bare = word.replace(/[,#]/g, "");
      return UPPER.has(bare.toUpperCase()) || /\d/.test(bare) ? word : word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

export function displayPlace(location: string) {
  const [city, ...rest] = (location || "").split(",");
  const zip = rest.join(",").replace("FL-", "").replace("FL", "").trim();
  return [displayName(city.trim()), zip].filter(Boolean).join(" ");
}

export const band = (deal: Deal): Band | "" => {
  const d = deal.metadata.diligence;
  if (!d || !d.score) return "";
  return d.band || "thin";
};
