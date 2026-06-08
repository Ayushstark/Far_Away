"use client";

import axios from "axios";
import {
  Activity,
  AlertTriangle,
  ArrowUp,
  FileText,
  HeartPulse,
  Paperclip,
  Pill,
  Stethoscope,
  Users,
} from "lucide-react";
import { FormEvent, useState } from "react";

const agents = [
  { name: "Symptom analyst", detail: "Clarifies symptoms", icon: Activity },
  { name: "Report reader", detail: "Explains labs and PDFs", icon: FileText },
  { name: "Medication manager", detail: "Tracks doses and alerts", icon: Pill },
  { name: "Care coordinator", detail: "Prepares doctor briefs", icon: Stethoscope },
  { name: "Emergency detector", detail: "Watches for red flags", icon: AlertTriangle },
];

type Reply = {
  message: string;
  agents_used: string[];
  emergency: boolean;
  disclaimer: string;
};

export default function Home() {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState<Reply | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    setLoading(true);
    try {
      const { data } = await axios.post<Reply>(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/chat`,
        { message, profile_id: "demo-user" },
      );
      setReply(data);
    } catch {
      setReply({
        message: "The API is offline. Start FastAPI on port 8000 and try again.",
        agents_used: [],
        emergency: false,
        disclaimer: "JARVIS provides general health information only.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f7f6] text-[#17211d]">
      <header className="border-b border-[#dce4e0] bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-md bg-[#12664f] text-white">
              <HeartPulse size={20} />
            </span>
            <div>
              <p className="font-semibold">JARVIS Health</p>
              <p className="text-xs text-[#66746e]">Care coordination workspace</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-[#51625a]">
            <span className="size-2 rounded-full bg-[#22a06b]" />
            Five agents ready
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-6 lg:grid-cols-[260px_1fr_280px]">
        <aside className="space-y-5">
          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase text-[#78867f]">Specialists</h2>
            <div className="space-y-1">
              {agents.map(({ name, detail, icon: Icon }) => (
                <div key={name} className="flex items-center gap-3 rounded-md px-2 py-2.5 hover:bg-white">
                  <Icon size={18} className="text-[#12664f]" />
                  <div>
                    <p className="text-sm font-medium">{name}</p>
                    <p className="text-xs text-[#78867f]">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
          <div className="border-t border-[#dce4e0] pt-4">
            <div className="flex items-center gap-3 px-2 py-2">
              <Users size={18} className="text-[#9a6612]" />
              <div>
                <p className="text-sm font-medium">Family dashboard</p>
                <p className="text-xs text-[#78867f]">Profiles and shared alerts</p>
              </div>
            </div>
          </div>
        </aside>

        <section className="flex min-h-[calc(100vh-7rem)] flex-col border-x border-[#dce4e0] bg-white">
          <div className="border-b border-[#e5ebe8] px-6 py-5">
            <h1 className="text-xl font-semibold">How can I help today?</h1>
            <p className="mt-1 text-sm text-[#66746e]">
              Your orchestrator will bring in the right specialists.
            </p>
          </div>
          <div className="flex flex-1 flex-col justify-end gap-5 p-6">
            {reply ? (
              <div className={`max-w-2xl border-l-4 p-4 ${reply.emergency ? "border-[#c4432b] bg-[#fff4f1]" : "border-[#12664f] bg-[#f1f8f5]"}`}>
                <p className="whitespace-pre-wrap text-sm leading-6">{reply.message}</p>
                {!!reply.agents_used.length && (
                  <p className="mt-3 text-xs text-[#66746e]">
                    Routed to: {reply.agents_used.map((item) => item.replaceAll("_", " ")).join(", ")}
                  </p>
                )}
              </div>
            ) : (
              <div className="mx-auto max-w-md text-center text-[#66746e]">
                <HeartPulse className="mx-auto mb-4 text-[#12664f]" size={32} />
                <p className="text-sm leading-6">
                  Describe symptoms, ask about a medication, or prepare for a doctor visit.
                </p>
              </div>
            )}
            <form onSubmit={submit} className="border border-[#cfdad5] bg-white p-3 shadow-sm focus-within:border-[#12664f]">
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Tell JARVIS what is happening..."
                className="min-h-20 w-full resize-none border-0 bg-transparent text-sm outline-none placeholder:text-[#8a9891]"
              />
              <div className="flex items-center justify-between border-t border-[#e5ebe8] pt-3">
                <button type="button" title="Attach medical report" className="grid size-9 place-items-center rounded-md text-[#66746e] hover:bg-[#f1f5f3]">
                  <Paperclip size={18} />
                </button>
                <button disabled={loading} title="Send message" className="grid size-9 place-items-center rounded-md bg-[#12664f] text-white disabled:opacity-50">
                  <ArrowUp size={18} />
                </button>
              </div>
            </form>
            <p className="text-center text-xs text-[#84928b]">
              General health information only. For emergencies, call local emergency services.
            </p>
          </div>
        </section>

        <aside>
          <h2 className="mb-3 text-xs font-semibold uppercase text-[#78867f]">Health memory</h2>
          <div className="space-y-4 border-t border-[#dce4e0] pt-4">
            <div>
              <p className="text-sm font-medium">Current profile</p>
              <p className="text-sm text-[#66746e]">Demo patient</p>
            </div>
            <div>
              <p className="text-sm font-medium">Memory status</p>
              <p className="text-sm text-[#66746e]">ChromaDB ready</p>
            </div>
            <div className="border-l-2 border-[#d3982c] pl-3">
              <p className="text-sm font-medium">Proactive nudges</p>
              <p className="mt-1 text-xs leading-5 text-[#66746e]">
                Medication reminders and trend alerts will appear here.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}
