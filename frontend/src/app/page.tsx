"use client";

import axios from "axios";
import {
  AlertTriangle,
  Bell,
  BellRing,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  HeartPulse,
  LoaderCircle,
  LogOut,
  MessageCircle,
  Mic,
  MicOff,
  Plus,
  Phone,
  Pill,
  Volume2,
  VolumeX,
  Send,
  UploadCloud,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { Session } from "@supabase/supabase-js";
import { createContext, DragEvent, FormEvent, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { authConfigured, supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_OWNER_ID = "9000001";
const OwnerContext = createContext(DEMO_OWNER_ID);

function useOwnerId() {
  return useContext(OwnerContext);
}

type Tab = "chat" | "reports" | "medications" | "family" | "profile";
type Speaker = "user" | "assistant" | "system";
type PreferredLanguage = "en" | "hi";

const LANGUAGE_EVENT = "careos-language-change";

function subscribeLanguage(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(LANGUAGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(LANGUAGE_EVENT, onChange);
  };
}

function getLanguageSnapshot(): PreferredLanguage {
  return window.localStorage.getItem("careos-language") === "hi" ? "hi" : "en";
}

function getServerLanguageSnapshot(): PreferredLanguage {
  return "en";
}

type EmergencyDetails = {
  suspected: string;
  immediate_steps: string[];
  call_number: string;
};

type ChatReply = {
  message: string;
  agents_used: string[];
  steps_taken: string[];
  emergency: boolean;
  emergency_details: EmergencyDetails | null;
};

type ChatMessage = {
  id: string;
  speaker: Speaker;
  text: string;
  agents?: string[];
};

type InsightCard = {
  type: "medication_reminder" | "trend_positive" | "followup_question" | "report_alert";
  icon_emoji: string;
  text: string;
};

type Profile = {
  id: string | number;
  name: string;
  age?: number;
  gender?: string;
  blood_group?: string;
  known_conditions?: string[];
  allergies?: string[];
  emergency_contact?: string;
  emergency_contacts?: string | string[];
  relation?: string;
};

type Report = {
  id: string;
  report_type: string;
  report_date?: string;
  uploaded_at?: string;
  ai_summary: string;
  flagged_values?: Record<string, unknown>;
};

type Medication = {
  id: string;
  drug_name: string;
  dose: string;
  frequency: string;
  timing?: string[];
  with_food?: boolean;
};

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
};

function responseLanguage(text: string, preferredLanguage: PreferredLanguage): PreferredLanguage {
  return preferredLanguage === "hi" || /[\u0900-\u097f]/.test(text) ? "hi" : "en";
}

async function createCareOSAudio(text: string, preferredLanguage: PreferredLanguage) {
  const { data } = await axios.post(
    `${API_URL}/text-to-speech`,
    { text, lang: responseLanguage(text, preferredLanguage) },
    { responseType: "blob" },
  );
  const url = URL.createObjectURL(data);
  return { audio: new Audio(url), url };
}

const navigation = [
  { id: "chat" as const, label: "Chat", icon: MessageCircle },
  { id: "reports" as const, label: "Reports", icon: FileText },
  { id: "medications" as const, label: "Medications", icon: Pill },
  { id: "family" as const, label: "Family", icon: Users },
  { id: "profile" as const, label: "Profile", icon: UserRound },
];

const tabTitles: Record<Exclude<Tab, "chat">, string> = {
  reports: "Reports",
  medications: "Medications",
  family: "Family",
  profile: "Profile",
};

export default function Home() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [ownerId, setOwnerId] = useState("");
  const [accountError, setAccountError] = useState("");

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) setSession(data.session);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setAccountError("");
      if (!nextSession) setOwnerId("");
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!session) return;
    axios.post<Profile>(
      `${API_URL}/auth/profile`,
      {},
      { headers: { Authorization: `Bearer ${session.access_token}` } },
    )
      .then(({ data }) => setOwnerId(String(data.id)))
      .catch((error) => {
        const detail = axios.isAxiosError(error) && error.response?.data?.detail;
        setAccountError(typeof detail === "string" ? detail : "CareOS could not prepare this account.");
      });
  }, [session]);

  async function signOut() {
    await supabase.auth.signOut();
    setOwnerId("");
  }

  if (session === undefined) return <AuthLoading />;
  if (ownerId) {
    return (
      <OwnerContext.Provider value={ownerId}>
        <CareOSApp onSignOut={signOut} />
      </OwnerContext.Provider>
    );
  }
  if (accountError) return <AuthSetupError detail={accountError} onSignOut={signOut} onDemo={() => { setAccountError(""); setOwnerId(DEMO_OWNER_ID); }} />;
  if (session) return <AuthLoading />;
  return <AuthScreen onDemo={() => setOwnerId(DEMO_OWNER_ID)} />;
}

