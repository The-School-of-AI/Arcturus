import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Settings2, Zap, Palette, Database, Info, Trash2, Clock, Terminal, Eye, EyeOff, ChevronDown, ChevronRight } from 'lucide-react';
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

// Define features for each card type
const CARD_FEATURES: Record<string, { name: string; key: string; default: boolean }[]> = {
    metric: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Trend Arrow', key: 'showTrend', default: true },
        { name: 'Show Percentage', key: 'showPercent', default: true },
    ],
    trend: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Sparkline', key: 'showSparkline', default: true },
        { name: 'Show Change', key: 'showChange', default: true },
    ],
    line_chart: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Axis Labels', key: 'showAxis', default: true },
        { name: 'Enable Animation', key: 'animate', default: true },
    ],
    bar_chart: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Values', key: 'showValues', default: false },
    ],
    pie_chart: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Percentages', key: 'showPercent', default: true },
        { name: 'Donut Style', key: 'donut', default: false },
    ],
    table: [
        { name: 'Show Header', key: 'showHeader', default: true },
        { name: 'Striped Rows', key: 'striped', default: true },
        { name: 'Hover Highlight', key: 'hoverHighlight', default: true },
        { name: 'Show Borders', key: 'showBorders', default: true },
    ],
    profile: [
        { name: 'Show Logo', key: 'showLogo', default: true },
        { name: 'Show Ticker', key: 'showTicker', default: true },
        { name: 'Show Description', key: 'showDescription', default: true },
        { name: 'Show Sector Info', key: 'showSector', default: true },
    ],
    valuation: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Prices', key: 'showPrices', default: true },
        { name: 'Show Gauge Bar', key: 'showGauge', default: true },
        { name: 'Show Label', key: 'showLabel', default: true },
    ],
    json: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Syntax Highlighting', key: 'highlight', default: true },
        { name: 'Collapsible Nodes', key: 'collapsible', default: true },
        { name: 'Show Line Numbers', key: 'lineNumbers', default: false },
    ],
    code: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Syntax Highlighting', key: 'highlight', default: true },
        { name: 'Show Line Numbers', key: 'lineNumbers', default: true },
        { name: 'Word Wrap', key: 'wordWrap', default: false },
    ],
    markdown: [
        { name: 'Show Title', key: 'showTitle', default: false },
        { name: 'Enable Editing', key: 'editable', default: true },
    ],
    header: [
        { name: 'Bold', key: 'bold', default: true },
        { name: 'Centered', key: 'centered', default: false },
    ],
    text: [
        { name: 'Show Border', key: 'showBorder', default: false },
        { name: 'Editable', key: 'editable', default: true },
    ],
};

// Default colors for cards
const DEFAULT_COLORS = {
    accent: '#eaff00',      // neon-yellow
    background: '#1a1b1e',  // charcoal-900
    text: '#ffffff',        // white
    secondary: '#6b7280',   // gray-500
    border: 'rgba(255,255,255,0.1)', // white/10
    success: '#4ade80',     // green-400
    danger: '#f87171',      // red-400
};

const COLOR_PRESETS = [
    { name: 'Neon Yellow', value: '#eaff00' },
    { name: 'Cyan', value: '#22d3ee' },
    { name: 'Green', value: '#4ade80' },
    { name: 'Purple', value: '#a855f7' },
    { name: 'Pink', value: '#ec4899' },
    { name: 'Orange', value: '#fb923c' },
    { name: 'Blue', value: '#3b82f6' },
    { name: 'White', value: '#ffffff' },
];

