"use client";

import axios from "axios";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  HeartPulse,
  LoaderCircle,
  MessageCircle,
  Mic,
  MicOff,
  Plus,
  Phone,
  Pill,
  Send,
  UploadCloud,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { DragEvent, FormEvent, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const OWNER_ID = "demo-user";

type Tab = "chat" | "reports" | "medications" | "family" | "profile";
type Speaker = "user" | "assistant" | "system";

type EmergencyDetails = {
  suspected: string;
  immediate_steps: string[];
  call_number: string;
};

type ChatReply = {
  message: string;
  agents_used: string[];
  emergency: boolean;
  emergency_details: EmergencyDetails | null;
};

type ChatMessage = {
  id: string;
  speaker: Speaker;
  text: string;
  agents?: string[];
};

type Profile = {
  id: string;
  name: string;
  age?: number;
  gender?: string;
  blood_group?: string;
  known_conditions?: string[];
  allergies?: string[];
  emergency_contact?: string;
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
  onerror: (() => void) | null;
};

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
  const [tab, setTab] = useState<Tab>("chat");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [emergency, setEmergency] = useState<EmergencyDetails | null>(null);
  const [activeProfile, setActiveProfile] = useState<Profile>({ id: OWNER_ID, name: "My profile" });
  const [ownerProfile, setOwnerProfile] = useState<Profile>({ id: OWNER_ID, name: "My profile" });
  const [family, setFamily] = useState<Profile[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      speaker: "assistant",
      text: "Hi, I am CareOS. Tell me what is happening, and I will bring in the right care agent.",
      agents: ["emergency_detector"],
    },
  ]);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const conversationEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    conversationEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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
      .catch(() => undefined);
  }, []);

  const familyMemberId = activeProfile.id === OWNER_ID ? undefined : activeProfile.id;

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

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
      });
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          speaker: "assistant",
          text: data.message,
          agents: data.agents_used,
        },
      ]);
      if (data.emergency) {
        setEmergency(
          data.emergency_details ?? {
            suspected: "Urgent medical concern",
            immediate_steps: ["Call emergency services now."],
            call_number: "112",
          },
        );
      }
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          speaker: "system",
          text: "CareOS could not reach the health service. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function toggleVoiceInput() {
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
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          speaker: "system",
          text: "Voice input is not supported in this browser.",
        },
      ]);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-IN";
    recognition.onresult = (event) => setInput(event.results[0][0].transcript);
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }

  return (
    <main className="min-h-dvh bg-[#edf3f0] text-[#17211d]">
      <div className="mx-auto flex min-h-dvh max-w-6xl bg-white shadow-sm">
        <DesktopNavigation active={tab} onChange={setTab} />

        <section className="relative flex min-h-dvh min-w-0 flex-1 flex-col pb-20 md:pb-0">
          <Header tab={tab} activeProfile={activeProfile} />
          {tab === "chat" ? (
            <ChatScreen
              input={input}
              loading={loading}
              listening={listening}
              messages={messages}
              conversationEnd={conversationEnd}
              onInput={setInput}
              onSend={sendMessage}
              onVoice={toggleVoiceInput}
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
              onSelect={setActiveProfile}
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

function Header({ tab, activeProfile }: { tab: Tab; activeProfile: Profile }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-[#dfe8e4] px-4 sm:px-6">
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
      <span className="max-w-[42%] truncate text-xs font-medium text-[#53665d]">
        {activeProfile.name}
      </span>
    </header>
  );
}

function ChatScreen({
  input,
  loading,
  listening,
  messages,
  conversationEnd,
  onInput,
  onSend,
  onVoice,
}: {
  input: string;
  loading: boolean;
  listening: boolean;
  messages: ChatMessage[];
  conversationEnd: React.RefObject<HTMLDivElement | null>;
  onInput: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onVoice: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          <div className="mb-2">
            <h1 className="text-xl font-semibold">How are you feeling today?</h1>
            <p className="mt-1 text-sm text-[#687971]">
              CareOS checks every message for urgent warning signs first.
            </p>
          </div>
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {loading && <TypingIndicator />}
          <div ref={conversationEnd} />
        </div>
      </div>

      <div className="shrink-0 border-t border-[#dfe8e4] bg-white px-3 py-3 sm:px-8">
        <form onSubmit={onSend} className="mx-auto flex max-w-3xl items-end gap-2">
          <button
            type="button"
            onClick={onVoice}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            title={listening ? "Stop voice input" : "Start voice input"}
            className={`grid size-11 shrink-0 place-items-center rounded-md border transition ${
              listening
                ? "border-[#c4432b] bg-[#fff0ec] text-[#b53521]"
                : "border-[#cfdad5] text-[#566a60] hover:bg-[#f1f6f3]"
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
            placeholder={listening ? "Listening..." : "Describe symptoms or ask a health question"}
            className="max-h-32 min-h-11 flex-1 resize-none rounded-md border border-[#cfdad5] px-3 py-2.5 text-sm outline-none transition focus:border-[#12664f]"
          />
          <button
            disabled={!input.trim() || loading}
            aria-label="Send message"
            title="Send message"
            className="grid size-11 shrink-0 place-items-center rounded-md bg-[#12664f] text-white transition hover:bg-[#0e5743] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send size={18} />
          </button>
        </form>
        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-[#809087]">
          CareOS provides general health information, not a diagnosis.
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.speaker === "user";
  const isSystem = message.speaker === "system";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-md px-4 py-3 text-sm leading-6 sm:max-w-[75%] ${
          isUser
            ? "bg-[#12664f] text-white"
            : isSystem
              ? "border border-[#e0b562] bg-[#fff8e8] text-[#6f5015]"
              : "border border-[#dfe8e4] bg-[#f4f8f6] text-[#24322c]"
        }`}
      >
        {!isUser && !isSystem && (
          <p className="mb-1 text-xs font-semibold text-[#12664f]">CareOS</p>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
        {!!message.agents?.length && (
          <p className={`mt-2 text-[11px] ${isUser ? "text-white/70" : "text-[#71827a]"}`}>
            {message.agents.map((agent) => agent.replaceAll("_", " ")).join(" + ")}
          </p>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start" aria-label="CareOS is typing">
      <div className="flex h-10 items-center gap-1 rounded-md border border-[#dfe8e4] bg-[#f4f8f6] px-4">
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
  const [reports, setReports] = useState<Report[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    axios
      .get<Report[]>(`${API_URL}/reports/${OWNER_ID}`, {
        params: { family_member_id: familyMemberId },
      })
      .then(({ data }) => setReports(data))
      .catch(() => setError("Could not load reports."));
  }, [familyMemberId]);

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
    } catch {
      setError("CareOS could not upload or analyze this report.");
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
        {!reports.length && !error && <EmptyState text="No reports uploaded yet." />}
      </div>
    </ScreenShell>
  );
}

function MedicationsScreen({ familyMemberId }: { familyMemberId?: string }) {
  const [medications, setMedications] = useState<Medication[]>([]);
  const [form, setForm] = useState({ drug_name: "", dose: "", frequency: "", timing: "", with_food: false });
  const [interaction, setInteraction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    axios
      .get<Medication[]>(`${API_URL}/medications/${OWNER_ID}`, {
        params: { family_member_id: familyMemberId },
      })
      .then(({ data }) => setMedications(data))
      .catch(() => setError("Could not load medications."));
  }, [familyMemberId]);

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

  return (
    <ScreenShell title="Active medications" description="Track doses, timing, and possible interactions.">
      <div className="grid gap-3 sm:grid-cols-2">
        {medications.map((medication) => (
          <article key={medication.id} className="rounded-md border border-[#dfe8e4] p-4">
            <Pill size={18} className="text-[#12664f]" />
            <p className="mt-3 text-sm font-semibold">{medication.drug_name}</p>
            <p className="mt-1 text-xs text-[#687971]">{medication.dose} · {medication.frequency}</p>
            <p className="mt-2 text-xs text-[#687971]">{medication.timing?.join(", ") || "Timing not set"}{medication.with_food ? " · with food" : ""}</p>
          </article>
        ))}
      </div>
      {!medications.length && <EmptyState text="No active medications." />}
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
          <button type="button" onClick={checkInteractions} disabled={busy || !form.drug_name} className="h-10 rounded-md border border-[#12664f] px-4 text-sm font-semibold text-[#12664f] disabled:opacity-40">Check interactions</button>
          <button disabled={busy} className="h-10 rounded-md bg-[#12664f] px-4 text-sm font-semibold text-white disabled:opacity-40">Add medication</button>
        </div>
      </form>
    </ScreenShell>
  );
}

function FamilyScreen({ activeProfile, family, owner, onFamilyChange, onSelect }: { activeProfile: Profile; family: Profile[]; owner: Profile; onFamilyChange: (profiles: Profile[]) => void; onSelect: (profile: Profile) => void }) {
  const [form, setForm] = useState({ name: "", relation: "", age: "", blood_group: "", known_conditions: "" });
  const [error, setError] = useState("");

  async function addMember(event: FormEvent) {
    event.preventDefault();
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
    }
  }

  return (
    <ScreenShell title="Family profiles" description="Switch profiles to manage care for dependents.">
      <div className="grid gap-3 sm:grid-cols-2">
        {[owner, ...family].map((profile) => (
          <button key={profile.id} onClick={() => onSelect(profile)} className={`rounded-md border p-4 text-left ${activeProfile.id === profile.id ? "border-[#12664f] bg-[#f1f8f5]" : "border-[#dfe8e4]"}`}>
            <UserRound size={19} className="text-[#12664f]" />
            <p className="mt-3 text-sm font-semibold">{profile.name}</p>
            <p className="mt-1 text-xs text-[#687971]">{profile.id === OWNER_ID ? "Owner" : profile.relation} · {profile.age ?? "Age not set"}</p>
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
        <button className="flex h-10 items-center gap-2 rounded-md bg-[#12664f] px-4 text-sm font-semibold text-white"><Plus size={17} /> Add family member</button>
      </form>
    </ScreenShell>
  );
}

function ProfileScreen({ profile, familyMemberId }: { profile: Profile; familyMemberId?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
        <ProfileField label="Emergency contact" value={profile.emergency_contact} />
      </div>
      <ProfileField label="Known conditions" value={profile.known_conditions?.join(", ")} />
      <ProfileField label="Allergies" value={profile.allergies?.join(", ")} />
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

function ErrorText({ text }: { text: string }) {
  return text ? <p className="rounded-md border border-[#efb2a8] bg-[#fff2ef] p-3 text-xs text-[#982d1d]">{text}</p> : null;
}

function formatDate(value?: string) {
  return value ? new Date(value).toLocaleDateString() : "Date unavailable";
}

function DesktopNavigation({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return (
    <aside className="hidden w-56 shrink-0 border-r border-[#dfe8e4] bg-[#f6f9f7] p-4 md:block">
      <p className="px-2 py-3 text-xs font-semibold uppercase text-[#71827a]">Workspace</p>
      <nav className="mt-2 space-y-1">
        {navigation.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={`flex h-11 w-full items-center gap-3 rounded-md px-3 text-sm font-medium ${
              active === id
                ? "bg-white text-[#12664f] shadow-sm"
                : "text-[#596b62] hover:bg-white"
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