function CareOSApp({ onSignOut }: { onSignOut: () => Promise<void> }) {
  const OWNER_ID = useOwnerId();
  const [tab, setTab] = useState<Tab>("chat");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [greetingLoading, setGreetingLoading] = useState(true);
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const [insightCards, setInsightCards] = useState<InsightCard[]>([]);
  const [digestLoading, setDigestLoading] = useState(true);
  const [listening, setListening] = useState(false);
  const [voiceSendSeconds, setVoiceSendSeconds] = useState<number | null>(null);
  const preferredLanguage = useSyncExternalStore(
    subscribeLanguage,
    getLanguageSnapshot,
    getServerLanguageSnapshot,
  );
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profileError, setProfileError] = useState("");
  const [emergency, setEmergency] = useState<EmergencyDetails | null>(null);
  const [activeProfile, setActiveProfile] = useState<Profile>({ id: OWNER_ID, name: "My profile" });
  const [ownerProfile, setOwnerProfile] = useState<Profile>({ id: OWNER_ID, name: "My profile" });
  const [family, setFamily] = useState<Profile[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const greetingScopeRef = useRef<string | null>(null);
  const activeProfileScopeRef = useRef(OWNER_ID);
  const greetingAudioRef = useRef<HTMLAudioElement | null>(null);
  const responseAudioRef = useRef<HTMLAudioElement | null>(null);
  const followUpEventIdRef = useRef<string | null>(null);
  const voiceTranscriptRef = useRef("");
  const voiceSendTimerRef = useRef<number | null>(null);
  const voiceCountdownRef = useRef<number | null>(null);
  const conversationEnd = useRef<HTMLDivElement>(null);
  const activeProfileId = String(activeProfile.id);
  const familyMemberId = activeProfileId === OWNER_ID ? undefined : activeProfileId;

  useEffect(() => {
    conversationEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    return () => {
      if (voiceSendTimerRef.current !== null) window.clearTimeout(voiceSendTimerRef.current);
      if (voiceCountdownRef.current !== null) window.clearInterval(voiceCountdownRef.current);
      responseAudioRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    Promise.all([
      axios.get<Profile>(`${API_URL}/profile/${OWNER_ID}`),
      axios.get<Profile[]>(`${API_URL}/family/${OWNER_ID}`),
    ])
      .then(([profileResponse, familyResponse]) => {
        setOwnerProfile(profileResponse.data);
        setActiveProfile(profileResponse.data);
        setFamily(familyResponse.data);
      })
      .catch(() => setProfileError("Demo profile could not be loaded. Check the backend and Supabase connection."))
      .finally(() => setProfilesLoading(false));
  }, [OWNER_ID]);

  useEffect(() => {
    const scope = `${activeProfileId}:${preferredLanguage}`;
    if (greetingScopeRef.current === scope) return;
    greetingScopeRef.current = scope;
    setGreetingLoading(true);
    followUpEventIdRef.current = null;
    responseAudioRef.current?.pause();
    const controller = new AbortController();

    axios.get<{ greeting: string; follow_up_event_id: string | null }>(`${API_URL}/greeting/${OWNER_ID}`, {
      params: {
        family_member_id: familyMemberId,
        preferred_language: preferredLanguage,
      },
      signal: controller.signal,
    })
      .then(async ({ data }) => {
        if (greetingScopeRef.current !== scope) return;
        followUpEventIdRef.current = data.follow_up_event_id;
        setMessages([{
          id: "proactive-greeting",
          speaker: "assistant" as const,
          text: data.greeting,
          agents: ["care_coordinator"],
        }]);

        // Browsers may require a prior tap for autoplay; manual speaker playback remains available.
        const { audio, url } = await createCareOSAudio(data.greeting, preferredLanguage);
        if (greetingScopeRef.current !== scope) {
          URL.revokeObjectURL(url);
          return;
        }
        greetingAudioRef.current = audio;
        audio.onended = () => URL.revokeObjectURL(url);
        audio.onerror = () => URL.revokeObjectURL(url);
        try {
          await audio.play();
        } catch {
          // Autoplay may be blocked until the first user interaction.
        }
      })
      .catch((error) => {
        if (axios.isCancel(error) || greetingScopeRef.current !== scope) return;
        setMessages([{
          id: "welcome-fallback",
          speaker: "assistant",
          text: preferredLanguage === "hi"
            ? "नमस्ते, मैं CareOS हूँ। पिछली बातचीत के बाद से आपकी तबीयत कैसी रही है?"
            : "Hi, I am CareOS. How have you been feeling since your last check-in?",
          agents: ["care_coordinator"],
        }]);
      })
      .finally(() => {
        if (greetingScopeRef.current === scope) setGreetingLoading(false);
      });

    return () => {
      controller.abort();
      greetingAudioRef.current?.pause();
    };
  }, [OWNER_ID, activeProfileId, familyMemberId, preferredLanguage]);

  useEffect(() => {
    const scope = `${activeProfileId}:${preferredLanguage}`;
    const controller = new AbortController();
    axios.get<InsightCard[]>(`${API_URL}/daily-digest/${OWNER_ID}`, {
      params: {
        family_member_id: familyMemberId,
        preferred_language: preferredLanguage,
      },
      signal: controller.signal,
    })
      .then(({ data }) => {
        if (`${String(activeProfile.id)}:${preferredLanguage}` === scope) setInsightCards(data);
      })
      .catch((error) => {
        if (!axios.isCancel(error) && activeProfileScopeRef.current === activeProfileId) {
          setInsightCards([]);
        }
      })
      .finally(() => {
        if (activeProfileScopeRef.current === activeProfileId) setDigestLoading(false);
      });
    return () => controller.abort();
  }, [OWNER_ID, activeProfile.id, activeProfileId, familyMemberId, preferredLanguage]);

  function setPreferredLanguage(language: PreferredLanguage) {
    window.localStorage.setItem("careos-language", language);
    window.dispatchEvent(new Event(LANGUAGE_EVENT));
  }

  function selectActiveProfile(profile: Profile) {
    cancelVoiceAutoSend();
    responseAudioRef.current?.pause();
    setMessages([]);
    setInsightCards([]);
    setDigestLoading(true);
    activeProfileScopeRef.current = String(profile.id);
    setActiveProfile(profile);
    setTab("chat");
  }

  function cancelVoiceAutoSend() {
    if (voiceSendTimerRef.current !== null) window.clearTimeout(voiceSendTimerRef.current);
    if (voiceCountdownRef.current !== null) window.clearInterval(voiceCountdownRef.current);
    voiceSendTimerRef.current = null;
    voiceCountdownRef.current = null;
    setVoiceSendSeconds(null);
  }

  function handleInput(value: string) {
    cancelVoiceAutoSend();
    setInput(value);
  }

  async function speakCareOS(text: string) {
    responseAudioRef.current?.pause();
    try {
      const { audio, url } = await createCareOSAudio(text, preferredLanguage);
      responseAudioRef.current = audio;
      audio.onended = () => URL.revokeObjectURL(url);
      audio.onerror = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch {
      // Manual playback remains available when browser autoplay is blocked.
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    await sendPrompt(text);
  }

  async function sendPrompt(text: string) {
    if (!text || loading) return;
    const requestProfileScope = activeProfileScopeRef.current;

    cancelVoiceAutoSend();
    setInput("");
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), speaker: "user", text },
    ]);
    setLoading(true);

    try {
      const { data } = await axios.post<ChatReply>(`${API_URL}/chat`, {
        message: text,
        profile_id: OWNER_ID,
        family_member_id: familyMemberId,
        preferred_language: preferredLanguage,
        previous_assistant_message: [...messages].reverse().find((message) => message.speaker === "assistant")?.text,
        follow_up_event_id: followUpEventIdRef.current,
      });
      if (activeProfileScopeRef.current !== requestProfileScope) return;
      if (data.message.toLowerCase().includes("mark this symptom as resolved") || data.message.includes("ठीक हुआ दर्ज")) {
        followUpEventIdRef.current = null;
      }
      if (data.steps_taken.length > 1) {
        setLoading(false);
        for (const step of data.steps_taken) {
          setThinkingSteps((current) => [...current, step]);
          await new Promise((resolve) => window.setTimeout(resolve, 700));
        }
        setThinkingSteps((current) => [...current, "Done"]);
        await new Promise((resolve) => window.setTimeout(resolve, 500));
      }
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          speaker: "assistant",
          text: data.message,
          agents: data.agents_used,
        },
      ]);
      void speakCareOS(data.message);
      setThinkingSteps([]);
      if (data.emergency) {
        setEmergency(
          data.emergency_details ?? {
            suspected: "Urgent medical concern",
            immediate_steps: ["Call emergency services now."],
            call_number: "112",
          },
        );
      }
    } catch (error) {
      if (activeProfileScopeRef.current !== requestProfileScope) return;
      setThinkingSteps([]);
      const detail = axios.isAxiosError(error) && error.response?.data?.detail;
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          speaker: "system",
          text: typeof detail === "string"
            ? `CareOS service error: ${detail}`
            : "CareOS could not reach the health service. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function addSystemMessage(text: string) {
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), speaker: "system", text },
    ]);
  }

  async function toggleVoiceInput() {
    cancelVoiceAutoSend();
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const SpeechRecognition = (
      window as typeof window & {
        SpeechRecognition?: new () => SpeechRecognitionInstance;
        webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
      }
    ).SpeechRecognition ?? (
      window as typeof window & {
        webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
      }
    ).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      addSystemMessage("Voice input is not supported in this browser. Try Chrome or Edge.");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      addSystemMessage("This browser cannot access a microphone. Check browser permissions or try Chrome or Edge.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
    } catch {
      addSystemMessage("Microphone access is blocked. Allow microphone permission for this site, then tap the microphone again.");
      return;
    }

    const recognition = new SpeechRecognition();
    voiceTranscriptRef.current = "";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = preferredLanguage === "hi" ? "hi-IN" : "en-IN";
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim();
      voiceTranscriptRef.current = transcript;
      setInput(transcript);
    };
    recognition.onend = () => {
      setListening(false);
      const transcript = voiceTranscriptRef.current.trim();
      if (!transcript) return;
      let seconds = 10;
      setVoiceSendSeconds(seconds);
      voiceCountdownRef.current = window.setInterval(() => {
        seconds -= 1;
        setVoiceSendSeconds(Math.max(seconds, 0));
      }, 1000);
      voiceSendTimerRef.current = window.setTimeout(() => {
        cancelVoiceAutoSend();
        void sendPrompt(transcript);
      }, 10_000);
    };
    recognition.onerror = (event) => {
      cancelVoiceAutoSend();
      setListening(false);
      const errors: Record<string, string> = {
        "not-allowed": "Microphone access was denied. Allow it in the browser's site permissions and try again.",
        "audio-capture": "CareOS could not find an available microphone.",
        "no-speech": "No speech was detected. Tap the microphone and try speaking again.",
        network: "Voice recognition could not reach the browser speech service. Check your connection.",
      };
      addSystemMessage(errors[event.error] ?? "Voice input stopped unexpectedly. Please try again.");
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true);
    } catch {
      addSystemMessage("Voice input could not start. Please wait a moment and try again.");
    }
  }

  return (
    <main className="h-dvh bg-[#f8faf9] text-[#17211d]">
      <div className="mx-auto flex h-screen max-w-7xl overflow-hidden bg-white md:my-4 md:h-[calc(100vh-32px)] md:rounded-2xl md:border md:border-[#dfe8e4] md:shadow-xl">
        <DesktopNavigation active={tab} onChange={setTab} />

        <section className="relative flex h-full min-w-0 flex-1 flex-col">
          <Header tab={tab} activeProfile={activeProfile} onSignOut={onSignOut} />
          {(profilesLoading || profileError) && (
            <ServiceNotice loading={profilesLoading} error={profileError} />
          )}
          {tab === "chat" ? (
            <ChatScreen
              input={input}
              loading={loading}
              greetingLoading={greetingLoading}
              thinkingSteps={thinkingSteps}
              insightCards={insightCards}
              digestLoading={digestLoading}
              listening={listening}
              preferredLanguage={preferredLanguage}
              messages={messages}
              conversationEnd={conversationEnd}
              onInput={handleInput}
              voiceSendSeconds={voiceSendSeconds}
              onCancelVoiceSend={cancelVoiceAutoSend}
              onSend={sendMessage}
              onVoice={toggleVoiceInput}
              onLanguage={setPreferredLanguage}
              onInsight={sendPrompt}
            />
          ) : tab === "reports" ? (
            <ReportsScreen familyMemberId={familyMemberId} />
          ) : tab === "medications" ? (
            <MedicationsScreen familyMemberId={familyMemberId} />
          ) : tab === "family" ? (
            <FamilyScreen
              activeProfile={activeProfile}
              family={family}
              owner={ownerProfile}
              onFamilyChange={setFamily}
              onSelect={selectActiveProfile}
            />
          ) : (
            <ProfileScreen profile={activeProfile} familyMemberId={familyMemberId} />
          )}
          <MobileNavigation active={tab} onChange={setTab} />
        </section>
      </div>

      {emergency && (
        <EmergencyOverlay details={emergency} onClose={() => setEmergency(null)} />
      )}
    </main>
  );
}

