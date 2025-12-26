import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { LayoutGrid, Save, Search, GripVertical } from 'lucide-react';

interface AppsSidebarProps {
    className?: string;
}

export const AppsSidebar: React.FC<AppsSidebarProps> = ({ className }) => {
    const [activeTab, setActiveTab] = useState<'components' | 'apps'>('components');

    return (
        <div className={cn("h-full flex flex-col bg-charcoal-900 border-r border-border", className)}>
            {/* Header / Tabs */}
            <div className="flex items-center border-b border-border">
                <button
                    onClick={() => setActiveTab('components')}
                    className={cn(
                        "flex-1 py-3 text-xs font-medium transition-colors hover:text-foreground relative",
                        activeTab === 'components' ? "text-primary" : "text-muted-foreground"
                    )}
                >
                    Components
                    {activeTab === 'components' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />}
                </button>
                <div className="w-px h-4 bg-border" />
                <button
                    onClick={() => setActiveTab('apps')}
                    className={cn(
                        "flex-1 py-3 text-xs font-medium transition-colors hover:text-foreground relative",
                        activeTab === 'apps' ? "text-primary" : "text-muted-foreground"
                    )}
                >
                    My Apps
                    {activeTab === 'apps' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />}
                </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
                {activeTab === 'components' ? (
                    <ComponentLibrary />
                ) : (
                    <SavedAppsList />
                )}
            </div>
        </div>
    );
};