export const AppInspector: React.FC<AppInspectorProps> = ({ className }) => {
    const [activeTab, setActiveTab] = useState<'config' | 'triggers' | 'style'>('style');
    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
        appearance: true,
        border: true,
        features: true,
        colors: true,
    });

    // Connect to Store
    const {
        appCards,
        selectedAppCardId,
        selectedLibraryComponent,
        removeAppCard,
        addAppCard,
        updateAppCardConfig,
        updateAppCardStyle
    } = useAppStore();

    const selectedCard = appCards.find(c => c.id === selectedAppCardId);

    const toggleSection = (section: string) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

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
                data: {},
                style: { showBorder: true, opacity: 100, accentColor: DEFAULT_COLORS.accent }
            };
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

    const cardStyle = selectedCard.style || { showBorder: true, opacity: 100, accentColor: DEFAULT_COLORS.accent };
    const cardFeatures = CARD_FEATURES[selectedCard.type] || [];

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
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-4">
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
                    <div className="space-y-3 animate-in fade-in slide-in-from-right-2 duration-200">
                        
                        {/* BORDER SECTION */}
                        <CollapsibleSection
                            title="Border"
                            icon={<div className="w-3 h-3 border-2 border-current rounded-sm" />}
                            expanded={expandedSections.border}
                            onToggle={() => toggleSection('border')}
                        >
                            <div className="space-y-3">
                                <ToggleRow
                                    label="Show Border"
                                    enabled={cardStyle.showBorder !== false}
                                    onChange={(v) => updateAppCardStyle(selectedCard.id, { showBorder: v })}
                                />
                                
                                {cardStyle.showBorder !== false && (
                                    <>
                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-muted-foreground font-bold uppercase">Border Width</label>
                                            <div className="flex gap-1">
                                                {[1, 2, 3].map(w => (
                                                    <button
                                                        key={w}
                                                        onClick={() => updateAppCardStyle(selectedCard.id, { borderWidth: w })}
                                                        className={cn(
                                                            "flex-1 py-1.5 text-[10px] rounded border transition-colors",
                                                            (cardStyle.borderWidth || 2) === w
                                                                ? "bg-primary/20 border-primary text-primary"
                                                                : "bg-charcoal-800 border-white/10 text-muted-foreground hover:border-white/20"
                                                        )}
                                                    >
                                                        {w}px
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                        
                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-muted-foreground font-bold uppercase">Border Color</label>
                                            <ColorPicker
                                                value={cardStyle.borderColor || 'rgba(255,255,255,0.1)'}
                                                onChange={(c) => updateAppCardStyle(selectedCard.id, { borderColor: c })}
                                                presets={[
                                                    { name: 'Default', value: 'rgba(255,255,255,0.1)' },
                                                    { name: 'Light', value: 'rgba(255,255,255,0.2)' },
                                                    { name: 'Accent', value: '#eaff00' },
                                                    { name: 'None', value: 'transparent' },
                                                ]}
                                            />
                                        </div>
                                    </>
                                )}
                            </div>
                        </CollapsibleSection>

                        {/* APPEARANCE SECTION */}
                        <CollapsibleSection
                            title="Appearance"
                            icon={<Palette className="w-3 h-3" />}
                            expanded={expandedSections.appearance}
                            onToggle={() => toggleSection('appearance')}
                        >
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Accent Color</label>
                                    <ColorPicker
                                        value={cardStyle.accentColor || DEFAULT_COLORS.accent}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { accentColor: c })}
                                        presets={COLOR_PRESETS}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Background</label>
                                    <ColorPicker
                                        value={cardStyle.backgroundColor || 'transparent'}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { backgroundColor: c })}
                                        presets={[
                                            { name: 'Default', value: 'transparent' },
                                            { name: 'Dark', value: '#0a0b0d' },
                                            { name: 'Charcoal', value: '#1a1b1e' },
                                            { name: 'Lighter', value: '#2a2b2e' },
                                        ]}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <div className="flex justify-between items-center">
                                        <label className="text-[10px] text-muted-foreground font-bold uppercase">Opacity</label>
                                        <span className="text-[10px] text-primary font-mono">{cardStyle.opacity || 100}%</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="20"
                                        max="100"
                                        value={cardStyle.opacity || 100}
                                        onChange={(e) => updateAppCardStyle(selectedCard.id, { opacity: parseInt(e.target.value) })}
                                        className="w-full h-1.5 bg-charcoal-800 rounded-full appearance-none cursor-pointer accent-primary"
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Corner Radius</label>
                                    <div className="flex gap-1">
                                        {[
                                            { label: 'None', value: 0 },
                                            { label: 'SM', value: 8 },
                                            { label: 'MD', value: 12 },
                                            { label: 'LG', value: 16 },
                                        ].map(opt => (
                                            <button
                                                key={opt.value}
                                                onClick={() => updateAppCardStyle(selectedCard.id, { borderRadius: opt.value })}
                                                className={cn(
                                                    "flex-1 py-1.5 text-[10px] rounded border transition-colors",
                                                    (cardStyle.borderRadius ?? 12) === opt.value
                                                        ? "bg-primary/20 border-primary text-primary"
                                                        : "bg-charcoal-800 border-white/10 text-muted-foreground hover:border-white/20"
                                                )}
                                            >
                                                {opt.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </CollapsibleSection>

                        {/* FEATURES SECTION */}
                        {cardFeatures.length > 0 && (
                            <CollapsibleSection
                                title="Features"
                                icon={<Eye className="w-3 h-3" />}
                                expanded={expandedSections.features}
                                onToggle={() => toggleSection('features')}
                            >
                                <div className="space-y-2">
                                    {cardFeatures.map(feature => {
                                        const isEnabled = selectedCard.config?.[feature.key] ?? feature.default;
                                        return (
                                            <ToggleRow
                                                key={feature.key}
                                                label={feature.name}
                                                enabled={isEnabled}
                                                onChange={(v) => updateAppCardConfig(selectedCard.id, { [feature.key]: v })}
                                            />
                                        );
                                    })}
                                </div>
                            </CollapsibleSection>
                        )}

                        {/* COLORS SECTION */}
                        <CollapsibleSection
                            title="Color Overrides"
                            icon={<div className="w-3 h-3 rounded-full bg-gradient-to-br from-primary to-green-400" />}
                            expanded={expandedSections.colors}
                            onToggle={() => toggleSection('colors')}
                        >
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Text Color</label>
                                    <ColorPicker
                                        value={cardStyle.textColor || '#ffffff'}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { textColor: c })}
                                        presets={[
                                            { name: 'White', value: '#ffffff' },
                                            { name: 'Gray', value: '#9ca3af' },
                                            { name: 'Accent', value: '#eaff00' },
                                            { name: 'Muted', value: '#6b7280' },
                                        ]}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Success Color</label>
                                    <ColorPicker
                                        value={cardStyle.successColor || '#4ade80'}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { successColor: c })}
                                        presets={[
                                            { name: 'Green', value: '#4ade80' },
                                            { name: 'Cyan', value: '#22d3ee' },
                                            { name: 'Accent', value: '#eaff00' },
                                        ]}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Danger Color</label>
                                    <ColorPicker
                                        value={cardStyle.dangerColor || '#f87171'}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { dangerColor: c })}
                                        presets={[
                                            { name: 'Red', value: '#f87171' },
                                            { name: 'Orange', value: '#fb923c' },
                                            { name: 'Pink', value: '#ec4899' },
                                        ]}
                                    />
                                </div>
                            </div>
                        </CollapsibleSection>

                    </div>
                )}
            </div>
        </div>
    );
};

