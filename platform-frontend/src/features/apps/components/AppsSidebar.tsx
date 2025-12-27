import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { LayoutGrid, Save, Search, Trash2, TrendingUp, BarChart3, PieChart, CandlestickChart, Table2, User, Gauge, Medal, LineChart, FileText, Image, Minus, Hash, Calendar, ToggleLeft, Sliders, CheckSquare, Rss, Terminal, Braces, Code2, MessageSquare, Play, Type, AlignLeft, Plus, Palette, Star, Clock, Sparkles, RefreshCw, ArrowRight } from 'lucide-react';
import { SankeyCard } from './cards/SankeyCard';
import { ScatterCard } from './cards/ScatterCard';
import { HeatmapCard } from './cards/HeatmapCard';

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
            <div className="flex-1 overflow-y-auto p-3 space-y-5 custom-scrollbar">
                {activeTab === 'components' ? (
                    <ComponentLibrary />
                ) : (
                    <SavedAppsList />
                )}
            </div>
        </div>
    );
};

export const COMPONENT_CATEGORIES = [
    {
        name: 'Basics',
        items: [
            { type: 'header', label: 'Header', icon: Type, defaultW: 12, defaultH: 2 },
            { type: 'text', label: 'Text Block', icon: AlignLeft, defaultW: 4, defaultH: 4 },
            { type: 'markdown', label: 'Markdown', icon: FileText, defaultW: 4, defaultH: 4 },
            { type: 'image', label: 'Image', icon: Image, defaultW: 4, defaultH: 4 },
            { type: 'spacer', label: 'Spacer', icon: Hash, defaultW: 12, defaultH: 2 },
            { type: 'divider', label: 'Divider', icon: Minus, defaultW: 12, defaultH: 1 },
        ]
    },
    {
        name: 'Charts & Data',
        items: [
            { type: 'metric', label: 'Metric', icon: Hash, defaultW: 2, defaultH: 3 },
            { type: 'trend', label: 'Trend Metric', icon: TrendingUp, defaultW: 3, defaultH: 3 },
            { type: 'line_chart', label: 'Line Chart', icon: LineChart, defaultW: 6, defaultH: 8 },
            { type: 'bar_chart', label: 'Bar Chart', icon: BarChart3, defaultW: 6, defaultH: 6 },
            { type: 'area_chart', label: 'Area Chart', icon: LineChart, defaultW: 6, defaultH: 6 },
            { type: 'pie_chart', label: 'Pie Chart', icon: PieChart, defaultW: 6, defaultH: 6 },
            { type: 'sankey', label: 'Sankey Chart', icon: ArrowRight, defaultW: 4, defaultH: 8 },
            { type: 'scatter', label: 'Scatter Plot', icon: BarChart3, defaultW: 6, defaultH: 6 },
            { type: 'heatmap', label: 'Heatmap', icon: LayoutGrid, defaultW: 6, defaultH: 6 },
            { type: 'table', label: 'Data Table', icon: Table2, defaultW: 6, defaultH: 5 },
        ]
    },
    {
        name: 'Finance',
        items: [
            { type: 'profile', label: 'Profile', icon: User, defaultW: 4, defaultH: 4 }, // Adjusted based on common usage
            { type: 'valuation', label: 'Valuation Gauge', icon: Gauge, defaultW: 6, defaultH: 4 },
            { type: 'score_card', label: 'Score Card', icon: Medal, defaultW: 3, defaultH: 3 },
            { type: 'grade_card', label: 'Grade Card', icon: Medal, defaultW: 3, defaultH: 3 },
            { type: 'peer_table', label: 'Peer Table', icon: Table2, defaultW: 6, defaultH: 8 },
            { type: 'ratios', label: 'Ratios Grid', icon: LayoutGrid, defaultW: 6, defaultH: 5 },
            { type: 'cash_flow', label: 'Cash Flow', icon: TrendingUp, defaultW: 6, defaultH: 5 },
            { type: 'balance_sheet', label: 'Balance Sheet', icon: Table2, defaultW: 6, defaultH: 5 },
            { type: 'income_stmt', label: 'Income Stmt', icon: FileText, defaultW: 6, defaultH: 5 },
            { type: 'summary', label: 'Exec Summary', icon: FileText, defaultW: 6, defaultH: 5 },
        ]
    },
    {
        name: 'Controls',
        items: [
            { type: 'button', label: 'Action Button', icon: Play, defaultW: 3, defaultH: 2 },
            { type: 'input', label: 'Text Input', icon: Type, defaultW: 3, defaultH: 2 },
            { type: 'textarea', label: 'Text Area', icon: AlignLeft, defaultW: 3, defaultH: 3 }, // Textarea needs more height
            { type: 'number_input', label: 'Number Input', icon: Hash, defaultW: 3, defaultH: 2 },
            { type: 'select', label: 'Dropdown', icon: CheckSquare, defaultW: 3, defaultH: 2 },
            { type: 'checkbox', label: 'Checkbox', icon: CheckSquare, defaultW: 3, defaultH: 1 },
            { type: 'switch', label: 'Switch', icon: ToggleLeft, defaultW: 3, defaultH: 1 },
            { type: 'radio_group', label: 'Radio Group', icon: CheckSquare, defaultW: 3, defaultH: 3 },
            { type: 'slider', label: 'Slider', icon: Sliders, defaultW: 3, defaultH: 2 },
            { type: 'date_picker', label: 'Date Picker', icon: Calendar, defaultW: 4, defaultH: 2 },
            { type: 'time_picker', label: 'Time Picker', icon: Clock, defaultW: 3, defaultH: 2 },
            { type: 'tags_input', label: 'Tags Input', icon: Type, defaultW: 4, defaultH: 2 },
            { type: 'color_picker', label: 'Color Picker', icon: Palette, defaultW: 3, defaultH: 2 },
            { type: 'rating', label: 'Rating', icon: Star, defaultW: 3, defaultH: 2 },
        ]
    },
    {
        name: 'Dev & Feed',
        items: [
            { type: 'feed', label: 'RSS / JSON Feed', icon: Rss, defaultW: 6, defaultH: 6 },
            { type: 'log', label: 'Log Stream', icon: Terminal, defaultW: 6, defaultH: 8 },
            { type: 'json', label: 'JSON Viewer', icon: Braces, defaultW: 6, defaultH: 8 },
            { type: 'code', label: 'Code Block', icon: Code2, defaultW: 6, defaultH: 8 },
        ]
    },
    {
        name: 'Blocks',
        items: [
            { type: 'stats_trending', label: 'Stats: Trending', icon: TrendingUp, defaultW: 6, defaultH: 6 },
            { type: 'stats_grid', label: 'Stats: Grid', icon: LayoutGrid, defaultW: 8, defaultH: 5 },
            { type: 'stats_status', label: 'Stats: Status', icon: LayoutGrid, defaultW: 8, defaultH: 5 },
            { type: 'stats_links', label: 'Stats: Links', icon: LayoutGrid, defaultW: 4, defaultH: 6 },
            { type: 'simple_table', label: 'Simple Table', icon: Table2, defaultW: 6, defaultH: 5 },
            { type: 'stats_01', label: 'Stats 01', icon: TrendingUp, defaultW: 8, defaultH: 4 },
            { type: 'usage_stats', label: 'Usage Stats', icon: BarChart3, defaultW: 6, defaultH: 6 },
            { type: 'storage_card', label: 'Storage Card', icon: PieChart, defaultW: 4, defaultH: 4 },
            { type: 'accordion_table', label: 'Accordion Table', icon: Table2, defaultW: 6, defaultH: 8 },
        ]
    }
];




