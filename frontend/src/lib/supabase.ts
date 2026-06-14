import { createClient } from "@supabase/supabase-js";

// These browser-safe fallbacks keep the public deployment usable when Vercel
// environment-variable scopes are accidentally omitted.
const url =
  process.env.NEXT_PUBLIC_SUPABASE_URL
  ?? "https://aetvmcpkczsawstpgoiq.supabase.co";
const publicKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ?? "sb_publishable_dNHL62Nr5q51I1nmtmyXPg_xrHAoO-j";

export const authConfigured = Boolean(url && publicKey);
export const supabase = createClient(
  url || "https://placeholder.supabase.co",
  publicKey || "placeholder-public-key",
);