function AuthLoading() {
  return (
    <main className="grid min-h-dvh place-items-center bg-[#f4f8f6] text-[#12664f]">
      <div className="flex items-center gap-3 text-sm font-semibold">
        <LoaderCircle className="animate-spin" size={20} />
        Opening CareOS...
      </div>
    </main>
  );
}

function AuthSetupError({ detail, onSignOut, onDemo }: { detail: string; onSignOut: () => Promise<void>; onDemo: () => void }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-[#f4f8f6] px-4 text-[#17211d]">
      <section className="w-full max-w-md rounded-md border border-[#e4c98c] bg-white p-6 shadow-lg">
        <HeartPulse className="text-[#12664f]" />
        <h1 className="mt-4 text-xl font-semibold">Account setup needs attention</h1>
        <p className="mt-2 text-sm leading-6 text-[#687971]">{detail}</p>
        <p className="mt-3 text-xs leading-5 text-[#687971]">Run the latest <code>supabase_schema_fix.sql</code> in Supabase, then sign in again.</p>
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={() => void onSignOut()} className="h-10 flex-1 rounded-md bg-[#12664f] text-sm font-semibold text-white">Sign out</button>
          <button type="button" onClick={onDemo} className="h-10 flex-1 rounded-md border border-[#12664f] text-sm font-semibold text-[#12664f]">Use demo</button>
        </div>
      </section>
    </main>
  );
}