const ComponentLibrary = () => {
    const [search, setSearch] = useState('');
    // Start with only 'Basics' expanded
    const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
        'Basics': true,
    });

    const toggleCategory = (categoryName: string) => {
        setExpandedCategories(prev => {
            const isCurrentlyExpanded = prev[categoryName];
            // Accordion behavior: collapse all others, toggle current
            if (isCurrentlyExpanded) {
                return { ...prev, [categoryName]: false };
            } else {
                // Collapse all, expand only this one
                return { [categoryName]: true };
            }
        });
    };

    const filteredCategories = COMPONENT_CATEGORIES.map(cat => ({
        ...cat,
        items: cat.items.filter(item =>
            item.label.toLowerCase().includes(search.toLowerCase()) ||
            item.type.toLowerCase().includes(search.toLowerCase())
        )
    })).filter(cat => cat.items.length > 0);

    // When searching, expand all categories
    const isSearching = search.length > 0;

    return (
        <div className="space-y-2">
            <div className="relative sticky top-0 z-10 bg-charcoal-900 pb-2">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-charcoal-950 border border-white/10 rounded-lg text-xs pl-8 pr-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 focus:border-neon-yellow/30 text-foreground placeholder:text-gray-600 transition-all"
                    placeholder="Search 40+ components..."
                />
            </div>

            {filteredCategories.map(category => {
                const isExpanded = isSearching || expandedCategories[category.name];
                return (
                    <div key={category.name} className="border border-white/5 rounded-lg overflow-hidden bg-charcoal-950/50">
                        <button
                            onClick={() => toggleCategory(category.name)}
                            className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 transition-colors"
                        >
                            <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold">
                                {category.name}
                            </span>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-gray-600">{category.items.length}</span>
                                <svg
                                    className={`w-3 h-3 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                            </div>
                        </button>
                        {isExpanded && (
                            <div className="grid grid-cols-2 gap-2 p-2 pt-0">
                                {category.items.map(item => (
                                    <ComponentPreviewCard
                                        key={item.type}
                                        type={item.type}
                                        label={item.label}
                                        icon={item.icon}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};


// Canva-style Preview Card with actual visual representation
const ComponentPreviewCard = ({ type, label, icon: Icon }: { type: string, label: string, icon: any }) => {
    const { selectLibraryComponent, selectedLibraryComponent } = useAppStore();
    const isSelected = selectedLibraryComponent?.type === type;

    const handleDragStart = (e: React.DragEvent) => {
        e.dataTransfer.setData('application/json', JSON.stringify({ type, label }));
        e.dataTransfer.effectAllowed = 'copy';
    };

    // Render a mini visual preview based on component type
    const renderPreview = () => {
        switch (type) {
            // BASICS
            case 'header':
                return (
                    <div className="w-full h-full flex flex-col justify-center p-3">
                        <div className="text-[11px] font-bold text-white">Add a heading</div>
                    </div>
                );
            case 'text':
                return (
                    <div className="w-full h-full flex flex-col justify-center p-3 gap-1">
                        <div className="h-1 w-full bg-gray-600 rounded-full" />
                        <div className="h-1 w-4/5 bg-gray-700 rounded-full" />
                        <div className="h-1 w-3/5 bg-gray-700 rounded-full" />
                    </div>
                );
            case 'markdown':
                return (
                    <div className="w-full h-full flex flex-col p-3 gap-1.5">
                        <div className="text-[9px] font-bold text-neon-yellow"># Heading</div>
                        <div className="flex items-center gap-1">
                            <div className="w-1 h-1 rounded-full bg-gray-500" />
                            <div className="h-0.5 w-12 bg-gray-600 rounded-full" />
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-1 h-1 rounded-full bg-gray-500" />
                            <div className="h-0.5 w-10 bg-gray-600 rounded-full" />
                        </div>
                    </div>
                );
            case 'image':
                return (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900">
                        <div className="w-8 h-6 border border-dashed border-gray-600 rounded flex items-center justify-center">
                            <Image className="w-3 h-3 text-gray-600" />
                        </div>
                    </div>
                );
            case 'spacer':
                return (
                    <div className="w-full h-full flex items-center justify-center">
                        <div className="w-full h-4 border border-dashed border-gray-700 rounded flex items-center justify-center">
                            <div className="text-[8px] text-gray-600">SPACE</div>
                        </div>
                    </div>
                );
            case 'divider':
                return (
                    <div className="w-full h-full flex items-center justify-center px-4">
                        <div className="w-full h-px bg-gradient-to-r from-transparent via-gray-500 to-transparent" />
                    </div>
                );

            // CHARTS
            case 'metric':
                return (
                    <div className="w-full h-full flex flex-col justify-center p-3">
                        <div className="text-[8px] text-gray-500 uppercase">Revenue</div>
                        <div className="text-sm font-black text-white">$2.4M</div>
                        <div className="flex items-center gap-0.5 text-green-400">
                            <TrendingUp className="w-2 h-2" />
                            <span className="text-[8px]">+12.5%</span>
                        </div>
                    </div>
                );
            case 'trend':
                return (
                    <div className="w-full h-full flex flex-col p-3">
                        <div className="text-[8px] text-gray-500">PRICE</div>
                        <div className="text-[10px] font-bold text-white">$145.20</div>
                        <div className="flex-1 flex items-end">
                            <svg viewBox="0 0 40 12" className="w-full h-3">
                                <path d="M0 10 Q10 8 15 6 T25 4 T40 2" fill="none" stroke="#4ade80" strokeWidth="1.5" />
                            </svg>
                        </div>
                    </div>
                );
            case 'line_chart':
                return (
                    <div className="w-full h-full flex items-end p-2 gap-0.5">
                        <svg viewBox="0 0 50 25" className="w-full h-full">
                            <path d="M0 20 Q10 15 20 18 T35 8 T50 5" fill="none" stroke="#eaff00" strokeWidth="2" />
                            <path d="M0 20 Q10 15 20 18 T35 8 T50 5 V25 H0 Z" fill="url(#lineGrad)" opacity="0.2" />
                            <defs>
                                <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#eaff00" />
                                    <stop offset="100%" stopColor="transparent" />
                                </linearGradient>
                            </defs>
                        </svg>
                    </div>
                );
            case 'bar_chart':
                return (
                    <div className="w-full h-full flex items-end justify-center gap-1 p-2 pb-3">
                        {[40, 70, 35, 90, 55].map((h, i) => (
                            <div key={i} className="w-2 bg-neon-yellow/80 rounded-t-sm" style={{ height: `${h}%` }} />
                        ))}
                    </div>
                );
            case 'area_chart':
                return (
                    <div className="w-full h-full flex items-end p-2">
                        <svg viewBox="0 0 50 25" className="w-full h-full">
                            <path d="M0 25 L0 18 Q12 12 25 15 T50 8 V25 Z" fill="#eaff00" opacity="0.3" />
                            <path d="M0 18 Q12 12 25 15 T50 8" fill="none" stroke="#eaff00" strokeWidth="1.5" />
                        </svg>
                    </div>
                );
            case 'pie_chart':
                return (
                    <div className="w-full h-full flex items-center justify-center p-2">
                        <svg viewBox="0 0 32 32" className="w-10 h-10">
                            <circle cx="16" cy="16" r="14" fill="none" stroke="#374151" strokeWidth="4" />
                            <circle cx="16" cy="16" r="14" fill="none" stroke="#eaff00" strokeWidth="4" strokeDasharray="44 88" transform="rotate(-90 16 16)" />
                            <circle cx="16" cy="16" r="14" fill="none" stroke="#4ade80" strokeWidth="4" strokeDasharray="22 88" strokeDashoffset="-44" transform="rotate(-90 16 16)" />
                        </svg>
                    </div>
                );
            case 'candlestick':
                return (
                    <div className="w-full h-full flex items-end justify-center gap-1.5 p-2 pb-3">
                        {[
                            { o: 60, c: 40, h: 70, l: 30, up: false },
                            { o: 40, c: 55, h: 65, l: 35, up: true },
                            { o: 55, c: 45, h: 60, l: 40, up: false },
                            { o: 45, c: 70, h: 80, l: 40, up: true },
                        ].map((candle, i) => (
                            <div key={i} className="relative w-2 h-full flex flex-col items-center">
                                <div className="absolute w-px bg-gray-500" style={{ top: `${100 - candle.h}%`, bottom: `${candle.l}%` }} />
                                <div
                                    className={cn("absolute w-1.5 rounded-sm", candle.up ? "bg-green-500" : "bg-red-500")}
                                    style={{
                                        top: `${100 - Math.max(candle.o, candle.c)}%`,
                                        bottom: `${Math.min(candle.o, candle.c)}%`
                                    }}
                                />
                            </div>
                        ))}
                    </div>
                );
            case 'table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="flex gap-1">
                            <div className="flex-1 h-1.5 bg-gray-600 rounded-sm" />
                            <div className="flex-1 h-1.5 bg-gray-600 rounded-sm" />
                            <div className="flex-1 h-1.5 bg-gray-600 rounded-sm" />
                        </div>
                        {[0, 1, 2].map(i => (
                            <div key={i} className="flex gap-1">
                                <div className="flex-1 h-1 bg-gray-700/50 rounded-sm" />
                                <div className="flex-1 h-1 bg-gray-700/50 rounded-sm" />
                                <div className="flex-1 h-1 bg-gray-700/50 rounded-sm" />
                            </div>
                        ))}
                    </div>
                );

            // FINANCE
            case 'profile':
                return (
                    <div className="w-full h-full flex items-center gap-2 p-3">
                        <div className="w-6 h-6 rounded bg-neon-yellow/20 flex items-center justify-center text-[9px] font-black text-neon-yellow">G</div>
                        <div className="flex flex-col">
                            <div className="text-[9px] font-bold text-white">Alphabet</div>
                            <div className="text-[7px] text-gray-500">GOOGL</div>
                        </div>
                    </div>
                );
            case 'valuation':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-gray-500">FAIR VALUE</div>
                        <div className="flex items-center gap-1">
                            <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                                <div className="h-full w-3/5 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded-full" />
                            </div>
                        </div>
                        <div className="flex justify-between text-[7px]">
                            <span className="text-white">$145</span>
                            <span className="text-green-400">$180</span>
                        </div>
                    </div>
                );
            case 'score_card':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2">
                        <div className="text-xl font-black text-neon-yellow">78</div>
                        <div className="text-[7px] text-green-400">Healthy</div>
                    </div>
                );
            case 'grade_card':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2">
                        <div className="text-xl font-black text-neon-yellow">A-</div>
                        <div className="text-[7px] text-gray-500">Top Tier</div>
                    </div>
                );
            case 'peer_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex gap-1 text-[6px] text-gray-500">
                            <span className="flex-1">Ticker</span>
                            <span className="flex-1">MCap</span>
                            <span className="flex-1">P/E</span>
                        </div>
                        {['AAPL', 'MSFT', 'GOOGL'].map(t => (
                            <div key={t} className="flex gap-1 text-[6px] text-gray-400">
                                <span className="flex-1">{t}</span>
                                <span className="flex-1">2.5T</span>
                                <span className="flex-1">28</span>
                            </div>
                        ))}
                    </div>
                );

            case 'ratios':
                return (
                    <div className="w-full h-full grid grid-cols-2 gap-1 p-2">
                        {[
                            { n: 'P/E', v: '24.5', s: 'text-yellow-400' },
                            { n: 'PEG', v: '1.1', s: 'text-green-400' },
                            { n: 'ROE', v: '22%', s: 'text-green-400' },
                            { n: 'D/E', v: '0.45', s: 'text-green-400' }
                        ].map((r, i) => (
                            <div key={i} className="bg-charcoal-800/50 rounded p-1 flex flex-col items-center">
                                <div className="text-[6px] text-gray-500">{r.n}</div>
                                <div className={`text-[9px] font-bold ${r.s}`}>{r.v}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'cash_flow':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5 justify-center">
                        {[
                            { n: 'Operating', v: '+$2.4B', pos: true },
                            { n: 'Investing', v: '-$800M', pos: false },
                            { n: 'Financing', v: '-$600M', pos: false }
                        ].map((c, i) => (
                            <div key={i} className="flex justify-between items-center">
                                <span className="text-[7px] text-gray-500">{c.n}</span>
                                <span className={`text-[8px] font-bold ${c.pos ? 'text-green-400' : 'text-red-400'}`}>{c.v}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'balance_sheet':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1 justify-center">
                        <div className="flex items-center gap-1">
                            <div className="flex-1 h-3 bg-green-500/30 rounded-sm flex items-center justify-center text-[6px] text-green-400">Assets</div>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="flex-[0.6] h-3 bg-red-500/30 rounded-sm flex items-center justify-center text-[6px] text-red-400">Liab</div>
                            <div className="flex-[0.4] h-3 bg-blue-500/30 rounded-sm flex items-center justify-center text-[6px] text-blue-400">Equity</div>
                        </div>
                    </div>
                );

            case 'income_stmt':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5 justify-center">
                        {[
                            { n: 'Revenue', v: '$100M', w: '100%' },
                            { n: 'COGS', v: '-$40M', w: '60%' },
                            { n: 'Net Income', v: '$25M', w: '25%' }
                        ].map((r, i) => (
                            <div key={i} className="flex flex-col gap-0.5">
                                <div className="flex justify-between text-[6px]">
                                    <span className="text-gray-500">{r.n}</span>
                                    <span className="text-white">{r.v}</span>
                                </div>
                                <div className="h-1 bg-charcoal-700 rounded-full overflow-hidden">
                                    <div className="h-full bg-neon-yellow/70 rounded-full" style={{ width: r.w }} />
                                </div>
                            </div>
                        ))}
                    </div>
                );

            case 'summary':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1 justify-center">
                        <div className="text-[6px] text-gray-400 leading-tight">Strong fundamentals with healthy growth...</div>
                        <div className="flex flex-col gap-0.5">
                            {['✓ Revenue +15% YoY', '✓ Market leader', '✓ Strong cash'].map((p, i) => (
                                <div key={i} className="text-[6px] text-green-400">{p}</div>
                            ))}
                        </div>
                    </div>
                );

            // CONTROLS
            case 'button':
                return (
                    <div className="w-full h-full flex items-center justify-center p-3">
                        <div className="px-3 py-1 bg-neon-yellow text-charcoal-900 text-[8px] font-bold rounded">
                            Run Analysis
                        </div>
                    </div>
                );
            case 'input':
                return (
                    <div className="w-full h-full flex items-center justify-center p-3">
                        <div className="w-full h-5 bg-charcoal-950 border border-gray-700 rounded px-1.5 flex items-center">
                            <span className="text-[7px] text-gray-600">Enter ticker...</span>
                        </div>
                    </div>
                );
            case 'select':
                return (
                    <div className="w-full h-full flex items-center justify-center p-3">
                        <div className="w-full h-5 bg-charcoal-950 border border-gray-700 rounded px-1.5 flex items-center justify-between">
                            <span className="text-[7px] text-gray-400">Select...</span>
                            <span className="text-[7px] text-gray-600">▼</span>
                        </div>
                    </div>
                );
            case 'date_picker':
                return (
                    <div className="w-full h-full flex items-center justify-center p-3">
                        <div className="w-full h-5 bg-charcoal-950 border border-gray-700 rounded px-1.5 flex items-center gap-1">
                            <Calendar className="w-2 h-2 text-gray-600" />
                            <span className="text-[7px] text-gray-400">Dec 26, 2025</span>
                        </div>
                    </div>
                );

            // DEV & FEEDS
            case 'feed':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        {[0, 1].map(i => (
                            <div key={i} className="flex gap-1 items-start">
                                <div className="w-1 h-1 rounded-full bg-neon-yellow mt-0.5" />
                                <div className="flex-1">
                                    <div className="h-1 w-full bg-gray-600 rounded-full mb-0.5" />
                                    <div className="h-0.5 w-3/4 bg-gray-700 rounded-full" />
                                </div>
                            </div>
                        ))}
                    </div>
                );
            case 'log':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5 ">
                        <div className="text-[6px] text-green-400">[INFO] Starting...</div>
                        <div className="text-[6px] text-gray-500">[DEBUG] Init</div>
                        <div className="text-[6px] text-neon-yellow">[WARN] Check</div>
                    </div>
                );
            case 'json':
                return (
                    <div className="w-full h-full flex flex-col p-2  text-[6px]">
                        <span className="text-gray-500">{"{"}</span>
                        <span className="pl-1"><span className="text-neon-yellow">"ticker"</span>: <span className="text-green-400">"GOOGL"</span></span>
                        <span className="text-gray-500">{"}"}</span>
                    </div>
                );
            case 'code':
                return (
                    <div className="w-full h-full flex flex-col p-2  text-[6px]">
                        <span className="text-purple-400">def</span><span className="text-white"> analyze():</span>
                        <span className="pl-2 text-gray-500"># logic here</span>
                        <span className="pl-2 text-blue-400">return</span><span className="text-white"> data</span>
                    </div>
                );

            // Sankey Chart Preview - Use actual component
            case 'sankey':
                return (
                    <div className="w-full h-full overflow-hidden pointer-events-none">
                        <div className="w-[300px] h-[200px] origin-top-left" style={{ transform: 'scale(0.35)' }}>
                            <SankeyCard title="" config={{ showLegend: false }} />
                        </div>
                    </div>
                );

            // Scatter Plot Preview - Use actual component
            case 'scatter':
                return (
                    <div className="w-full h-full overflow-hidden pointer-events-none">
                        <div className="w-[300px] h-[200px] origin-top-left" style={{ transform: 'scale(0.35)' }}>
                            <ScatterCard title="" config={{ showLegend: false, showAxisLabels: false }} />
                        </div>
                    </div>
                );

            // Heatmap Preview - Use actual component
            case 'heatmap':
                return (
                    <div className="w-full h-full overflow-hidden pointer-events-none">
                        <div className="w-[300px] h-[200px] origin-top-left" style={{ transform: 'scale(0.35)' }}>
                            <HeatmapCard title="" config={{ showLegend: false, showAxisLabels: false }} />
                        </div>
                    </div>
                );

            // Blocks components
            case 'stats_trending':
                return (
                    <div className="w-full h-full flex flex-col gap-1 p-2 justify-center">
                        {[
                            { label: 'Profit', value: '$287K', change: '+8.3%', positive: true },
                            { label: 'Pending', value: '$173K', change: '+2.8%', positive: true },
                        ].map((stat, i) => (
                            <div key={i} className="flex items-center justify-between">
                                <div className="text-[7px] text-gray-500">{stat.label}</div>
                                <div className="flex items-center gap-1">
                                    <span className="text-[8px] font-bold text-white">{stat.value}</span>
                                    <span className={`text-[6px] ${stat.positive ? 'text-green-400' : 'text-red-400'}`}>{stat.change}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                );

            case 'stats_grid':
                return (
                    <div className="w-full h-full grid grid-cols-2 gap-1 p-2">
                        {[{ v: '10.4K', c: '-12%', neg: true }, { v: '56.1%', c: '+1.8%' }, { v: '5.2m', c: '+19%' }, { v: '3.2%', c: '-2.4%', neg: true }].map((s, i) => (
                            <div key={i} className="bg-charcoal-800/50 rounded p-1 flex flex-col items-center">
                                <div className="text-[9px] font-bold text-white">{s.v}</div>
                                <div className={`text-[6px] ${s.neg ? 'text-red-400' : 'text-green-400'}`}>{s.c}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'stats_status':
                return (
                    <div className="w-full h-full grid grid-cols-2 gap-1 p-2">
                        {[{ v: '99.9%', s: 'success' }, { v: '142ms', s: 'success' }, { v: '0.4%', s: 'warning' }, { v: '2,847', s: 'info' }].map((s, i) => (
                            <div key={i} className="bg-charcoal-800/50 rounded p-1 flex items-center gap-1">
                                <div className={`w-1.5 h-1.5 rounded-full ${s.s === 'success' ? 'bg-green-500' : s.s === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'}`} />
                                <div className="text-[8px] font-bold text-white">{s.v}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'stats_links':
                return (
                    <div className="w-full h-full flex flex-col gap-1 p-2 justify-center">
                        {['Projects: 12', 'Issues: 47', 'PRs: 8'].map((item, i) => (
                            <div key={i} className="flex items-center justify-between text-[7px] text-gray-400 hover:text-white">
                                <span>{item.split(':')[0]}</span>
                                <span className="text-white font-bold">{item.split(':')[1]}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'simple_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex gap-1 text-[6px] text-gray-500 border-b border-white/10 pb-0.5">
                            <span className="flex-1">Task</span><span className="flex-1">Status</span>
                        </div>
                        {[['Auth', '🟡'], ['UI', '🟢'], ['API', '⚪']].map(([t, s], i) => (
                            <div key={i} className="flex gap-1 text-[6px] text-gray-400">
                                <span className="flex-1">{t}</span><span className="flex-1">{s}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'stats_01':
                return (
                    <div className="w-full h-full grid grid-cols-2 gap-1 p-2">
                        {[{ v: '$287K', c: '+8%', pos: true }, { v: '$9.4K', c: '-12%' }, { v: '$173K', c: '+2%', pos: true }, { v: '$52K', c: '-5%' }].map((s, i) => (
                            <div key={i} className="flex flex-col items-center justify-center">
                                <div className="text-[9px] font-bold text-white">{s.v}</div>
                                <div className={`text-[6px] ${s.pos ? 'text-green-400' : 'text-red-400'}`}>{s.c}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'usage_stats':
                return (
                    <div className="w-full h-full flex flex-col gap-1 p-2 justify-center">
                        {[{ n: 'API', p: 35 }, { n: 'Storage', p: 30 }, { n: 'Users', p: 48 }].map((u, i) => (
                            <div key={i} className="flex flex-col gap-0.5">
                                <div className="flex justify-between text-[6px]">
                                    <span className="text-gray-500">{u.n}</span>
                                    <span className="text-gray-400">{u.p}%</span>
                                </div>
                                <div className="h-1 bg-charcoal-700 rounded-full overflow-hidden">
                                    <div className="h-full bg-neon-yellow rounded-full" style={{ width: `${u.p}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                );

            case 'storage_card':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2 gap-1">
                        <svg viewBox="0 0 36 36" className="w-10 h-10">
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#374151" strokeWidth="4" />
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#3b82f6" strokeWidth="4" strokeDasharray="30 58" transform="rotate(-90 18 18)" />
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#10b981" strokeWidth="4" strokeDasharray="20 68" strokeDashoffset="-30" transform="rotate(-90 18 18)" />
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#f59e0b" strokeWidth="4" strokeDasharray="15 73" strokeDashoffset="-50" transform="rotate(-90 18 18)" />
                        </svg>
                        <div className="text-[7px] text-gray-500">8.3 / 15 GB</div>
                    </div>
                );

            case 'accordion_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex items-center gap-1 text-[6px] text-white bg-charcoal-800/50 rounded px-1 py-0.5">
                            <span className="text-gray-500">▶</span>
                            <span>Project A</span>
                            <span className="ml-auto text-neon-yellow">$45K</span>
                        </div>
                        <div className="flex items-center gap-1 text-[6px] text-gray-400 pl-2">
                            <span>└ Frontend</span>
                            <span className="ml-auto">$15K</span>
                        </div>
                        <div className="flex items-center gap-1 text-[6px] text-white bg-charcoal-800/50 rounded px-1 py-0.5">
                            <span className="text-gray-500">▶</span>
                            <span>Campaign</span>
                            <span className="ml-auto text-neon-yellow">$28K</span>
                        </div>
                    </div>
                );

            default:
                return (
                    <div className="w-full h-full flex items-center justify-center">
                        <Icon className="w-5 h-5 text-gray-600" />
                    </div>
                );
        }
    };

    return (
        <div
            draggable
            onDragStart={handleDragStart}
            onClick={() => selectLibraryComponent({ type, label, description: '', usage: '' })}
            className={cn(
                "group relative flex flex-col rounded-xl border-2 cursor-grab active:cursor-grabbing transition-all duration-300 overflow-hidden select-none shadow-lg",
                // Match Explorer node styling
                isSelected
                    ? "bg-charcoal-800 border-neon-yellow ring-4 ring-neon-yellow/20 scale-[1.02]"
                    : "bg-charcoal-900/90 border-white/10 hover:border-white/30 hover:scale-[1.02]"
            )}
        >
            {/* Preview Area - matches the actual card appearance with animation */}
            <div className="aspect-[2] w-full overflow-hidden bg-charcoal-950/50 group-hover:bg-charcoal-900/80 transition-colors">
                <div className="w-full h-full animate-in fade-in slide-in-from-bottom-1 duration-500">
                    {renderPreview()}
                </div>
            </div>

            {/* Label */}
            <div className={cn(
                "px-2 py-1 text-[10px] font-medium text-center border-t transition-colors",
                isSelected ? "bg-charcoal-800 border-neon-yellow/20 text-neon-yellow" : "bg-charcoal-900 border-white/5 text-gray-400"
            )}>
                {label}
            </div>
        </div>
    );
};

const SavedAppsList = () => {
    const { savedApps, saveApp, loadApp, deleteApp, editingAppId, createNewApp, fetchApps } = useAppStore();
    const [name, setName] = useState('');

    // Auto-refresh apps every 5 seconds (Pseudo Hot-Loading)
    useEffect(() => {
        // Initial fetch
        fetchApps();

        const interval = setInterval(() => {
            fetchApps();
        }, 5000);
        return () => clearInterval(interval);
    }, [fetchApps]);

    const activeApp = savedApps.find(a => a.id === editingAppId);

    const handleSave = () => {
        if (!name.trim()) return;
        saveApp(name);
        setName('');
    };

    return (
        <div className="space-y-6">
            {/* Create New / Header */}
            <div className="flex items-center justify-between px-1">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 font-bold">
                    My Dashboards
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => fetchApps()}
                        className="p-1 text-gray-400 hover:text-white transition-colors"
                        title="Refresh List"
                    >
                        <RefreshCw className="w-3 h-3" />
                    </button>
                    <button
                        onClick={() => useAppStore.getState().loadShowcaseApp()}
                        className="p-1 text-purple-400 hover:text-white transition-colors"
                        title="Generate Showcase App"
                    >
                        <Sparkles className="w-3 h-3" />
                    </button>
                    <button
                        onClick={createNewApp}
                        className="flex items-center gap-1 text-[10px] font-bold text-neon-yellow hover:text-white transition-colors"
                    >
                        <Plus className="w-3 h-3" />
                        NEW APP
                    </button>
                </div>
            </div>

            {/* Save Controls - Only shown when starting fresh or renaming */}
            {!activeApp && (
                <div className="flex flex-col gap-2 p-3 bg-charcoal-800/50 rounded-xl border border-white/5">
                    <label className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">Save New App</label>
                    <div className="flex gap-2">
                        <input
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="Dashboard Name..."
                            className="flex-1 bg-charcoal-950 border border-white/10 rounded-lg text-xs px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-gray-600"
                        />
                        <button
                            onClick={handleSave}
                            disabled={!name.trim()}
                            className="p-2 bg-neon-yellow/20 hover:bg-neon-yellow/30 text-neon-yellow rounded-lg border border-neon-yellow/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            title="Save App"
                        >
                            <Save className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}

            {/* List */}
            <div className="space-y-3">
                {savedApps.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground text-center space-y-2 opacity-60">
                        <LayoutGrid className="w-8 h-8 opacity-20" />
                        <p className="text-xs">No saved apps yet.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 gap-2">
                        {savedApps.map(app => {
                            const isActive = app.id === editingAppId;
                            return (
                                <div
                                    key={app.id}
                                    className={cn(
                                        "group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all border-2",
                                        isActive
                                            ? "bg-charcoal-800 border-neon-yellow shadow-[0_0_15px_rgba(234,255,0,0.1)] scale-[1.02]"
                                            : "bg-charcoal-900/90 border-white/10 hover:border-white/30"
                                    )}
                                    onClick={() => loadApp(app.id)}
                                >
                                    <div className="flex-1 min-w-0">
                                        <div className={cn(
                                            "text-xs font-bold truncate",
                                            isActive ? "text-neon-yellow" : "text-foreground"
                                        )}>
                                            {app.name}
                                        </div>
                                        <div className="text-[10px] text-gray-500">
                                            {isActive ? "Currently Editing" : new Date(app.lastModified).toLocaleDateString()}
                                        </div>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); deleteApp(app.id); }}
                                        className={cn(
                                            "p-1.5 hover:bg-red-500/10 text-gray-600 hover:text-red-400 rounded-lg transition-all",
                                            isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                                        )}
                                        title="Delete App"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