// Sub-Components

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

const CollapsibleSection = ({ 
    title, 
    icon, 
    expanded, 
    onToggle, 
    children 
}: { 
    title: string; 
    icon: React.ReactNode; 
    expanded: boolean; 
    onToggle: () => void; 
    children: React.ReactNode;
}) => (
    <div className="rounded-lg border border-white/5 overflow-hidden bg-charcoal-800/30">
        <button
            onClick={onToggle}
            className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
        >
            <div className="flex items-center gap-2">
                <div className="text-primary">{icon}</div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-foreground">{title}</span>
            </div>
            {expanded ? <ChevronDown className="w-3 h-3 text-muted-foreground" /> : <ChevronRight className="w-3 h-3 text-muted-foreground" />}
        </button>
        {expanded && (
            <div className="p-3 pt-0 border-t border-white/5 animate-in slide-in-from-top-1 duration-200">
                {children}
            </div>
        )}
    </div>
);

const ToggleRow = ({ label, enabled, onChange }: { label: string; enabled: boolean; onChange: (v: boolean) => void }) => (
    <div className="flex items-center justify-between py-1">
        <span className="text-xs text-foreground">{label}</span>
        <button
            onClick={() => onChange(!enabled)}
            className={cn(
                "w-9 h-5 rounded-full transition-colors relative",
                enabled ? "bg-primary" : "bg-charcoal-700"
            )}
        >
            <div className={cn(
                "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
                enabled ? "translate-x-4" : "translate-x-0.5"
            )} />
        </button>
    </div>
);

const ColorPicker = ({ 
    value, 
    onChange, 
    presets 
}: { 
    value: string; 
    onChange: (color: string) => void; 
    presets: { name: string; value: string }[];
}) => {
    const [showCustom, setShowCustom] = useState(false);

    return (
        <div className="space-y-2">
            {/* Current Color Preview */}
            <div className="flex items-center gap-2">
                <div 
                    className="w-full h-8 rounded border border-white/10 cursor-pointer transition-all hover:border-white/20"
                    style={{ backgroundColor: value }}
                    onClick={() => setShowCustom(!showCustom)}
                />
            </div>

            {/* Preset Colors */}
            <div className="flex flex-wrap gap-1.5">
                {presets.map(preset => (
                    <button
                        key={preset.value}
                        onClick={() => onChange(preset.value)}
                        className={cn(
                            "w-6 h-6 rounded border-2 transition-all hover:scale-110",
                            value === preset.value ? "border-white ring-1 ring-white/50" : "border-transparent"
                        )}
                        style={{ backgroundColor: preset.value }}
                        title={preset.name}
                    />
                ))}
            </div>

            {/* Custom Color Input */}
            {showCustom && (
                <div className="flex gap-2 animate-in slide-in-from-top-1">
                    <input
                        type="color"
                        value={value.startsWith('#') ? value : '#ffffff'}
                        onChange={(e) => onChange(e.target.value)}
                        className="w-8 h-8 rounded cursor-pointer bg-transparent border-0"
                    />
                    <input
                        type="text"
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        placeholder="#ffffff"
                        className="flex-1 bg-charcoal-800 border border-white/10 rounded text-xs px-2 py-1 text-foreground font-mono"
                    />
                </div>
            )}
        </div>
    );
};
