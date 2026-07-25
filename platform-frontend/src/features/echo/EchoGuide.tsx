import React from 'react';
import {
    Mic, MessageSquare, Navigation, FileText, Zap, Shield, Volume2,
    ArrowRight, Keyboard, Globe, BookOpen, Layout
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface CapabilityCardProps {
    icon: React.ReactNode;
    title: string;
    description: string;
    examples: string[];
    accent: string;       // tailwind color token like "violet" | "emerald" etc.
}

const CapabilityCard: React.FC<CapabilityCardProps> = ({ icon, title, description, examples, accent }) => (
    <div className={cn(
        'group rounded-xl border bg-card/50 p-4 transition-all duration-200',
        'hover:bg-card/80 hover:shadow-lg hover:shadow-black/10',
        `border-${accent}-500/20 hover:border-${accent}-500/40`
    )}>
        <div className="flex items-start gap-3">
            <div className={cn(
                'shrink-0 w-9 h-9 rounded-lg flex items-center justify-center',
                `bg-${accent}-500/15 text-${accent}-400`
            )}>
                {icon}
            </div>
            <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-foreground mb-0.5">{title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed mb-2.5">{description}</p>
                <div className="space-y-1.5">
                    {examples.map((ex, i) => (
                        <div key={i} className="flex items-center gap-2">
                            <ArrowRight className={cn('w-3 h-3 shrink-0', `text-${accent}-500/50`)} />
                            <span className="text-xs text-foreground/70 italic">"{ex}"</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    </div>
);

const CAPABILITIES: CapabilityCardProps[] = [
    {
        icon: <MessageSquare className="w-4.5 h-4.5" />,
        title: 'Ask Questions',
        description: 'Ask anything — get answers via direct chat or multi-step Nexus agents. Supports follow-up questions for 30 seconds.',
        examples: [
            'What is quantum computing?',
            'Summarize this project',
            'What meetings do I have today?',
        ],
        accent: 'violet',
    },
    {
        icon: <Navigation className="w-4.5 h-4.5" />,
        title: 'Navigate Tabs',
        description: 'Switch between any tab instantly with short voice commands. Works with all sidebar destinations.',
        examples: [
            'Open the explorer',
            'Go to settings',
            'Show me the canvas',
        ],
        accent: 'sky',
    },
    {
        icon: <Zap className="w-4.5 h-4.5" />,
        title: 'Run Agents',
        description: 'Trigger complex multi-step Nexus agent runs. Streaming TTS speaks results as they arrive — no waiting.',
        examples: [
            'Check my emails and summarize them',
            'Find and fix the bug in auth',
            'Plan a migration strategy',
        ],
        accent: 'amber',
    },
    {
        icon: <FileText className="w-4.5 h-4.5" />,
        title: 'Dictation Mode',
        description: 'Transcribe speech to text — no LLM processing. Auto-saves to Notes every 10 seconds.',
        examples: [
            'Start dictation',
            'Take a note',
            'Stop dictation',
        ],
        accent: 'emerald',
    },
];

const NAV_TARGETS = [
    'Runs', 'Notes', 'RAG', 'Settings', 'Apps', 'Explorer',
    'Scheduler', 'IDE', 'Console', 'Studio', 'Skills', 'Canvas',
    'MCP', 'Memory', 'News', 'Learn', 'Echo', 'Inbox',
    'Calendar', 'Home', 'Graph',
];

export const EchoGuide: React.FC = () => {
    return (
        <div className="w-full h-full overflow-y-auto bg-background">
            <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">

                {/* Hero */}
                <div className="text-center space-y-3">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-violet-500/15 border border-violet-500/30 mb-2">
                        <Mic className="w-7 h-7 text-violet-400" />
                    </div>
                    <h1 className="text-2xl font-bold text-foreground tracking-tight">Echo Voice Assistant</h1>
                    <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
                        Talk to Arcturus hands-free. Ask questions, navigate tabs,
                        run agents, or dictate notes — all by voice.
                    </p>
                    <div className="flex items-center justify-center gap-4 pt-1">
                        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground/70 bg-muted/30 px-2.5 py-1 rounded-full border border-border/30">
                            <Keyboard className="w-3 h-3" />
                            Say "Hey Arcturus" or tap the mic
                        </span>
                    </div>
                </div>

                {/* Capabilities Grid */}
                <div>
                    <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60 mb-3 flex items-center gap-2">
                        <BookOpen className="w-3.5 h-3.5" />
                        What you can do
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {CAPABILITIES.map(cap => (
                            <CapabilityCard key={cap.title} {...cap} />
                        ))}
                    </div>
                </div>

                {/* Navigation Targets */}
                <div>
                    <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60 mb-3 flex items-center gap-2">
                        <Layout className="w-3.5 h-3.5" />
                        Voice-navigable tabs
                    </h2>
                    <div className="flex flex-wrap gap-1.5">
                        {NAV_TARGETS.map(tab => (
                            <span
                                key={tab}
                                className="px-2.5 py-1 text-xs rounded-md bg-sky-500/8 border border-sky-500/20 text-sky-400/80 font-medium"
                            >
                                {tab}
                            </span>
                        ))}
                    </div>
                </div>

                {/* Features strip */}
                <div>
                    <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60 mb-3 flex items-center gap-2">
                        <Volume2 className="w-3.5 h-3.5" />
                        Features
                    </h2>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        {[
                            {
                                icon: <Shield className="w-4 h-4" />,
                                label: 'Privacy Mode',
                                desc: 'Switch to fully local STT + TTS — nothing leaves your device',
                                color: 'emerald',
                            },
                            {
                                icon: <Volume2 className="w-4 h-4" />,
                                label: 'Voice Personas',
                                desc: 'Professional, Casual, or Energetic — switch anytime',
                                color: 'violet',
                            },
                            {
                                icon: <Globe className="w-4 h-4" />,
                                label: 'Barge-in',
                                desc: 'Interrupt the agent mid-sentence by speaking over it',
                                color: 'amber',
                            },
                        ].map(f => (
                            <div
                                key={f.label}
                                className={cn(
                                    'rounded-lg border p-3 bg-card/30',
                                    `border-${f.color}-500/15`
                                )}
                            >
                                <div className={cn('mb-1.5', `text-${f.color}-400`)}>{f.icon}</div>
                                <p className="text-xs font-semibold text-foreground mb-0.5">{f.label}</p>
                                <p className="text-xs text-muted-foreground/70 leading-relaxed">{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Quick tips */}
                <div className="rounded-lg border border-border/30 bg-muted/10 p-4 text-xs text-muted-foreground space-y-1.5">
                    <p className="font-semibold text-foreground/80 mb-2">Tips</p>
                    <p>After the agent responds, you have <strong className="text-foreground/80">30 seconds</strong> to ask a follow-up without re-triggering the wake word.</p>
                    <p>Short imperative commands like <em>"Open settings"</em> route to instant navigation — no LLM delay.</p>
                    <p>For dictation, say <em>"Stop dictation"</em> when done. Your text is auto-saved to <strong className="text-foreground/80">Notes &gt; Voice</strong>.</p>
                </div>

            </div>
        </div>
    );
};

export default EchoGuide;
