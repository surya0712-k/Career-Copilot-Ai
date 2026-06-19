"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Room, RoomEvent, Track } from "livekit-client";
import { api, Goal } from "@/lib/api";
import { ArrowLeft, Mic, MicOff, PhoneOff } from "lucide-react";

function VoiceInterviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("Connecting...");
  const [connected, setConnected] = useState(false);
  const [muted, setMuted] = useState(false);
  const [focusLabel, setFocusLabel] = useState<string | null>(null);
  const goalRef = useRef<Goal | null>(null);
  const roomRef = useRef<Room | null>(null);
  const audioContainerRef = useRef<HTMLDivElement>(null);
  const connectGenRef = useRef(0);

  const roadmapId = searchParams.get("roadmapId");
  const milestoneId = searchParams.get("milestoneId");
  const goalIdParam = searchParams.get("goalId");

  const detachAllAudio = useCallback(() => {
    audioContainerRef.current?.querySelectorAll("audio").forEach((el) => {
      el.pause();
      el.srcObject = null;
      el.remove();
    });
  }, []);

  const teardownRoom = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;
    detachAllAudio();
    if (room) {
      room.removeAllListeners();
      await room.disconnect();
    }
  }, [detachAllAudio]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    const generation = ++connectGenRef.current;
    let cancelled = false;

    async function connect() {
      await teardownRoom();
      if (cancelled || generation !== connectGenRef.current) return;

      try {
        const activeGoal = await api.getActiveGoal();
        if (cancelled || generation !== connectGenRef.current) return;
        goalRef.current = activeGoal;

        const creds = await api.getLiveKitToken({
          goalId: goalIdParam ?? activeGoal?.id,
          roadmapId: roadmapId ?? undefined,
          milestoneId: milestoneId ?? undefined,
        });
        if (cancelled || generation !== connectGenRef.current) return;

        if (creds.focus_label) {
          setFocusLabel(creds.focus_label);
        }

        const room = new Room();
        roomRef.current = room;

        room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
          if (track.kind !== Track.Kind.Audio || !audioContainerRef.current) return;
          // Only play the agent — ignore duplicate or stale agent tracks
          if (participant.isLocal) return;
          detachAllAudio();
          const el = track.attach();
          el.style.display = "none";
          audioContainerRef.current.appendChild(el);
        });

        room.on(RoomEvent.TrackUnsubscribed, (track) => {
          track.detach().forEach((el) => el.remove());
        });

        room.on(RoomEvent.Disconnected, () => {
          setConnected(false);
          setStatus("Interview ended");
          detachAllAudio();
        });

        await room.connect(creds.url, creds.token);
        if (cancelled || generation !== connectGenRef.current) {
          room.removeAllListeners();
          await room.disconnect();
          return;
        }

        await room.localParticipant.setMicrophoneEnabled(true);
        setConnected(true);
        setStatus("Live — speak with your AI interviewer");
      } catch (e) {
        if (!cancelled && generation === connectGenRef.current) {
          setStatus(e instanceof Error ? e.message : "Failed to connect");
        }
      }
    }

    connect();

    return () => {
      cancelled = true;
      void teardownRoom();
    };
  }, [router, roadmapId, milestoneId, goalIdParam, teardownRoom, detachAllAudio]);

  async function toggleMute() {
    if (!roomRef.current) return;
    const next = !muted;
    await roomRef.current.localParticipant.setMicrophoneEnabled(!next);
    setMuted(next);
  }

  async function endCall() {
    connectGenRef.current += 1;
    await teardownRoom();
    setConnected(false);
    setStatus("Interview ended");
    try {
      await api.saveVoiceSummary({
        goal_id: goalRef.current?.id,
        summary: focusLabel
          ? `Voice mock interview (${focusLabel}) completed via LiveKit.`
          : "Voice mock interview completed via LiveKit.",
        score: 7,
        improvements: [],
        strengths: [],
      });
    } catch {
      /* best-effort persist */
    }
    router.push("/dashboard");
  }

  return (
    <main className="flex min-h-screen min-h-[100dvh] flex-col items-center justify-center px-4 py-8 sm:px-6">
      <div className="card w-full max-w-md text-center">
        <Link
          href={roadmapId ? `/roadmap/${roadmapId}` : "/dashboard"}
          className="mb-6 inline-flex items-center gap-2 text-sm text-white/60 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> {roadmapId ? "Back to Roadmap" : "Dashboard"}
        </Link>

        {focusLabel && (
          <p className="mb-4 rounded-lg bg-brand-600/20 px-3 py-2 text-left text-sm leading-snug text-brand-300 sm:text-center">
            Focus: {focusLabel}
          </p>
        )}

        <div
          className={`mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full ${
            connected ? "bg-brand-600/30 animate-pulse" : "bg-white/10"
          }`}
        >
          <Mic className={`h-10 w-10 ${connected ? "text-brand-400" : "text-white/40"}`} />
        </div>

        <h1 className="mb-2 text-xl font-bold">Voice Mock Interview</h1>
        <p className="mb-8 text-sm text-white/60">{status}</p>

        <div ref={audioContainerRef} className="hidden" aria-hidden />

        {connected && (
          <div className="flex justify-center gap-6 sm:gap-4">
            <button
              onClick={toggleMute}
              className="flex h-16 w-16 items-center justify-center rounded-full border border-white/20 bg-white/5 hover:bg-white/10 active:scale-95 sm:h-14 sm:w-14"
              aria-label={muted ? "Unmute" : "Mute"}
            >
              {muted ? <MicOff className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
            </button>
            <button
              onClick={endCall}
              className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 hover:bg-red-700 active:scale-95 sm:h-14 sm:w-14"
              aria-label="End interview"
            >
              <PhoneOff className="h-6 w-6" />
            </button>
          </div>
        )}

        {!connected && status.includes("Failed") && (
          <Link href="/interview/new" className="btn-secondary mt-4 inline-block">
            Try text interview instead
          </Link>
        )}
      </div>
    </main>
  );
}

export default function VoiceInterviewPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </main>
      }
    >
      <VoiceInterviewContent />
    </Suspense>
  );
}
