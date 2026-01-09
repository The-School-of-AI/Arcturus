import React from 'react';
import { Cpu, FileText, Brain, Terminal, Wrench, Settings, ChevronRight } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';

type SettingsTabId = 'models' | 'rag' | 'agent' | 'prompts' | 'advanced';

const SETTINGS_TABS: { id: SettingsTabId; label: string; icon: typeof Cpu; description: string }[] = [
    { id: 'models', label: 'Models', icon: Cpu, description: 'Ollama & Gemini models' },
    { id: 'rag', label: 'RAG Pipeline', icon: FileText, description: 'Chunking & search' },
    { id: 'agent', label: 'Agent', icon: Brain, description: 'Execution & Gemini' },
    { id: 'prompts', label: 'Prompts', icon: Terminal, description: 'Agent prompts' },
    { id: 'advanced', label: 'Advanced', icon: Wrench, description: 'URLs & restart' },
];

export const SettingsPanel: React.FC = () => {
    const { settingsActiveTab, setSettingsActiveTab } = useAppStore();

    return (
        <div className="flex flex-col h-full bg-card text-foreground">

            {/* Tabs List */}
            <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
                {SETTINGS_TABS.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setSettingsActiveTab(tab.id)}
                        className={cn(
                            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left group",
                            settingsActiveTab === tab.id
                                ? "bg-primary/10 text-primary border border-primary/20"
                                : "text-muted-foreground hover:bg-muted/50"
                        )}
                    >
                        <tab.icon className="w-4 h-4 shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium">{tab.label}</div>
                            <div className="text-[10px] opacity-60 truncate">{tab.description}</div>
                        </div>
                        <ChevronRight className={cn(
                            "w-4 h-4 shrink-0 transition-transform",
                            settingsActiveTab === tab.id && "rotate-90 text-primary"
                        )} />
                    </button>
                ))}
            </nav>
        </div>
    );
};
