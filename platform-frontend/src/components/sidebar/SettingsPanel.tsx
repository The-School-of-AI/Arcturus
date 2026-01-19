import React from 'react';
import { Cpu, FileText, Brain, Terminal, Wrench, Settings, ChevronRight, Layout } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';

type SettingsTabId = 'models' | 'rag' | 'agent' | 'ide' | 'prompts' | 'advanced';

const SETTINGS_TABS: { id: SettingsTabId; label: string; icon: typeof Cpu; description: string }[] = [
    { id: 'models', label: 'Models', icon: Cpu, description: 'Ollama & Gemini models' },
    { id: 'rag', label: 'RAG Pipeline', icon: FileText, description: 'Chunking & search' },
    { id: 'agent', label: 'Agent', icon: Brain, description: 'Execution & Gemini' },
    { id: 'ide', label: 'IDE', icon: Layout, description: 'IDE, Test, & Debugging' },
    { id: 'prompts', label: 'Prompts', icon: Terminal, description: 'Agent prompts' },
    { id: 'advanced', label: 'Advanced', icon: Wrench, description: 'URLs & restart' },
];

export const SettingsPanel: React.FC = () => {
    const { settingsActiveTab, setSettingsActiveTab } = useAppStore();

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header */}
            <div className="px-4 py-4 border-b border-border/50 bg-muted/20">
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                        <Settings className="w-4 h-4" />
                    </div>
                    <div>
                        <h2 className="text-xs font-bold uppercase tracking-widest text-primary">System Settings</h2>
                        <p className="text-[10px] text-muted-foreground opacity-60">Configure your environment</p>
                    </div>
                </div>
            </div>

            {/* Tabs List */}
            <nav className="flex-1 p-4 space-y-3 overflow-y-auto scrollbar-hide">
                {SETTINGS_TABS.map((tab) => {
                    const isActive = settingsActiveTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setSettingsActiveTab(tab.id)}
                            className={cn(
                                "w-full flex items-center gap-4 p-4 rounded-xl border transition-all duration-300 text-left group overflow-hidden relative",
                                isActive
                                    ? "border-primary/40 bg-primary/5 shadow-lg shadow-primary/5 ring-1 ring-primary/20"
                                    : "border-border/50 hover:border-primary/50 hover:bg-accent/50 hover:shadow-md"
                            )}
                        >
                            <div className={cn(
                                "p-2 rounded-lg transition-colors duration-300",
                                isActive ? "bg-primary text-white" : "bg-muted text-muted-foreground group-hover:text-foreground"
                            )}>
                                <tab.icon className="w-4 h-4 shrink-0" />
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className={cn(
                                    "text-[13px] font-bold tracking-tight transition-colors duration-300",
                                    isActive ? "text-primary" : "text-foreground group-hover:text-primary"
                                )}>
                                    {tab.label}
                                </div>
                                <div className="text-[10px] text-muted-foreground opacity-60 truncate group-hover:opacity-100 transition-opacity">
                                    {tab.description}
                                </div>
                            </div>

                            <ChevronRight className={cn(
                                "w-4 h-4 shrink-0 transition-all duration-300",
                                isActive ? "rotate-90 text-primary" : "text-muted-foreground/30 group-hover:text-primary/50"
                            )} />
                        </button>
                    );
                })}
            </nav>
        </div>
    );
};