function AuthScreen({ onDemo }: { onDemo: () => void }) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!authConfigured) {
      setError("Add the public Supabase URL and anon key to frontend/.env.local to enable accounts.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "signup") {
        const { data, error: authError } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { name: name.trim() } },
        });
        if (authError) throw authError;
        if (!data.session) {
          setNotice("Account created. Check your email to confirm it, then sign in.");
          setMode("signin");
        }
      } else {
        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
        if (authError) throw authError;
      }
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-dvh bg-[#f4f8f6] px-4 py-8 text-[#17211d]">
      <div className="mx-auto grid min-h-[calc(100vh-64px)] max-w-5xl overflow-hidden rounded-lg border border-[#d9e5df] bg-white shadow-xl md:grid-cols-[1.05fr_0.95fr]">
        <section className="flex flex-col justify-between bg-[#12664f] p-7 text-white sm:p-10">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-md bg-white/15"><HeartPulse size={25} /></span>
            <span className="text-xl font-semibold">CareOS</span>
          </div>
          <div className="my-12 max-w-md">
            <h1 className="text-3xl font-semibold leading-tight sm:text-4xl">Your family&apos;s health context, remembered carefully.</h1>
            <p className="mt-5 text-sm leading-6 text-white/75">Sign in to keep conversations, reports, medicines, and family profiles separated and available when you return.</p>
          </div>
          <p className="text-xs text-white/60">Emergency-first healthcare companion</p>
        </section>

        <section className="flex items-center p-6 sm:p-10">
          <div className="w-full">
            <div className="grid grid-cols-2 rounded-md border border-[#cfdad5] p-1">
              {(["signin", "signup"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => { setMode(value); setError(""); setNotice(""); }}
                  className={`h-10 rounded-md text-sm font-semibold ${mode === value ? "bg-[#12664f] text-white" : "text-[#53665d]"}`}
                >
                  {value === "signin" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>
            <form onSubmit={submit} className="mt-7 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">{mode === "signin" ? "Welcome back" : "Start your CareOS profile"}</h2>
                <p className="mt-1 text-sm text-[#687971]">{mode === "signin" ? "Continue your private health workspace." : "Create a separate workspace for your health and family."}</p>
              </div>
              {mode === "signup" && <TextInput label="Full name" value={name} onChange={setName} required />}
              <label className="block text-xs font-medium text-[#596b62]">Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-[#cfdad5] px-3 text-sm outline-none focus:border-[#12664f]" /></label>
              <label className="block text-xs font-medium text-[#596b62]">Password<input required minLength={6} type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-[#cfdad5] px-3 text-sm outline-none focus:border-[#12664f]" /></label>
              {notice && <p className="rounded-md border border-[#b8d8ca] bg-[#f1f8f5] p-3 text-xs leading-5 text-[#12664f]">{notice}</p>}
              <ErrorText text={error} />
              <button disabled={busy} className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-[#12664f] text-sm font-semibold text-white disabled:opacity-50">
                {busy && <LoaderCircle className="animate-spin" size={17} />}
                {busy ? "Please wait..." : mode === "signin" ? "Sign in" : "Create account"}
              </button>
            </form>
            <div className="my-6 flex items-center gap-3 text-xs text-[#87958e]"><span className="h-px flex-1 bg-[#dfe8e4]" />or<span className="h-px flex-1 bg-[#dfe8e4]" /></div>
            <button type="button" onClick={onDemo} className="h-11 w-full rounded-md border border-[#12664f] text-sm font-semibold text-[#12664f] hover:bg-[#f1f8f5]">
              Continue with Ramesh demo
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}

function DailyDigest({
  cards,
  loading,
  preferredLanguage,
  onSelect,
}: {
  cards: InsightCard[];
  loading: boolean;
  preferredLanguage: PreferredLanguage;
  onSelect: (text: string) => void;
}) {
  const styles: Record<InsightCard["type"], string> = {
    medication_reminder: "border-[#b9d5e7] bg-[#eef7fc]",
    trend_positive: "border-[#bcdcc9] bg-[#eef8f2]",
    followup_question: "border-[#ead39a] bg-[#fff8e7]",
    report_alert: "border-[#efc0b8] bg-[#fff2ef]",
  };
  if (loading) {
    return <div className="h-20 animate-pulse rounded-md bg-[#eef3f0]" aria-label="Loading daily insights" />;
  }
  return (
    <section aria-label={preferredLanguage === "hi" ? "आज की स्वास्थ्य जानकारी" : "Today's health insights"}>
      <p className="mb-2 text-xs font-semibold uppercase text-[#60736a]">
        {preferredLanguage === "hi" ? "आज की जानकारी" : "Today"}
      </p>
      <div className="flex snap-x gap-2 overflow-x-auto pb-2">
        {cards.map((card, index) => (
          <button
            key={`${card.type}-${index}`}
            type="button"
            onClick={() => onSelect(card.text)}
            className={`min-w-56 snap-start rounded-md border p-3 text-left text-sm leading-5 transition hover:-translate-y-0.5 ${styles[card.type]}`}
          >
            <span className="mb-2 block text-lg" aria-hidden="true">{card.icon_emoji}</span>
            {card.text}
          </button>
        ))}
      </div>
    </section>
  );
}

function Header({ tab, activeProfile, onSignOut }: { tab: Tab; activeProfile: Profile; onSignOut: () => Promise<void> }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-[#f1f5f3] px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-md bg-[#12664f] text-white">
          <HeartPulse size={20} />
        </span>
        <div>
          <p className="text-sm font-semibold sm:text-base">CareOS</p>
          <p className="text-xs text-[#6b7b74]">
            {tab === "chat" ? "Health conversation" : tabTitles[tab]}
          </p>
        </div>
      </div>
      <div className="flex min-w-0 items-center gap-2">
        <span className="max-w-32 truncate text-xs font-medium text-[#53665d]">{activeProfile.name}</span>
        <button
          type="button"
          onClick={() => void onSignOut()}
          title="Sign out"
          aria-label="Sign out"
          className="grid size-9 shrink-0 place-items-center rounded-md text-[#53665d] hover:bg-[#edf4f1] hover:text-[#12664f]"
        >
          <LogOut size={17} />
        </button>
      </div>
    </header>
  );
}

function ChatScreen({
  input,
  loading,
  greetingLoading,
  thinkingSteps,
  insightCards,
  digestLoading,
  listening,
  preferredLanguage,
  messages,
  conversationEnd,
  onInput,
  onSend,
  onVoice,
  onLanguage,
  onInsight,
  voiceSendSeconds,
  onCancelVoiceSend,
}: {
  input: string;
  loading: boolean;
  greetingLoading: boolean;
  thinkingSteps: string[];
  insightCards: InsightCard[];
  digestLoading: boolean;
  listening: boolean;
  preferredLanguage: PreferredLanguage;
  messages: ChatMessage[];
  conversationEnd: React.RefObject<HTMLDivElement | null>;
  onInput: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onVoice: () => void;
  onLanguage: (language: PreferredLanguage) => void;
  onInsight: (text: string) => void;
  voiceSendSeconds: number | null;
  onCancelVoiceSend: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          <div className="mb-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-semibold">{preferredLanguage === "hi" ? "आज आप कैसा महसूस कर रहे हैं?" : "How are you feeling today?"}</h1>
                <p className="mt-1 text-sm text-[#687971]">
                  {preferredLanguage === "hi" ? "CareOS हर संदेश में पहले आपात संकेतों की जाँच करता है।" : "CareOS checks every message for urgent warning signs first."}
                </p>
              </div>
              <div className="flex h-9 rounded-md border border-[#cfdad5] p-0.5" aria-label="Conversation language">
                {(["en", "hi"] as PreferredLanguage[]).map((language) => (
                  <button
                    key={language}
                    type="button"
                    onClick={() => onLanguage(language)}
                    className={`min-w-14 rounded px-3 text-xs font-semibold ${preferredLanguage === language ? "bg-[#12664f] text-white" : "text-[#5e7168]"}`}
                  >
                    {language === "en" ? "English" : "हिंदी"}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {(digestLoading || insightCards.length > 0) && (
            <DailyDigest
              cards={insightCards}
              loading={digestLoading}
              preferredLanguage={preferredLanguage}
              onSelect={onInsight}
            />
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} preferredLanguage={preferredLanguage} />
          ))}
          {!!thinkingSteps.length && (
            <ThinkingTrail steps={thinkingSteps} preferredLanguage={preferredLanguage} />
          )}
          {(loading || greetingLoading) && <TypingIndicator />}
          <div ref={conversationEnd} />
        </div>
      </div>

      <div className="shrink-0 bg-white px-4 pb-6 pt-2 sm:px-8">
        <form onSubmit={onSend} className="relative mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-[#dfe8e4] bg-[#fcfdfe] p-2 shadow-sm transition-all focus-within:border-[#12664f] focus-within:ring-4 focus-within:ring-[#12664f]/5">
          <button
            type="button"
            onClick={onVoice}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            title={listening ? "Stop voice input" : "Start voice input"}
            className={`grid size-10 shrink-0 place-items-center rounded-xl transition ${
              listening
                ? "animate-pulse bg-red-50 text-red-600"
                : "text-[#566a60] hover:bg-gray-100"
            }`}
          >
            {listening ? <MicOff size={19} /> : <Mic size={19} />}
          </button>
          <textarea
            value={input}
            onChange={(event) => onInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={1}
            placeholder={listening ? (preferredLanguage === "hi" ? "सुन रहा हूँ..." : "Listening...") : (preferredLanguage === "hi" ? "लक्षण बताएँ या स्वास्थ्य प्रश्न पूछें" : "Describe symptoms or ask a health question")}
            className="max-h-48 min-h-10 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-gray-400"
          />
          <button
            disabled={!input.trim() || loading}
            aria-label="Send message"
            title="Send message"
            className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#12664f] text-white transition hover:bg-[#0e5743] disabled:cursor-not-allowed disabled:opacity-30"
          >
            <Send size={18} />
          </button>
        </form>
        {voiceSendSeconds !== null && (
          <div className="mx-auto mt-2 flex max-w-3xl items-center justify-between rounded-md bg-[#eef7f3] px-3 py-2 text-xs text-[#45665a]">
            <span>
              {preferredLanguage === "hi"
                ? `आवाज़ संदेश ${voiceSendSeconds} सेकंड में भेजा जाएगा`
                : `Voice message will send automatically in ${voiceSendSeconds}s`}
            </span>
            <button
              type="button"
              onClick={onCancelVoiceSend}
              className="font-semibold text-[#12664f]"
            >
              {preferredLanguage === "hi" ? "रोकें" : "Cancel"}
            </button>
          </div>
        )}
        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-[#809087]">
          CareOS provides general health information, not a diagnosis.
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message, preferredLanguage }: { message: ChatMessage; preferredLanguage: PreferredLanguage }) {
  const isUser = message.speaker === "user";
  const isSystem = message.speaker === "system";
  const [generatingVoice, setGeneratingVoice] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  async function toggleSpeech() {
    if (speaking) {
      audioRef.current?.pause();
      setSpeaking(false);
      return;
    }

    audioRef.current?.pause();
    setVoiceError("");
    setGeneratingVoice(true);
    try {
      const { audio, url } = await createCareOSAudio(message.text, preferredLanguage);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setSpeaking(false);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setSpeaking(false);
        setVoiceError("CareOS could not play this voice response.");
      };
      setGeneratingVoice(false);
      setSpeaking(true);
      await audio.play();
    } catch (error) {
      setGeneratingVoice(false);
      setSpeaking(false);
      const detail = axios.isAxiosError(error) && error.response?.data?.detail;
      setVoiceError(typeof detail === "string" ? detail : "CareOS could not generate this voice response.");
    }
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`message-bubble-in max-w-[88%] rounded-2xl px-5 py-3.5 text-sm leading-6 sm:max-w-[80%] ${
          isUser
            ? "rounded-tr-none bg-[#12664f] text-white"
            : isSystem
              ? "border border-amber-100 bg-amber-50 text-amber-900"
              : "rounded-tl-none bg-[#f1f5f3] text-[#24322c]"
        }`}
      >
        {!isUser && !isSystem && (
          <div className="mb-1 flex items-center justify-between gap-3">
            <p className="text-xs font-semibold text-[#12664f]">CareOS</p>
            <button
              type="button"
              onClick={toggleSpeech}
              disabled={generatingVoice}
              aria-label={generatingVoice ? "Generating voice output" : speaking ? "Stop voice output" : "Read response aloud"}
              title={generatingVoice ? "Generating voice output" : speaking ? "Stop voice output" : "Read response aloud"}
              className="grid size-7 shrink-0 place-items-center rounded-lg text-[#597269] hover:bg-white/50"
            >
              {generatingVoice ? <LoaderCircle className="animate-spin" size={16} /> : speaking ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
        {!!message.agents?.length && (
          <p className={`mt-2 text-[11px] ${isUser ? "text-white/70" : "text-[#71827a]"}`}>
            {message.agents.map((agent) => agent.replaceAll("_", " ")).join(" + ")}
          </p>
        )}
        {voiceError && <p className="mt-2 text-[11px] text-[#9b3a28]">{voiceError}</p>}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start" aria-label="CareOS is typing">
      <div className="flex h-10 items-center gap-1 rounded-2xl bg-[#f1f5f3] px-5">
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="typing-dot size-1.5 rounded-full bg-[#5f756a]"
            style={{ animationDelay: `${dot * 160}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

function ThinkingTrail({
  steps,
  preferredLanguage,
}: {
  steps: string[];
  preferredLanguage: PreferredLanguage;
}) {
  const labels: Record<string, { icon: React.ReactNode; hi: string }> = {
    "Analyzing symptoms": { icon: <HeartPulse size={15} />, hi: "लक्षणों का विश्लेषण कर रहा हूँ" },
    "Checking your medications": { icon: <Pill size={15} />, hi: "आपकी दवाओं की जाँच कर रहा हूँ" },
    "Finding the right specialist": { icon: <UserRound size={15} />, hi: "सही विशेषज्ञ ढूँढ रहा हूँ" },
    "Updating your health timeline": { icon: <FileText size={15} />, hi: "आपकी स्वास्थ्य समयरेखा अपडेट कर रहा हूँ" },
    "Running OPQRST assessment": { icon: <HeartPulse size={15} />, hi: "OPQRST लक्षण आकलन कर रहा हूँ" },
    Done: { icon: <HeartPulse size={15} />, hi: "पूरा हुआ" },
  };
  return (
    <div className="flex flex-col gap-1.5 px-1 text-xs text-[#5f756a]" aria-label="CareOS agent activity">
      {steps.map((step, index) => {
        const detail = labels[step] ?? { icon: <LoaderCircle size={15} />, hi: step };
        return (
          <div key={`${step}-${index}`} className="thinking-step flex items-center gap-2">
            <span className="text-[#12664f]">{detail.icon}</span>
            <span>{preferredLanguage === "hi" ? detail.hi : step}{step === "Done" ? "" : "..."}</span>
          </div>
        );
      })}
    </div>
  );
}

function EmergencyOverlay({
  details,
  onClose,
}: {
  details: EmergencyDetails;
  onClose: () => void;
}) {
  const number = details.call_number.match(/\d+/)?.[0] ?? "112";
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[#9d2518] px-4 py-6 text-white">
      <div className="mx-auto flex min-h-full max-w-xl flex-col justify-center">
        <button
          onClick={onClose}
          aria-label="Close emergency alert"
          title="Close emergency alert"
          className="absolute right-4 top-4 grid size-10 place-items-center rounded-md bg-black/20 hover:bg-black/30"
        >
          <X size={22} />
        </button>
        <AlertTriangle size={54} />
        <p className="mt-5 text-sm font-bold uppercase">Emergency alert</p>
        <h2 className="mt-2 text-3xl font-bold leading-tight">{details.suspected}</h2>
        <ol className="mt-7 space-y-3 border-y border-white/30 py-5">
          {details.immediate_steps.map((step, index) => (
            <li key={step} className="flex gap-3 text-base leading-6">
              <span className="font-bold">{index + 1}.</span>
              {step}
            </li>
          ))}
        </ol>
        <a
          href={`tel:${number}`}
          className="mt-7 flex h-14 items-center justify-center gap-3 rounded-md bg-white text-lg font-bold text-[#9d2518]"
        >
          <Phone size={22} />
          Call {number}
        </a>
        <button onClick={onClose} className="mt-3 h-11 text-sm font-semibold text-white/80">
          Return to chat
        </button>
      </div>
    </div>
  );
}

function ReportsScreen({ familyMemberId }: { familyMemberId?: string }) {
  const OWNER_ID = useOwnerId();
  const [reports, setReports] = useState<Report[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    axios
      .get<Report[]>(`${API_URL}/reports/${OWNER_ID}`, {
        params: { family_member_id: familyMemberId },
        signal: controller.signal,
      })
      .then(({ data }) => setReports(data))
      .catch((error) => {
        if (!axios.isCancel(error)) setError("Could not load reports.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setInitialLoading(false);
      });
    return () => controller.abort();
  }, [OWNER_ID, familyMemberId]);

  async function loadReports() {
    try {
      const { data } = await axios.get<Report[]>(`${API_URL}/reports/${OWNER_ID}`, {
        params: { family_member_id: familyMemberId },
      });
      setReports(data);
    } catch {
      setError("Could not load reports.");
    }
  }

  async function upload(file?: File) {
    if (!file || file.type !== "application/pdf") {
      setError("Please select a PDF report.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Please select a PDF smaller than 10 MB.");
      return;
    }
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("profile_id", OWNER_ID);
    form.append("report_type", "blood report");
    if (familyMemberId) form.append("family_member_id", familyMemberId);
    try {
      await axios.post(`${API_URL}/upload-report`, form);
      await loadReports();
    } catch (error) {
      const detail = axios.isAxiosError(error) && error.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "CareOS could not upload or analyze this report.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell title="Medical reports" description="Upload PDFs and review CareOS analysis.">
      <input
        ref={fileInput}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(event) => upload(event.target.files?.[0])}
      />
      <button
        onClick={() => fileInput.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event: DragEvent<HTMLButtonElement>) => {
          event.preventDefault();
          upload(event.dataTransfer.files[0]);
        }}
        className="flex min-h-36 w-full flex-col items-center justify-center rounded-md border border-dashed border-[#9eb9ad] bg-[#f4f8f6] px-5 text-center hover:border-[#12664f]"
      >
        {busy ? <LoaderCircle className="animate-spin text-[#12664f]" /> : <UploadCloud className="text-[#12664f]" />}
        <span className="mt-3 text-sm font-semibold">{busy ? "Analyzing report..." : "Drop a PDF here or browse"}</span>
        <span className="mt-1 text-xs text-[#71827a]">Gemini reads the original PDF and saves its summary.</span>
      </button>
      <ErrorText text={error} />
      <div className="space-y-3">
        {reports.map((report) => (
          <article key={report.id} className="rounded-md border border-[#dfe8e4] p-4">
            <button className="flex w-full items-start justify-between gap-3 text-left" onClick={() => setExpanded(expanded === report.id ? null : report.id)}>
              <div>
                <p className="text-sm font-semibold">{report.report_type}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#687971]">{report.ai_summary}</p>
                <p className="mt-2 text-[11px] text-[#87958e]">{formatDate(report.report_date ?? report.uploaded_at)}</p>
              </div>
              {expanded === report.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            {expanded === report.id && <p className="mt-4 whitespace-pre-wrap border-t border-[#e5ece8] pt-4 text-sm leading-6">{report.ai_summary}</p>}
          </article>
        ))}
        {initialLoading && <LoadingState text="Loading reports..." />}
        {!initialLoading && !reports.length && !error && <EmptyState text="No reports uploaded yet." />}
      </div>
    </ScreenShell>
  );
}

function MedicationsScreen({ familyMemberId }: { familyMemberId?: string }) {
  const OWNER_ID = useOwnerId();
  const [medications, setMedications] = useState<Medication[]>([]);
  const [form, setForm] = useState({ drug_name: "", dose: "", frequency: "", timing: "", with_food: false });
  const [interaction, setInteraction] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [remindersEnabled, setRemindersEnabled] = useState(() =>
    typeof window !== "undefined"
    && window.localStorage.getItem("careos-medication-reminders") === "true"
    && "Notification" in window
    && Notification.permission === "granted",
  );

  useEffect(() => {
    if (!remindersEnabled || !("Notification" in window)) return;
    const timers = medications.flatMap((medication) =>
      (medication.timing ?? []).map((timing) => {
        const doseTime = nextDoseTime(timing);
        if (!doseTime) return undefined;
        return window.setTimeout(() => {
          new Notification(`Time for ${medication.drug_name}`, {
            body: `${medication.dose} | ${timing}${medication.with_food ? " | Take with food" : ""}`,
          });
        }, doseTime.getTime() - Date.now());
      }).filter((timer): timer is number => timer !== undefined),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [medications, remindersEnabled]);

  useEffect(() => {
    const controller = new AbortController();
    axios
      .get<Medication[]>(`${API_URL}/medications/${OWNER_ID}`, {
        params: { family_member_id: familyMemberId },
        signal: controller.signal,
      })
      .then(({ data }) => setMedications(data))
      .catch((error) => {
        if (!axios.isCancel(error)) setError("Could not load medications.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setInitialLoading(false);
      });
    return () => controller.abort();
  }, [OWNER_ID, familyMemberId]);

  async function loadMedications() {
    try {
      const { data } = await axios.get<Medication[]>(`${API_URL}/medications/${OWNER_ID}`, {
        params: { family_member_id: familyMemberId },
      });
      setMedications(data);
    } catch {
      setError("Could not load medications.");
    }
  }

  async function checkInteractions() {
    if (!form.drug_name.trim()) return;
    setBusy(true);
    try {
      const { data } = await axios.post<{ message: string }>(`${API_URL}/medications/check-interactions`, {
        user_id: OWNER_ID,
        family_member_id: familyMemberId,
        new_drug: form.drug_name,
      });
      setInteraction(data.message);
    } catch {
      setError("Interaction check failed.");
    } finally {
      setBusy(false);
    }
  }

  async function addMedication(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await axios.post(`${API_URL}/medications/add`, {
        user_id: OWNER_ID,
        family_member_id: familyMemberId,
        drug_name: form.drug_name,
        dose: form.dose,
        frequency: form.frequency,
        timing: form.timing.split(",").map((item) => item.trim()).filter(Boolean),
        with_food: form.with_food,
      });
      setForm({ drug_name: "", dose: "", frequency: "", timing: "", with_food: false });
      setInteraction("");
      await loadMedications();
    } catch {
      setError("Could not add medication.");
    } finally {
      setBusy(false);
    }
  }

  async function enableReminders() {
    if (!("Notification" in window)) {
      setError("Browser notifications are not supported here.");
      return;
    }
    const permission = await Notification.requestPermission();
    const enabled = permission === "granted";
    setRemindersEnabled(enabled);
    window.localStorage.setItem("careos-medication-reminders", String(enabled));
    if (enabled) {
      setError("");
      new Notification("CareOS medication reminders enabled", {
        body: "You will receive alerts for upcoming active-medication doses while CareOS is open.",
      });
    } else {
      setError("Notification permission was not granted.");
    }
  }

  return (
    <ScreenShell title="Active medications" description="Track doses, timing, and possible interactions.">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#dfe8e4] bg-[#f4f8f6] p-4">
        <div>
          <p className="text-sm font-semibold">Medication reminders</p>
          <p className="mt-1 text-xs text-[#687971]">{remindersEnabled ? "Browser reminders are active while CareOS is open." : "Enable alerts for upcoming active-medication doses."}</p>
        </div>
        <button type="button" onClick={enableReminders} className="flex h-10 items-center gap-2 rounded-md border border-[#12664f] px-4 text-sm font-semibold text-[#12664f]">
          {remindersEnabled ? <BellRing size={17} /> : <Bell size={17} />}
          {remindersEnabled ? "Reminders active" : "Enable reminders"}
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {medications.map((medication) => (
          <article key={medication.id} className="rounded-md border border-[#dfe8e4] p-4">
            <Pill size={18} className="text-[#12664f]" />
            <p className="mt-3 text-sm font-semibold">{medication.drug_name}</p>
            <p className="mt-1 text-xs text-[#687971]">{medication.dose} | {medication.frequency}</p>
            <p className="mt-2 text-xs text-[#687971]">{medication.timing?.join(", ") || "Timing not set"}{medication.with_food ? " | with food" : ""}</p>
            <p className="mt-3 border-t border-[#e5ece8] pt-3 text-xs font-medium text-[#12664f]">{nextDoseLabel(medication.timing)}</p>
          </article>
        ))}
      </div>
      {initialLoading && <LoadingState text="Loading medications..." />}
      {!initialLoading && !medications.length && !error && <EmptyState text="No active medications." />}
      <form onSubmit={addMedication} className="space-y-3 border-t border-[#dfe8e4] pt-5">
        <h2 className="text-sm font-semibold">Add medication</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <TextInput label="Drug name" value={form.drug_name} onChange={(value) => setForm({ ...form, drug_name: value })} required />
          <TextInput label="Dose" value={form.dose} onChange={(value) => setForm({ ...form, dose: value })} required />
          <TextInput label="Frequency" value={form.frequency} onChange={(value) => setForm({ ...form, frequency: value })} required />
          <TextInput label="Timing, comma separated" value={form.timing} onChange={(value) => setForm({ ...form, timing: value })} />
        </div>
        <label className="flex items-center gap-2 text-xs text-[#596b62]">
          <input type="checkbox" checked={form.with_food} onChange={(event) => setForm({ ...form, with_food: event.target.checked })} />
          Take with food
        </label>
        {interaction && <p className="rounded-md border border-[#e0b562] bg-[#fff8e8] p-3 text-xs leading-5 text-[#6f5015]">{interaction}</p>}
        <ErrorText text={error} />
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={checkInteractions} disabled={busy || !form.drug_name} className="h-10 rounded-md border border-[#12664f] px-4 text-sm font-semibold text-[#12664f] disabled:opacity-40">{busy ? "Checking..." : "Check interactions"}</button>
          <button disabled={busy} className="h-10 rounded-md bg-[#12664f] px-4 text-sm font-semibold text-white disabled:opacity-40">{busy ? "Working..." : "Add medication"}</button>
        </div>
      </form>
    </ScreenShell>
  );
}

function FamilyScreen({ activeProfile, family, owner, onFamilyChange, onSelect }: { activeProfile: Profile; family: Profile[]; owner: Profile; onFamilyChange: (profiles: Profile[]) => void; onSelect: (profile: Profile) => void }) {
  const OWNER_ID = useOwnerId();
  const [form, setForm] = useState({ name: "", relation: "", age: "", blood_group: "", known_conditions: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function addMember(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await axios.post<Profile>(`${API_URL}/family/add`, {
        owner_id: OWNER_ID,
        name: form.name,
        relation: form.relation,
        age: Number(form.age),
        blood_group: form.blood_group,
        known_conditions: form.known_conditions.split(",").map((item) => item.trim()).filter(Boolean),
      });
      onFamilyChange([...family, data]);
      setForm({ name: "", relation: "", age: "", blood_group: "", known_conditions: "" });
    } catch {
      setError("Could not add family member.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell title="Family profiles" description="Switch profiles to manage care for dependents.">
      <div className="rounded-md border border-[#b8d8ca] bg-[#f1f8f5] p-4">
        <p className="text-xs font-semibold uppercase text-[#527166]">Currently viewing</p>
        <p className="mt-1 text-base font-semibold text-[#12664f]">{activeProfile.name}</p>
        <p className="mt-1 text-xs leading-5 text-[#60736a]">
          Chat, reports, medications, profile details, insights, and CareOS memory now use this person&apos;s health context.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {[owner, ...family].map((profile) => (
          <button key={profile.id} onClick={() => onSelect(profile)} className={`rounded-md border p-4 text-left ${String(activeProfile.id) === String(profile.id) ? "border-[#12664f] bg-[#f1f8f5]" : "border-[#dfe8e4]"}`}>
            <UserRound size={19} className="text-[#12664f]" />
            <p className="mt-3 text-sm font-semibold">{profile.name}</p>
            <p className="mt-1 text-xs text-[#687971]">{String(profile.id) === OWNER_ID ? "Owner" : profile.relation} | {profile.age ?? "Age not set"}</p>
            <p className="mt-2 text-xs text-[#687971]">{profile.known_conditions?.join(", ") || "No known conditions"}</p>
          </button>
        ))}
      </div>
      <form onSubmit={addMember} className="space-y-3 border-t border-[#dfe8e4] pt-5">
        <h2 className="text-sm font-semibold">Add family member</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <TextInput label="Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
          <TextInput label="Relation" value={form.relation} onChange={(value) => setForm({ ...form, relation: value })} required />
          <TextInput label="Age" value={form.age} onChange={(value) => setForm({ ...form, age: value })} required />
          <TextInput label="Blood group" value={form.blood_group} onChange={(value) => setForm({ ...form, blood_group: value })} required />
        </div>
        <TextInput label="Known conditions, comma separated" value={form.known_conditions} onChange={(value) => setForm({ ...form, known_conditions: value })} />
        <ErrorText text={error} />
        <button disabled={busy} className="flex h-10 items-center gap-2 rounded-md bg-[#12664f] px-4 text-sm font-semibold text-white disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={17} /> : <Plus size={17} />} {busy ? "Adding..." : "Add family member"}</button>
      </form>
    </ScreenShell>
  );
}

function ProfileScreen({ profile, familyMemberId }: { profile: Profile; familyMemberId?: string }) {
  const OWNER_ID = useOwnerId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const historyScope = familyMemberId ?? OWNER_ID;
  const [historyState, setHistoryState] = useState({ scope: "", text: "" });
  const historyLoading = historyState.scope !== historyScope;

  useEffect(() => {
    const controller = new AbortController();
    axios.get<{ history: string }>(`${API_URL}/history/${OWNER_ID}`, {
      params: { family_member_id: familyMemberId },
      signal: controller.signal,
    })
      .then(({ data }) => setHistoryState({ scope: historyScope, text: data.history }))
      .catch((error) => {
        if (!axios.isCancel(error)) {
          setHistoryState({ scope: historyScope, text: "Health timeline could not be loaded." });
        }
      });
    return () => controller.abort();
  }, [OWNER_ID, familyMemberId, historyScope]);

  async function downloadBrief() {
    setBusy(true);
    setError("");
    try {
      const { data } = await axios.get(`${API_URL}/api/care-brief/${OWNER_ID}/pdf`, {
        params: { family_member_id: familyMemberId },
        responseType: "blob",
      });
      const url = URL.createObjectURL(data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `careos-${profile.name.replaceAll(" ", "-").toLowerCase()}-brief.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not generate doctor brief.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell title={profile.name} description="Health profile and visit preparation.">
      <div className="grid gap-3 sm:grid-cols-2">
        <ProfileField label="Age" value={profile.age} />
        <ProfileField label="Gender" value={profile.gender} />
        <ProfileField label="Blood group" value={profile.blood_group} />
        <ProfileField label="Emergency contact" value={profile.emergency_contact ?? formatList(profile.emergency_contacts)} />
      </div>
      <ProfileField label="Known conditions" value={profile.known_conditions?.join(", ")} />
      <ProfileField label="Allergies" value={profile.allergies?.join(", ")} />
      <section className="rounded-md border border-[#dfe8e4] p-4">
        <p className="text-xs font-semibold uppercase text-[#71827a]">Health timeline</p>
        {historyLoading
          ? <p className="mt-3 text-sm text-[#687971]">Loading health details...</p>
          : <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#35463e]">{historyState.text}</p>}
      </section>
      <ErrorText text={error} />
      <button onClick={downloadBrief} disabled={busy} className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-[#12664f] text-sm font-semibold text-white disabled:opacity-50 sm:w-auto sm:px-5">
        {busy ? <LoaderCircle className="animate-spin" size={18} /> : <Download size={18} />}
        Generate doctor brief
      </button>
    </ScreenShell>
  );
}

function ScreenShell({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <div className="flex-1 overflow-y-auto px-4 py-5 pb-24 sm:px-8 md:pb-8"><div className="mx-auto max-w-3xl space-y-5"><div><h1 className="text-xl font-semibold">{title}</h1><p className="mt-1 text-sm text-[#687971]">{description}</p></div>{children}</div></div>;
}

function TextInput({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return <label className="block text-xs font-medium text-[#596b62]">{label}<input required={required} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-[#cfdad5] px-3 text-sm outline-none focus:border-[#12664f]" /></label>;
}

function ProfileField({ label, value }: { label: string; value: unknown }) {
  return <div className="rounded-md border border-[#dfe8e4] p-4"><p className="text-xs font-medium text-[#71827a]">{label}</p><p className="mt-2 text-sm">{String(value || "Not provided")}</p></div>;
}

function EmptyState({ text }: { text: string }) {
  return <p className="rounded-md border border-dashed border-[#cfdad5] px-4 py-8 text-center text-sm text-[#71827a]">{text}</p>;
}

function LoadingState({ text }: { text: string }) {
  return <p className="flex items-center justify-center gap-2 rounded-md border border-[#dfe8e4] px-4 py-8 text-sm text-[#71827a]"><LoaderCircle className="animate-spin" size={17} />{text}</p>;
}

function ErrorText({ text }: { text: string }) {
  return text ? <p className="rounded-md border border-[#efb2a8] bg-[#fff2ef] p-3 text-xs text-[#982d1d]">{text}</p> : null;
}

function ServiceNotice({ loading, error }: { loading: boolean; error: string }) {
  return <div className={`mx-4 mt-3 rounded-md border px-3 py-2 text-xs sm:mx-6 ${error ? "border-[#efb2a8] bg-[#fff2ef] text-[#982d1d]" : "border-[#b8d8ca] bg-[#f1f8f5] text-[#43675a]"}`}>{loading ? "Loading CareOS demo profile..." : error}</div>;
}

function formatDate(value?: string) {
  return value ? new Date(value).toLocaleDateString() : "Date unavailable";
}

function formatList(value?: string | string[]) {
  return Array.isArray(value) ? value.join(", ") : value;
}

function nextDoseTime(timing: string) {
  const match = timing.match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/i);
  if (!match) return null;
  let hour = Number(match[1]);
  const minute = Number(match[2] ?? 0);
  const period = match[3]?.toLowerCase();
  if (period === "pm" && hour < 12) hour += 12;
  if (period === "am" && hour === 12) hour = 0;
  const next = new Date();
  next.setHours(hour, minute, 0, 0);
  const weekdays = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  const requestedDay = weekdays.findIndex((day) => timing.toLowerCase().includes(day));
  if (requestedDay >= 0) {
    let daysAhead = (requestedDay - next.getDay() + 7) % 7;
    if (daysAhead === 0 && next.getTime() <= Date.now()) daysAhead = 7;
    next.setDate(next.getDate() + daysAhead);
  } else if (next.getTime() <= Date.now()) {
    next.setDate(next.getDate() + 1);
  }
  return next;
}

function nextDoseLabel(timings?: string[]) {
  const next = (timings ?? [])
    .map((timing) => ({ timing, date: nextDoseTime(timing) }))
    .filter((item): item is { timing: string; date: Date } => Boolean(item.date))
    .sort((a, b) => a.date.getTime() - b.date.getTime())[0];
  return next
    ? `Next dose: ${next.date.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}`
    : "Add a clock time to enable dose reminders.";
}

function DesktopNavigation({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return (
    <aside className="hidden h-full w-64 shrink-0 overflow-y-auto border-r border-[#f1f5f3] bg-white p-6 md:block">
      <div className="mb-8 flex items-center gap-2 px-2 font-bold text-[#12664f]">
        <HeartPulse size={22} />
        <span className="text-lg">CareOS</span>
      </div>
      <nav className="space-y-1.5">
        {navigation.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={`flex h-11 w-full items-center gap-3 rounded-xl px-4 text-sm font-medium transition-all ${
              active === id ? "bg-[#f1f8f5] text-[#12664f]" : "text-[#596b62] hover:bg-gray-50"
            }`}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function MobileNavigation({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-20 grid h-20 grid-cols-5 border-t border-[#dfe8e4] bg-white px-1 pb-[env(safe-area-inset-bottom)] md:hidden">
      {navigation.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`flex min-w-0 flex-col items-center justify-center gap-1 text-[10px] font-medium ${
            active === id ? "text-[#12664f]" : "text-[#71827a]"
          }`}
        >
          <Icon size={19} strokeWidth={active === id ? 2.5 : 2} />
          <span className="max-w-full truncate">{label}</span>
        </button>
      ))}
    </nav>
  );
}
