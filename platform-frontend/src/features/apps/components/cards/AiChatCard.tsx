"use client";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  IconBolt,
  IconChevronDown,
  IconCircle,
  IconCircleDashed,
  IconCloud,
  IconCode,
  IconDeviceLaptop,
  IconHistory,
  IconLoader2,
  IconPaperclip,
  IconPlus,
  IconProgress,
  IconSend,
  IconUser,
  IconWand,
  IconWorld,
} from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";
const POLL_INTERVAL_MS = 1_000;
const POLL_TIMEOUT_MS = 120_000;

interface ChatMessage {
  role: "user" | "bot";
  content: string;
}

export default function Ai03() {
  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("Local");
  const [selectedAgent, setSelectedAgent] = useState("Agent");
  const [selectedPerformance, setSelectedPerformance] = useState("High");
  const [autoMode, setAutoMode] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const sessionId = sessionIdRef.current;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      // 1. POST to webchat inbound endpoint
      const postResp = await fetch(`${API_BASE}/api/nexus/webchat/inbound`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          sender_id: sessionId,
          sender_name: "WebChat User",
          text,
        }),
      });

      if (!postResp.ok) {
        throw new Error(`Inbound POST failed: ${postResp.status}`);
      }

      // 2. Poll for reply
      const deadline = Date.now() + POLL_TIMEOUT_MS;
      let reply: string | null = null;

      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

        const getResp = await fetch(
          `${API_BASE}/api/nexus/webchat/messages/${sessionId}`
        );
        if (!getResp.ok) continue;

        const data = await getResp.json();
        const msgs: { text: string }[] = data.messages ?? [];
        if (msgs.length > 0) {
          reply = msgs.map((m) => m.text).join("\n\n");
          break;
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: reply ?? "Agent did not respond in time. Please try again.",
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: `Error: ${String(err)}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <div className="w-xl flex flex-col gap-2">
      {/* Message history */}
      {(messages.length > 0 || loading) && (
        <div className="bg-background border border-border rounded-2xl p-3 flex flex-col gap-2 max-h-[50vh] overflow-y-auto">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn("flex", {
                "justify-end": msg.role === "user",
                "justify-start": msg.role === "bot",
              })}
            >
              <div
                className={cn(
                  "max-w-[80%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap",
                  {
                    "bg-primary text-primary-foreground": msg.role === "user",
                    "bg-muted text-foreground": msg.role === "bot",
                  }
                )}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-muted text-muted-foreground rounded-xl px-3 py-2 text-sm flex items-center gap-1.5">
                <IconLoader2 className="size-3.5 animate-spin" />
                Thinking…
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input area */}
      <div className="bg-background border border-border rounded-2xl overflow-hidden">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="sr-only"
          onChange={() => {}}
        />

        <div className="px-3 pt-3 pb-2 grow">
          <form onSubmit={handleSubmit}>
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything"
              className="w-full bg-transparent! p-0 border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 text-foreground placeholder-muted-foreground resize-none border-none outline-none text-sm min-h-10 max-h-[25vh]"
              rows={1}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = "auto";
                target.style.height = target.scrollHeight + "px";
              }}
            />
          </form>
        </div>

        <div className="mb-2 px-2 flex items-center justify-between">
          <div className="flex items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 rounded-full border border-border hover:bg-accent"
                >
                  <IconPlus className="size-3" />
                </Button>
              </DropdownMenuTrigger>

              <DropdownMenuContent
                align="start"
                className="max-w-xs rounded-2xl p-1.5"
              >
                <DropdownMenuGroup className="space-y-1">
                  <DropdownMenuItem
                    className="rounded-[calc(1rem-6px)] text-xs"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <IconPaperclip size={16} className="opacity-60" />
                    Attach Files
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="rounded-[calc(1rem-6px)] text-xs"
                    onClick={() => {}}
                  >
                    <IconCode size={16} className="opacity-60" />
                    Code Interpreter
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="rounded-[calc(1rem-6px)] text-xs"
                    onClick={() => {}}
                  >
                    <IconWorld size={16} className="opacity-60" />
                    Web Search
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="rounded-[calc(1rem-6px)] text-xs"
                    onClick={() => {}}
                  >
                    <IconHistory size={16} className="opacity-60" />
                    Chat History
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAutoMode(!autoMode)}
              className={cn(
                "h-7 px-2 rounded-full border border-border hover:bg-accent ",
                {
                  "bg-primary/10 text-primary border-primary/30": autoMode,
                  "text-muted-foreground": !autoMode,
                }
              )}
            >
              <IconWand className="size-3" />
              <span className="text-xs">Auto</span>
            </Button>
          </div>

          <div>
            <Button
              type="submit"
              disabled={!input.trim() || loading}
              className="size-7 p-0 rounded-full bg-primary disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleSubmit}
            >
              {loading ? (
                <IconLoader2 className="size-3 animate-spin" />
              ) : (
                <IconSend className="size-3 fill-primary" />
              )}
            </Button>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-0 pt-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 rounded-full border border-transparent hover:bg-accent text-muted-foreground text-xs"
            >
              <IconDeviceLaptop className="size-3" />
              <span>{selectedModel}</span>
              <IconChevronDown className="size-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="max-w-xs rounded-2xl p-1.5 bg-popover border-border"
          >
            <DropdownMenuGroup className="space-y-1">
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedModel("Local")}
              >
                <IconDeviceLaptop size={16} className="opacity-60" />
                Local
              </DropdownMenuItem>
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedModel("Cloud")}
              >
                <IconCloud size={16} className="opacity-60" />
                Cloud
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 rounded-full border border-transparent hover:bg-accent text-muted-foreground text-xs"
            >
              <IconUser className="size-3" />
              <span>{selectedAgent}</span>
              <IconChevronDown className="size-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="max-w-xs rounded-2xl p-1.5 bg-popover border-border"
          >
            <DropdownMenuGroup className="space-y-1">
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedAgent("Agent")}
              >
                <IconUser size={16} className="opacity-60" />
                Agent
              </DropdownMenuItem>
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedAgent("Assistant")}
              >
                Assistant
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 rounded-full border border-transparent hover:bg-accent text-muted-foreground text-xs"
            >
              <IconBolt className="size-3" />
              <span>{selectedPerformance}</span>
              <IconChevronDown className="size-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="max-w-xs rounded-2xl p-1.5 bg-popover border-border"
          >
            <DropdownMenuGroup className="space-y-1">
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedPerformance("High")}
              >
                <IconCircle size={16} className="opacity-60" />
                High
              </DropdownMenuItem>
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedPerformance("Medium")}
              >
                <IconProgress size={16} className="opacity-60" />
                Medium
              </DropdownMenuItem>
              <DropdownMenuItem
                className="rounded-[calc(1rem-6px)] text-xs"
                onClick={() => setSelectedPerformance("Low")}
              >
                <IconCircleDashed size={16} className="opacity-60" />
                Low
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="flex-1" />
      </div>
    </div>
  );
}
