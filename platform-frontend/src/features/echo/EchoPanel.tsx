"use client"

import { Mic } from "lucide-react"
import useVoice from "@/hooks/useVoice"

export default function EchoPanel() {

    const { state, transcript, turns, start, isStreaming } = useVoice()

    const statusText = () => {
        if (state === "idle") return "Waiting for wake word..."
        if (state === "listening") return "Listening..."
        if (state === "dictating") return "Dictating — say \"stop dictation\" to finish."
        return "Idle"
    }

    return (
        <div className="flex flex-col h-full bg-background border-r border-border/50 text-foreground overflow-hidden w-80 shrink-0 p-6">

            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <h2 className="text-xl font-semibold">Echo</h2>
                    {/* SSE connection indicator */}
                    <span
                        title={isStreaming ? "Event stream connected" : "Event stream disconnected"}
                        className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}
                    />
                </div>

                <button
                    onClick={start}
                    className="p-3 rounded-full bg-indigo-600 hover:bg-indigo-500 transition"
                >
                    <Mic size={20} />
                </button>
            </div>

            {/* Status */}
            <div className="mb-4 text-sm text-zinc-400">
                {statusText()}
            </div>

            {/* Transcript Box */}
            <div className="flex-1 bg-zinc-800 rounded-lg p-4 overflow-auto">
                {state === "dictating" ? (
                    <p className="text-indigo-300 italic">
                        {transcript || "Dictation active — speak freely..."}
                    </p>
                ) : transcript ? (
                    <p className="text-zinc-200">{transcript}</p>
                ) : (
                    <p className="text-zinc-500">
                        No turns yet. Say "Hey Arcturus" to start.
                    </p>
                )}
            </div>

            {/* Footer */}
            <div className="mt-4 text-xs text-zinc-500">
                Turns: {turns}
            </div>

        </div>
    )
}