import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const publicKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ?? "";

export const authConfigured = Boolean(url && publicKey);
export const supabase = createClient(
  url || "https://placeholder.supabase.co",
  publicKey || "placeholder-public-key",
);
