import React, { useState } from 'react';
import { Settings, Play, Palette, Clock, Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface AppInspectorProps {
    className?: string;
    selectedCardId?: string | null;
}

export const AppInspector: React.FC<AppInspectorProps> = ({ className, selectedCardId }) => {
    const [activeTab, setActiveTab] = useState<'config' | 'triggers' | 'appearance'>('config');

    if (!selectedCardId) {
        return (
            <div className={cn("h-full flex flex-col items-center justify-center p-8 text-center text-muted-foreground", className)}>
                <Settings className="w-12 h-12 opacity-20 mb-4" />
                <p className="text-sm font-medium">No Component Selected</p>
                <p className="text-xs opacity-70">Select a card on the canvas to configure settings.</p>
            </div>
        );
    }

    return (
        <div className={cn("h-full flex flex-col bg-charcoal-900 border-l border-border", className)}>
            {/* Header */}
            <div className="p-4 border-b border-border bg-charcoal-900/95 backdrop-blur">
                <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full bg-primary" />
                    <span className="font-bold text-sm text-foreground">Score Card</span>
                </div>
                <div className="text-[10px] text-muted-foreground font-mono">{selectedCardId}</div>
            </div>

            {/* Tabs */}
            <div className="flex items-center border-b border-border px-2">
                <button
                    onClick={() => setActiveTab('config')}
                    className={cn(
                        "flex items-center gap-2 px-3 py-3 text-xs font-medium border-b-2 transition-all hover:bg-accent/50",
                        activeTab === 'config' ? "border-primary text-primary bg-primary/5" : "border-transparent text-muted-foreground"
                    )}
                >
                    <Settings className="w-3 h-3" /> Config
                </button>
                <button
                    onClick={() => setActiveTab('triggers')}
                    className={cn(
                        "flex items-center gap-2 px-3 py-3 text-xs font-medium border-b-2 transition-all hover:bg-accent/50",
                        activeTab === 'triggers' ? "border-primary text-primary bg-primary/5" : "border-transparent text-muted-foreground"
                    )}
                >
                    <Play className="w-3 h-3" /> Triggers
                </button>
                <button
                    onClick={() => setActiveTab('appearance')}
                    className={cn(
                        "flex items-center gap-2 px-3 py-3 text-xs font-medium border-b-2 transition-all hover:bg-accent/50",
                        activeTab === 'appearance' ? "border-primary text-primary bg-primary/5" : "border-transparent text-muted-foreground"
                    )}
                >
                    <Palette className="w-3 h-3" /> Style
                </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">

                {/* Configuration Tab */}
                {activeTab === 'config' && (
                    <div className="space-y-6">
                        <div className="space-y-3">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Data Source</div>
                            <div className="p-3 bg-white/5 rounded border border-white/10 space-y-3">
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Source Type</label>
                                    <select className="w-full bg-black/50 border border-white/10 rounded px-2 py-1.5 text-xs text-foreground focus:outline-none">
                                        <option>Agent Run (Output)</option>
                                        <option>Static Value</option>
                                        <option>Python Script</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Select Agent</label>
                                    <select className="w-full bg-black/50 border border-white/10 rounded px-2 py-1.5 text-xs text-foreground focus:outline-none">
                                        <option>Research Agent v2</option>
                                        <option>Financial Analyst</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Input Mapping</div>
                            <div className="p-3 bg-white/5 rounded border border-white/10 space-y-2">
                                <p className="text-[10px] text-muted-foreground italic">Map dashboard inputs to agent arguments.</p>
                                <div className="flex items-center gap-2">
                                    <Terminal className="w-3 h-3 text-muted-foreground" />
                                    <span className="text-xs font-mono text-foreground">ticker</span>
                                    <span className="text-xs text-muted-foreground">=</span>
                                    <div className="flex-1 px-2 py-1 bg-black/50 rounded border border-white/10 text-xs text-primary font-mono">
                                        InputCard_1.value
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Triggers Tab */}
                {activeTab === 'triggers' && (
                    <div className="space-y-6">
                        <div className="space-y-3">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Manual Trigger</div>
                            <Button className="w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
                                <Play className="w-4 h-4" /> Run Now
                            </Button>
                        </div>

                        <div className="space-y-3">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Schedule</div>
                            <div className="p-3 bg-white/5 rounded border border-white/10 space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs text-foreground">Enable Schedule</span>
                                    <div className="w-8 h-4 bg-primary/20 rounded-full relative cursor-pointer">
                                        <div className="absolute right-0.5 top-0.5 w-3 h-3 bg-primary rounded-full shadow-sm" />
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Cron Expression</label>
                                    <div className="flex gap-2">
                                        <Input className="h-8 font-mono text-xs" defaultValue="0 9 * * 1-5" />
                                        <div className="flex items-center justify-center px-2 bg-white/5 rounded text-[10px] text-muted-foreground">
                                            <Clock className="w-3 h-3" />
                                        </div>
                                    </div>
                                    <p className="text-[10px] text-muted-foreground">Runs at 09:00, Monday through Friday.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Appearance Tab */}
                {activeTab === 'appearance' && (
                    <div className="space-y-6">
                        <div className="space-y-3">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">General</div>
                            <div className="space-y-2">
                                <label className="text-xs text-muted-foreground">Card Title</label>
                                <Input className="h-8 text-xs" placeholder="e.g. Quarterly Revenue" />
                            </div>
                        </div>
                        <div className="space-y-3">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Colors</div>
                            <div className="grid grid-cols-5 gap-2">
                                {['bg-red-500', 'bg-blue-500', 'bg-green-500', 'bg-yellow-500', 'bg-purple-500'].map(c => (
                                    <div key={c} className={cn("w-6 h-6 rounded-full cursor-pointer hover:scale-110 transition-transform ring-1 ring-white/10", c)} />
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