const COMPONENT_CATEGORIES = [
    {
        name: 'Basics',
        items: [
            { type: 'header', label: 'Header', description: 'Large title text', usage: 'Main dashboard title or section break' },
            { type: 'text', label: 'Text Block', description: 'Basic paragraph text', usage: 'Descriptions, notes, or instructions' },
            { type: 'markdown', label: 'Markdown', description: 'Rich text with markdown support', usage: 'Detailed reports and formatted notes' },
            { type: 'image', label: 'Image', description: 'External or uploaded image', usage: 'Company logos or infrastructure diagrams' },
            { type: 'spacer', label: 'Spacer', description: 'Horizontal/Vertical empty space', usage: 'Fine-tuning layout spacing' },
            { type: 'divider', label: 'Divider', description: 'Visual horizontal line', usage: 'Separating sections within a column' },
        ]
    },
    {
        name: 'Charts & Data',
        items: [
            { type: 'metric', label: 'Metric', description: 'Big number display', usage: 'Revenue, Profit, or KPI highlights' },
            { type: 'trend', label: 'Trend Metric', description: 'Number with sparkline', usage: 'Price movement or growth rates' },
            { type: 'line_chart', label: 'Line Chart', description: 'Time-series line graph', usage: 'Historical price or metric tracking' },
            { type: 'bar_chart', label: 'Bar Chart', description: 'Categorical comparison', usage: 'Quarterly revenue or segment counts' },
            { type: 'area_chart', label: 'Area Chart', description: 'Volume over time', usage: 'Market share or cumulative totals' },
            { type: 'pie_chart', label: 'Pie Chart', description: 'Proportional breakdown', usage: 'Portfolio allocation or revenue by sector' },
            { type: 'candlestick', label: 'Candlestick', description: 'Financial OHLC chart', usage: 'Stock price performance' },
            { type: 'scatter', label: 'Scatter Plot', description: 'Correlation mapping', usage: 'Risk vs Reward or P/E vs Growth' },
            { type: 'heatmap', label: 'Heatmap', description: 'Intensity grid', usage: 'Activity tracking or regional performance' },
            { type: 'table', label: 'Data Table', description: 'Structured grid', usage: 'Raw data listing or report details' },
        ]
    },
    {
        name: 'Finance',
        items: [
            { type: 'profile', label: 'Profile', description: 'Entity information', usage: 'Company overview, ticker, and sector' },
            { type: 'valuation', label: 'Valuation Gauge', description: 'Fair value vs Market price', usage: 'AlphaSpread style undervaluation' },
            { type: 'score_card', label: 'Score Card', description: 'Numerical health score', usage: 'Solvency, Health, or Credit Rating' },
            { type: 'grade_card', label: 'Grade Card', description: 'A-F rating display', usage: 'Profitability or Value grades' },
            { type: 'peer_table', label: 'Peer Table', description: 'Competitor comparison', usage: 'Market cap and P/E vs Peers' },
            { type: 'ratios', label: 'Ratios Grid', description: 'Key financial ratios', usage: 'P/E, PEG, ROE, Current Ratio' },
            { type: 'cash_flow', label: 'Cash Flow', description: 'Inflow/Outflow summary', usage: 'Operating, Investing, Financing flows' },
            { type: 'balance_sheet', label: 'Balance Sheet', description: 'Assets/Liabilities snapshot', usage: 'Debt levels and liquidity status' },
            { type: 'income_stmt', label: 'Income Stmt', description: 'P&L summary', usage: 'Revenue, EBITDA, Net Income' },
            { type: 'summary', label: 'Exec Summary', description: 'Rich summary grid', usage: 'High-level analytical takeaways' },
        ]
    },
    {
        name: 'Controls',
        items: [
            { type: 'button', label: 'Action Button', description: 'Trigger for agents/scripts', usage: 'Manual run or state update' },
            { type: 'input', label: 'Text Input', description: 'User input field', usage: 'Manual ticker override or query' },
            { type: 'select', label: 'Dropdown', description: 'Selection menu', usage: 'Choosing tickers or timeframes' },
            { type: 'date_picker', label: 'Date Picker', description: 'Calendar selection', usage: 'Setting report start/end dates' },
            { type: 'multi_select', label: 'Multi-Select', description: 'Multi-choice tag list', usage: 'Selecting multiple sectors or regions' },
            { type: 'toggle', label: 'Toggle Switch', description: 'Boolean on/off', usage: 'Enabling/Disabling features' },
            { type: 'slider', label: 'Range Slider', description: 'Numerical range', usage: 'Adjusting sensitivity or thresholds' },
            { type: 'checkbox', label: 'Checkbox', description: 'Selection flag', usage: 'Agreement or feature flags' },
        ]
    },
    {
        name: 'Dev & Feeds',
        items: [
            { type: 'feed', label: 'News Feed', description: 'Chronological events', usage: 'Latest SEC filings or news headlines' },
            { type: 'log', label: 'Log Stream', description: 'Live agent activity', usage: 'Debugging and monitoring execution' },
            { type: 'json', label: 'JSON Viewer', description: 'Tree view for data', usage: 'Inspecting raw API responses' },
            { type: 'code', label: 'Code Block', description: 'Syntax highlighted code', usage: 'Viewing snippets or configurations' },
            { type: 'terminal', label: 'Terminal', description: 'Interactive CLI', usage: 'Running low-level commands' },
            { type: 'chat', label: 'Chat Interface', description: 'Conversation window', usage: 'Direct interaction with agents' },
        ]
    }
];

