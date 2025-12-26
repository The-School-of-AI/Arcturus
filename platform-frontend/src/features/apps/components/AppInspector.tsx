import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Settings2, Zap, Palette, Database, Info, Trash2, Clock, Terminal } from 'lucide-react';
import { useAppStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface AppInspectorProps {
    className?: string;
}

// Helper for Smart Default Dimensions (Duplicate of AppGrid logic for now)
const getSmartDimensions = (type: string) => {
    switch (type) {
        case 'divider':
        case 'spacer':
        case 'header':
            return { w: 12, h: 2 };
        case 'metric':
        case 'trend':
        case 'score_card':
        case 'grade_card':
            return { w: 3, h: 3 };
        case 'line_chart':
        case 'bar_chart':
        case 'area_chart':
        case 'candlestick':
        case 'scatter':
        case 'valuation':
            return { w: 6, h: 6 };
        case 'table':
        case 'peer_table':
        case 'ratios':
        case 'cash_flow':
        case 'balance_sheet':
        case 'income_stmt':
        case 'log':
        case 'code':
        case 'json':
            return { w: 6, h: 8 };
        default:
            return { w: 4, h: 4 };
    }
};

export const AppInspector: React.FC<AppInspectorProps> = ({ className }) => {
    const [activeTab, setActiveTab] = useState<'config' | 'triggers' | 'style'>('config');

    // Connect to Store
    const {
        appCards,
        selectedAppCardId,
        selectedLibraryComponent,
        removeAppCard,
        addAppCard,
        updateAppCardConfig
    } = useAppStore();

    const selectedCard = appCards.find(c => c.id === selectedAppCardId);

    // Handle "Preview Mode" (Library Item Selected)
    if (!selectedCard && selectedLibraryComponent) {
        const onAddClick = () => {
            const newId = `${selectedLibraryComponent.type}-${Date.now()}`;
            const dims = getSmartDimensions(selectedLibraryComponent.type);

            const newCard = {
                id: newId,
                type: selectedLibraryComponent.type,
                label: selectedLibraryComponent.label,
                config: {},
                data: {}
            };
            // Default position (0,0) or find first available slot
            // Passing dims (w, h) ensures it respects the smart sizing
            addAppCard(newCard, { x: 0, y: Infinity, ...dims });
        };

        return (
            <div className={cn("h-full flex flex-col bg-charcoal-900 border-l border-border", className)}>
                <div className="p-4 border-b border-border flex items-center gap-2 bg-primary/5">
                    <div className="p-1.5 rounded bg-primary/20 text-primary">
                        <Info className="w-4 h-4" />
                    </div>
                    <div>
                        <div className="font-bold text-xs uppercase tracking-wider text-primary">Library Preview</div>
                        <div className="text-[10px] text-muted-foreground font-mono opacity-80">{selectedLibraryComponent.type}</div>
                    </div>
                </div>

                <div className="p-6 space-y-6 flex-1 overflow-y-auto">
                    <div className="space-y-2 text-center">
                        <h3 className="text-xl font-bold text-foreground">{selectedLibraryComponent.label}</h3>
                        <p className="text-sm text-muted-foreground">{selectedLibraryComponent.description}</p>
                    </div>

                    <div className="p-4 rounded-lg bg-black/40 border border-white/10 space-y-2">
                        <div className="text-[10px] uppercase font-bold text-muted-foreground">Typical Usage</div>
                        <p className="text-xs text-foreground leading-relaxed">{selectedLibraryComponent.usage}</p>
                    </div>

                    <div className="flex justify-center">
                        <div className="w-32 h-20 border border-dashed border-white/20 rounded-lg flex items-center justify-center text-xs text-muted-foreground">
                            Visual Preview
                        </div>
                    </div>
                </div>

                <div className="p-4 border-t border-border bg-black/20">
                    <Button onClick={onAddClick} className="w-full gap-2 bg-primary text-primary-foreground font-bold text-xs h-10 uppercase tracking-widest hover:bg-primary/90">
                        <Zap className="w-4 h-4" /> Add to Canvas
                    </Button>
                </div>
            </div>
        );
    }

    if (!selectedCard) {
        return (
            <div className={cn("h-full flex flex-col items-center justify-center p-8 bg-charcoal-900 text-center space-y-4", className)}>
                <div className="p-4 rounded-full bg-white/5">
                    <Settings2 className="w-8 h-8 text-muted-foreground opacity-20" />
                </div>
                <div className="space-y-1">
                    <h3 className="font-bold text-foreground">No Component Selected</h3>
                    <p className="text-xs text-muted-foreground">Select a card on the builder canvas to configure its logic and appearance.</p>
                </div>
            </div>
        );
    }

    return (
        <div className={cn("h-full flex flex-col bg-charcoal-900 border-l border-border", className)}>
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded bg-primary/10 text-primary">
                        <Settings2 className="w-4 h-4" />
                    </div>
                    <div>
                        <div className="font-bold text-xs uppercase tracking-wider">{selectedCard.label}</div>
                        <div className="text-[10px] text-muted-foreground font-mono opacity-50">{selectedCard.id}</div>
                    </div>
                </div>
                <button
                    onClick={() => removeAppCard(selectedCard.id)}
                    className="p-1.5 hover:bg-red-500/10 text-muted-foreground hover:text-red-400 rounded transition-colors"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-border bg-black/20">
                <TabButton active={activeTab === 'config'} onClick={() => setActiveTab('config')} icon={<Settings2 className="w-3.5 h-3.5" />} label="Config" />
                <TabButton active={activeTab === 'triggers'} onClick={() => setActiveTab('triggers')} icon={<Zap className="w-3.5 h-3.5" />} label="Triggers" />
                <TabButton active={activeTab === 'style'} onClick={() => setActiveTab('style')} icon={<Palette className="w-3.5 h-3.5" />} label="Style" />
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-6">
                {activeTab === 'config' && (
                    <div className="space-y-5 animate-in fade-in slide-in-from-right-2 duration-200">
                        <div className="space-y-3">
                            <SectionHeader icon={<Database className="w-3 h-3" />} label="Data Source" />
                            <div className="space-y-2">
                                <label className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">Connected Source</label>
                                <select className="w-full bg-charcoal-800 border border-border rounded text-xs px-2 py-1.5 text-foreground focus:outline-none">
                                    <option>Local State (Default)</option>
                                    <option>Research Agent (Live)</option>
                                    <option>Script Output</option>
                                </select>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <SectionHeader icon={<Terminal className="w-3 h-3" />} label="Properties" />
                            <div className="space-y-1.5">
                                <label className="text-[10px] text-muted-foreground font-bold uppercase">Display Title</label>
                                <Input
                                    value={selectedCard.label}
                                    onChange={(e) => updateAppCardConfig(selectedCard.id, { label: e.target.value })}
                                    className="bg-charcoal-800 border-border text-xs h-8"
                                />
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'triggers' && (
                    <div className="space-y-5 animate-in fade-in slide-in-from-right-2 duration-200">
                        <SectionHeader icon={<Zap className="w-3 h-3" />} label="Event Triggers" />
                        <div className="p-4 rounded-lg border border-dashed border-border flex flex-col items-center justify-center text-center space-y-2">
                            <Clock className="w-6 h-6 text-muted-foreground opacity-20" />
                            <p className="text-xs text-muted-foreground">Coming soon: Schedule or trigger actions from this card.</p>
                        </div>
                    </div>
                )}

                {activeTab === 'style' && (
                    <div className="space-y-5 animate-in fade-in slide-in-from-right-2 duration-200">
                        <SectionHeader icon={<Palette className="w-3 h-3" />} label="Appearance" />
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <label className="text-[10px] text-muted-foreground font-bold uppercase">Accent</label>
                                <div className="w-full h-8 rounded bg-primary border border-white/10" />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-[10px] text-muted-foreground font-bold uppercase">Opacity</label>
                                <div className="w-full h-8 rounded bg-white/5 border border-white/10 flex items-center justify-center text-[10px]">100%</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="p-4 border-t border-border bg-black/20">
                <Button className="w-full bg-primary text-primary-foreground font-bold text-xs h-9 uppercase tracking-widest">
                    Save Config
                </Button>
            </div>
        </div>
    );
};

const TabButton = ({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string }) => (
    <button
        onClick={onClick}
        className={cn(
            "flex-1 flex items-center justify-center gap-2 py-3 text-[10px] font-bold uppercase tracking-tighter transition-all relative",
            active ? "text-primary bg-primary/5" : "text-muted-foreground hover:text-foreground"
        )}
    >
        {icon}
        {label}
        {active && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />}
    </button>
);

const SectionHeader = ({ icon, label }: { icon: React.ReactNode, label: string }) => (
    <div className="flex items-center gap-2 pb-2 border-b border-border/50">
        <div className="text-primary">{icon}</div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-foreground">{label}</span>
    </div>
);