const ComponentLibrary = () => {
    const [search, setSearch] = useState('');

    const filteredCategories = COMPONENT_CATEGORIES.map(cat => ({
        ...cat,
        items: cat.items.filter(item =>
            item.label.toLowerCase().includes(search.toLowerCase()) ||
            item.type.toLowerCase().includes(search.toLowerCase())
        )
    })).filter(cat => cat.items.length > 0);

    return (
        <div className="space-y-6">
            <div className="relative sticky top-0 z-10 bg-charcoal-900 pb-2">
                <Search className="absolute left-2.5 top-2.5 w-3 h-3 text-muted-foreground" />
                <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-background/50 border border-input rounded text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground"
                    placeholder="Search 40+ components..."
                />
            </div>

            {filteredCategories.map(category => (
                <div key={category.name} className="space-y-3">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold flex items-center justify-between">
                        <span>{category.name}</span>
                        <span className="opacity-40">{category.items.length}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        {category.items.map(item => (
                            <DraggableCard
                                key={item.type}
                                type={item.type}
                                label={item.label}
                                description={item.description}
                                usage={item.usage}
                                icon={<LayoutGrid className="w-3 h-3" />}
                            />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};

const SavedAppsList = () => {
    return (
        <div className="flex flex-col items-center justify-center h-48 text-muted-foreground text-center space-y-2 opacity-60">
            <Save className="w-8 h-8 opacity-20" />
            <p className="text-xs">No saved apps yet.</p>
        </div>
    );
};

// Draggable Item Wrapper
const DraggableCard = ({ type, label, description, usage, icon }: { type: string, label: string, description: string, usage: string, icon: React.ReactNode }) => {
    const { selectLibraryComponent, selectedLibraryComponent } = useAppStore();
    const isSelected = selectedLibraryComponent?.type === type;

    const handleDragStart = (e: React.DragEvent) => {
        // Essential for HTML5 DnD to work with some libraries
        e.dataTransfer.setData('application/json', JSON.stringify({ type, label }));
        e.dataTransfer.effectAllowed = 'copy';
    };

    return (
        <div
            draggable
            onDragStart={handleDragStart}
            onClick={() => selectLibraryComponent({ type, label, description, usage })}
            className={cn(
                "group relative flex flex-col items-center justify-center gap-2 p-2 rounded-lg border bg-card cursor-grab active:cursor-grabbing transition-all hover:scale-[1.02] shadow-sm overflow-hidden select-none",
                isSelected ? "border-primary ring-1 ring-primary/50 bg-primary/5" : "border-border hover:border-primary/50 hover:bg-accent/50"
            )}
        >
            {/* Tooltip Link (Hidden visually, but useful for screen readers/status) */}
            <div className="absolute inset-0 z-10" />

            {/* Mini Visual Preview */}
            <div className="w-full aspect-[1.4] bg-background/50 rounded border border-white/5 mb-1 relative overflow-hidden flex flex-col pointer-events-none">
                {/* Simulated Content based on type */}
                {type.includes('chart') && (
                    <div className="flex-1 flex items-end gap-0.5 p-1 opacity-40">
                        <div className="flex-1 bg-primary/40 rounded-t-[1px]" style={{ height: '40%' }} />
                        <div className="flex-1 bg-primary/60 rounded-t-[1px]" style={{ height: '70%' }} />
                        <div className="flex-1 bg-primary/30 rounded-t-[1px]" style={{ height: '50%' }} />
                        <div className="flex-1 bg-primary/80 rounded-t-[1px]" style={{ height: '90%' }} />
                    </div>
                )}
                {type === 'metric' && (
                    <div className="flex-1 flex flex-col justify-center items-start p-1 opacity-40">
                        <div className="w-2/3 h-0.5 bg-muted-foreground/20 mb-1 rounded-full" />
                        <div className="w-1/2 h-2 bg-foreground/20 rounded-full" />
                    </div>
                )}
                {type === 'table' && (
                    <div className="flex-1 flex flex-col p-1 opacity-40 gap-0.5">
                        <div className="w-full h-0.5 bg-foreground/20 rounded-full" />
                        <div className="w-full h-0.5 bg-muted-foreground/10 rounded-full" />
                        <div className="w-full h-0.5 bg-muted-foreground/10 rounded-full" />
                    </div>
                )}
                {/* Fallback for others */}
                {!['chart', 'metric', 'table'].some(k => type.includes(k)) && (
                    <div className="flex-1 flex items-center justify-center opacity-10">
                        {icon}
                    </div>
                )}
                <div className="absolute inset-0 border border-white/5" />
            </div>

            <div className="text-[9px] font-medium text-center text-foreground w-full truncate leading-none pointer-events-none">{label}</div>

            <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 text-muted-foreground z-20 pointer-events-none">
                <GripVertical className="w-3 h-3" />
            </div>
        </div>
    );
};
