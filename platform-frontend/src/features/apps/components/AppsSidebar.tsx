// SET CARD DEFAULT WIDTH AND HEIGHT IN THIS FILE

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import type { SavedApp } from '@/store';
import { LayoutGrid, Save, Search, Trash2, TrendingUp, BarChart3, PieChart, CandlestickChart, Table2, User, Gauge, Medal, LineChart, FileText, Image, Minus, Hash, Calendar, ToggleLeft, Sliders, CheckSquare, Rss, Terminal, Braces, Code2, MessageSquare, Play, Type, AlignLeft, Plus, Palette, Star, Clock, RefreshCw, ArrowRight, Eye, Edit, Upload, Share2, FormInput, Bot, ListTodo, Package, FolderKanban } from 'lucide-react';
import { SankeyCard } from './cards/SankeyCard';
import { ScatterCard } from './cards/ScatterCard';
import { HeatmapCard } from './cards/HeatmapCard';


interface AppsSidebarProps {
    className?: string;
}

export const AppsSidebar: React.FC<AppsSidebarProps> = ({ className }) => {
    const { savedApps, appsSidebarTab, setAppsSidebarTab } = useAppStore();
    const activeTab = appsSidebarTab;
    const setActiveTab = setAppsSidebarTab;

    return (
        <div className={cn("h-full flex flex-col bg-card text-foreground", className)}>

            {/* Tabs */}
            <div className="flex items-center border-b border-border/50 bg-muted/20 pt-1">
                <button
                    onClick={() => setActiveTab('apps')}
                    className={cn(
                        "flex-1 py-2.5 text-[10px] font-bold uppercase tracking-widest transition-colors hover:text-foreground relative",
                        activeTab === 'apps' ? "text-neon-yellow" : "text-muted-foreground/70"
                    )}
                >
                    My Apps
                    {activeTab === 'apps' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-neon-yellow" />}
                </button>
                <div className="w-px h-4 bg-border" />
                <button
                    onClick={() => setActiveTab('components')}
                    className={cn(
                        "flex-1 py-2.5 text-[10px] font-bold uppercase tracking-widest transition-colors hover:text-foreground relative",
                        activeTab === 'components' ? "text-neon-yellow" : "text-muted-foreground/70"
                    )}
                >
                    Components
                    {activeTab === 'components' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-neon-yellow" />}
                </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto space-y-5 scrollbar-hide">
                {activeTab === 'apps' ? (
                    <SavedAppsList />
                ) : (
                    <ComponentLibrary />
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
            { type: 'text', label: 'Text Block', icon: AlignLeft, defaultW: 6, defaultH: 4 },
            { type: 'markdown', label: 'Markdown', icon: FileText, defaultW: 6, defaultH: 6 },
            { type: 'image', label: 'Image', icon: Image, defaultW: 6, defaultH: 6 },
            { type: 'spacer', label: 'Spacer', icon: Hash, defaultW: 12, defaultH: 1 },
            { type: 'divider', label: 'Divider', icon: Minus, defaultW: 12, defaultH: 1 },
        ]
    },
    {
        name: 'Charts & Data',
        items: [
            { type: 'metric', label: 'Metric', icon: Hash, defaultW: 3, defaultH: 3 },
            { type: 'trend', label: 'Trend Metric', icon: TrendingUp, defaultW: 3, defaultH: 3 },
            { type: 'line_chart', label: 'Line Chart', icon: LineChart, defaultW: 6, defaultH: 8 },
            { type: 'bar_chart', label: 'Bar Chart', icon: BarChart3, defaultW: 6, defaultH: 6 },
            { type: 'area_chart', label: 'Area Chart', icon: LineChart, defaultW: 6, defaultH: 6 },
            { type: 'pie_chart', label: 'Pie Chart', icon: PieChart, defaultW: 4, defaultH: 4 },
            { type: 'sankey', label: 'Sankey Chart', icon: ArrowRight, defaultW: 4, defaultH: 8 },
            { type: 'scatter', label: 'Scatter Plot', icon: BarChart3, defaultW: 6, defaultH: 6 },
            { type: 'heatmap', label: 'Heatmap', icon: LayoutGrid, defaultW: 6, defaultH: 6 },
            { type: 'table', label: 'Data Table', icon: Table2, defaultW: 6, defaultH: 6 },
        ]
    },
    {
        name: 'Finance',
        items: [
            { type: 'profile', label: 'Profile', icon: User, defaultW: 4, defaultH: 6 }, // Adjusted based on common usage
            { type: 'valuation', label: 'Valuation Gauge', icon: Gauge, defaultW: 6, defaultH: 4 },
            { type: 'score_card', label: 'Score Card', icon: Medal, defaultW: 3, defaultH: 3 },
            { type: 'grade_card', label: 'Grade Card', icon: Medal, defaultW: 3, defaultH: 3 },
            { type: 'peer_table', label: 'Peer Table', icon: Table2, defaultW: 6, defaultH: 5 },
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
            // New Blocks.so Components
            { type: 'ai_chat', label: 'AI Chat', icon: Bot, defaultW: 6, defaultH: 8 },
            { type: 'share_dialog', label: 'Share Dialog', icon: Share2, defaultW: 4, defaultH: 4 },
            { type: 'file_upload', label: 'File Upload', icon: Upload, defaultW: 6, defaultH: 6 },
            { type: 'form_layout', label: 'Form Layout', icon: FormInput, defaultW: 6, defaultH: 8 },
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
            { type: 'usage_stats', label: 'Usage Stats', icon: BarChart3, defaultW: 6, defaultH: 6 },
            { type: 'storage_card', label: 'Storage Card', icon: PieChart, defaultW: 4, defaultH: 4 },
            { type: 'accordion_table', label: 'Accordion Table', icon: Table2, defaultW: 6, defaultH: 8 },
            { type: 'stats_row', label: 'Stats Row', icon: TrendingUp, defaultW: 12, defaultH: 3 },
            { type: 'task_table', label: 'Task Table', icon: ListTodo, defaultW: 8, defaultH: 4 },
            { type: 'inventory_table', label: 'Inventory Table', icon: Package, defaultW: 8, defaultH: 4 },
        ]
    },
    {
        name: 'Quiz Blocks',
        items: [
            // Phase 1: Simple Selection
            { type: 'quiz_mcq', label: 'Multiple Choice', icon: CheckSquare, defaultW: 6, defaultH: 5 },
            { type: 'quiz_tf', label: 'True / False', icon: ToggleLeft, defaultW: 4, defaultH: 4 },
            { type: 'quiz_multi', label: 'Multiple Answers', icon: CheckSquare, defaultW: 6, defaultH: 6 },
            { type: 'quiz_rating', label: 'Rating', icon: Star, defaultW: 4, defaultH: 3 },
            { type: 'quiz_likert', label: 'Likert Scale', icon: Sliders, defaultW: 6, defaultH: 4 },
            { type: 'quiz_nps', label: 'Net Promoter Score', icon: Gauge, defaultW: 6, defaultH: 4 },
            { type: 'quiz_ranking', label: 'Ranking', icon: LayoutGrid, defaultW: 5, defaultH: 6 },
            // Phase 2: Input-Based
            { type: 'quiz_fitb', label: 'Fill In the Blank', icon: Type, defaultW: 6, defaultH: 4 },
            { type: 'quiz_fitmb', label: 'Fill Multiple Blanks', icon: AlignLeft, defaultW: 6, defaultH: 5 },
            { type: 'quiz_number', label: 'Numerical Answer', icon: Hash, defaultW: 4, defaultH: 4 },
            { type: 'quiz_formula', label: 'Formula Question', icon: Code2, defaultW: 6, defaultH: 5 },
            { type: 'quiz_date', label: 'Date Question', icon: Calendar, defaultW: 4, defaultH: 4 },
            { type: 'quiz_essay', label: 'Essay Question', icon: FileText, defaultW: 6, defaultH: 8 },
            // Phase 3: Advanced Interactive
            { type: 'quiz_match', label: 'Matching', icon: ArrowRight, defaultW: 6, defaultH: 6 },
            { type: 'quiz_dropdown', label: 'Multiple Dropdowns', icon: CheckSquare, defaultW: 6, defaultH: 5 },
            { type: 'quiz_code', label: 'Code Editor', icon: Code2, defaultW: 6, defaultH: 8 },
            { type: 'quiz_upload', label: 'File Upload', icon: FileText, defaultW: 4, defaultH: 4 },
            { type: 'quiz_image', label: 'Image Interaction', icon: Image, defaultW: 6, defaultH: 6 },
            // Phase 4: Structural & AI
            { type: 'quiz_text', label: 'Text (No Question)', icon: AlignLeft, defaultW: 6, defaultH: 3 },
            { type: 'quiz_section', label: 'Section', icon: LayoutGrid, defaultW: 12, defaultH: 2 },
            { type: 'quiz_media', label: 'Media-Based', icon: Play, defaultW: 6, defaultH: 6 },
            { type: 'quiz_branch', label: 'Conditional Branch', icon: ArrowRight, defaultW: 6, defaultH: 5 },
            { type: 'quiz_ai', label: 'AI-Graded Task', icon: MessageSquare, defaultW: 6, defaultH: 8 },
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
        <div className="flex flex-col gap-4">
            <div className="sticky top-0 px-4 pt-4 pb-2 z-20 bg-card border-b border-border/50">
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-muted-foreground transition-all"
                        placeholder="Search 60+ components..."
                    />
                </div>
            </div>
            <div className="px-4 pb-4 space-y-4">

                {filteredCategories.map(category => {
                    const isExpanded = isSearching || expandedCategories[category.name];
                    return (
                        <div key={category.name} className="border border-border/50 rounded-lg overflow-hidden bg-background/50">
                            <button
                                onClick={() => toggleCategory(category.name)}
                                className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 transition-colors"
                            >
                                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">
                                    {category.name}
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] text-muted-foreground">{category.items.length}</span>
                                    <svg
                                        className={`w-3 h-3 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`}
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
                        <div className="text-[11px] font-bold text-foreground">Add a heading</div>
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
                            <Image className="w-3 h-3 text-muted-foreground" />
                        </div>
                    </div>
                );
            case 'spacer':
                return (
                    <div className="w-full h-full flex items-center justify-center">
                        <div className="w-full h-4 border border-dashed border-gray-700 rounded flex items-center justify-center">
                            <div className="text-[8px] text-muted-foreground">SPACE</div>
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
                        <div className="text-[8px] text-muted-foreground uppercase">Revenue</div>
                        <div className="text-sm font-black text-foreground">$2.4M</div>
                        <div className="flex items-center gap-0.5 text-green-400">
                            <TrendingUp className="w-2 h-2" />
                            <span className="text-[8px]">+12.5%</span>
                        </div>
                    </div>
                );
            case 'trend':
                return (
                    <div className="w-full h-full flex flex-col p-3">
                        <div className="text-[8px] text-muted-foreground">PRICE</div>
                        <div className="text-[10px] font-bold text-foreground">$145.20</div>
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
                            <path d="M0 20 Q10 15 20 18 T35 8 T50 5" fill="none" stroke="#F5C542" strokeWidth="2" />
                            <path d="M0 20 Q10 15 20 18 T35 8 T50 5 V25 H0 Z" fill="url(#lineGrad)" opacity="0.2" />
                            <defs>
                                <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#F5C542" />
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
                            <path d="M0 25 L0 18 Q12 12 25 15 T50 8 V25 Z" fill="#F5C542" opacity="0.3" />
                            <path d="M0 18 Q12 12 25 15 T50 8" fill="none" stroke="#F5C542" strokeWidth="1.5" />
                        </svg>
                    </div>
                );
            case 'pie_chart':
                return (
                    <div className="w-full h-full flex items-center justify-center p-2">
                        <svg viewBox="0 0 32 32" className="w-10 h-10">
                            <circle cx="16" cy="16" r="14" fill="none" stroke="#374151" strokeWidth="4" />
                            <circle cx="16" cy="16" r="14" fill="none" stroke="#F5C542" strokeWidth="4" strokeDasharray="44 88" transform="rotate(-90 16 16)" />
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
                            <div className="text-[9px] font-bold text-foreground">Alphabet</div>
                            <div className="text-[7px] text-muted-foreground">GOOGL</div>
                        </div>
                    </div>
                );
            case 'valuation':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-muted-foreground">FAIR VALUE</div>
                        <div className="flex items-center gap-1">
                            <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                                <div className="h-full w-3/5 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded-full" />
                            </div>
                        </div>
                        <div className="flex justify-between text-[7px]">
                            <span className="text-foreground">$145</span>
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
                        <div className="text-[7px] text-muted-foreground">Top Tier</div>
                    </div>
                );
            case 'peer_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex gap-1 text-[6px] text-muted-foreground">
                            <span className="flex-1">Ticker</span>
                            <span className="flex-1">MCap</span>
                            <span className="flex-1">P/E</span>
                        </div>
                        {['AAPL', 'MSFT', 'GOOGL'].map(t => (
                            <div key={t} className="flex gap-1 text-[6px] text-muted-foreground">
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
                            <div key={i} className="bg-muted/50 rounded p-1 flex flex-col items-center">
                                <div className="text-[6px] text-muted-foreground">{r.n}</div>
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
                                <span className="text-[7px] text-muted-foreground">{c.n}</span>
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
                                    <span className="text-muted-foreground">{r.n}</span>
                                    <span className="text-foreground">{r.v}</span>
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
                        <div className="text-[6px] text-muted-foreground leading-tight">Strong fundamentals with healthy growth...</div>
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
                        <div className="w-full h-5 bg-background border border-gray-700 rounded px-1.5 flex items-center">
                            <span className="text-[7px] text-muted-foreground">Enter ticker...</span>
                        </div>
                    </div>
                );
            case 'select':
                return (
                    <div className="w-full h-full flex items-center justify-center p-3">
                        <div className="w-full h-5 bg-background border border-gray-700 rounded px-1.5 flex items-center justify-between">
                            <span className="text-[7px] text-muted-foreground">Select...</span>
                            <span className="text-[7px] text-muted-foreground">▼</span>
                        </div>
                    </div>
                );
            case 'date_picker':
                return (
                    <div className="w-full h-full flex items-center justify-center p-3">
                        <div className="w-full h-5 bg-background border border-gray-700 rounded px-1.5 flex items-center gap-1">
                            <Calendar className="w-2 h-2 text-muted-foreground" />
                            <span className="text-[7px] text-muted-foreground">Dec 26, 2025</span>
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
                        <div className="text-[6px] text-muted-foreground">[DEBUG] Init</div>
                        <div className="text-[6px] text-neon-yellow">[WARN] Check</div>
                    </div>
                );
            case 'json':
                return (
                    <div className="w-full h-full flex flex-col p-2  text-[6px]">
                        <span className="text-muted-foreground">{"{"}</span>
                        <span className="pl-1"><span className="text-neon-yellow">"ticker"</span>: <span className="text-green-400">"GOOGL"</span></span>
                        <span className="text-muted-foreground">{"}"}</span>
                    </div>
                );
            case 'code':
                return (
                    <div className="w-full h-full flex flex-col p-2  text-[6px]">
                        <span className="text-purple-400">def</span><span className="text-foreground"> analyze():</span>
                        <span className="pl-2 text-muted-foreground"># logic here</span>
                        <span className="pl-2 text-blue-400">return</span><span className="text-foreground"> data</span>
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
                                <div className="text-[7px] text-muted-foreground">{stat.label}</div>
                                <div className="flex items-center gap-1">
                                    <span className="text-[8px] font-bold text-foreground">{stat.value}</span>
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
                            <div key={i} className="bg-muted/50 rounded p-1 flex flex-col items-center">
                                <div className="text-[9px] font-bold text-foreground">{s.v}</div>
                                <div className={`text-[6px] ${s.neg ? 'text-red-400' : 'text-green-400'}`}>{s.c}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'stats_status':
                return (
                    <div className="w-full h-full grid grid-cols-2 gap-1 p-2">
                        {[{ v: '99.9%', s: 'success' }, { v: '142ms', s: 'success' }, { v: '0.4%', s: 'warning' }, { v: '2,847', s: 'info' }].map((s, i) => (
                            <div key={i} className="bg-muted/50 rounded p-1 flex items-center gap-1">
                                <div className={`w-1.5 h-1.5 rounded-full ${s.s === 'success' ? 'bg-green-500' : s.s === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'}`} />
                                <div className="text-[8px] font-bold text-foreground">{s.v}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'stats_links':
                return (
                    <div className="w-full h-full flex flex-col gap-1 p-2 justify-center">
                        {['Projects: 12', 'Issues: 47', 'PRs: 8'].map((item, i) => (
                            <div key={i} className="flex items-center justify-between text-[7px] text-muted-foreground hover:text-foreground">
                                <span>{item.split(':')[0]}</span>
                                <span className="text-foreground font-bold">{item.split(':')[1]}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'simple_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex gap-1 text-[6px] text-muted-foreground border-b border-border pb-0.5">
                            <span className="flex-1">Task</span><span className="flex-1">Status</span>
                        </div>
                        {[['Auth', '🟡'], ['UI', '🟢'], ['API', '⚪']].map(([t, s], i) => (
                            <div key={i} className="flex gap-1 text-[6px] text-muted-foreground">
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
                                <div className="text-[9px] font-bold text-foreground">{s.v}</div>
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
                                    <span className="text-muted-foreground">{u.n}</span>
                                    <span className="text-muted-foreground">{u.p}%</span>
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
                        <div className="text-[7px] text-muted-foreground">8.3 / 15 GB</div>
                    </div>
                );

            case 'accordion_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex items-center gap-1 text-[6px] text-foreground bg-muted/50 rounded px-1 py-0.5">
                            <span className="text-muted-foreground">▶</span>
                            <span>Project A</span>
                            <span className="ml-auto text-neon-yellow">$45K</span>
                        </div>
                        <div className="flex items-center gap-1 text-[6px] text-muted-foreground pl-2">
                            <span>└ Frontend</span>
                            <span className="ml-auto">$15K</span>
                        </div>
                        <div className="flex items-center gap-1 text-[6px] text-foreground bg-muted/50 rounded px-1 py-0.5">
                            <span className="text-muted-foreground">▶</span>
                            <span>Campaign</span>
                            <span className="ml-auto text-neon-yellow">$28K</span>
                        </div>
                    </div>
                );

            // QUIZ BLOCKS - Phase 1: Simple Selection
            case 'quiz_mcq':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground font-medium">What is 2+2?</div>
                        <div className="flex flex-col gap-0.5">
                            {['4', '5', '3'].map((opt, i) => (
                                <div key={i} className={cn("flex items-center gap-1 px-1 py-0.5 rounded text-[6px]", i === 0 ? "bg-neon-yellow/20 text-neon-yellow" : "bg-muted/40 text-muted-foreground")}>
                                    <div className={cn("w-2 h-2 rounded-full border", i === 0 ? "border-neon-yellow bg-neon-yellow" : "border-gray-500")} />
                                    <span>{opt}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            case 'quiz_tf':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground font-medium">The sky is blue</div>
                        <div className="flex gap-1">
                            <div className="flex-1 bg-green-500/20 text-green-400 rounded px-2 py-1 text-[8px] text-center font-medium">TRUE</div>
                            <div className="flex-1 bg-muted/40 text-muted-foreground rounded px-2 py-1 text-[8px] text-center">FALSE</div>
                        </div>
                    </div>
                );
            case 'quiz_multi':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground font-medium">Select all that apply</div>
                        <div className="flex flex-col gap-0.5">
                            {['Option A', 'Option B', 'Option C'].map((opt, i) => (
                                <div key={i} className={cn("flex items-center gap-1 px-1 py-0.5 rounded text-[6px]", i < 2 ? "bg-neon-yellow/20 text-neon-yellow" : "bg-muted/40 text-muted-foreground")}>
                                    <div className={cn("w-2 h-2 rounded-sm border", i < 2 ? "border-neon-yellow bg-neon-yellow" : "border-gray-500")} />
                                    <span>{opt}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            case 'quiz_rating':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2 gap-1">
                        <div className="text-[7px] text-foreground font-medium">Rate this</div>
                        <div className="flex gap-0.5">
                            {[1, 2, 3, 4, 5].map((s) => (
                                <Star key={s} className={cn("w-3 h-3", s <= 4 ? "fill-neon-yellow text-neon-yellow" : "text-gray-500")} />
                            ))}
                        </div>
                    </div>
                );
            case 'quiz_likert':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[6px] text-foreground font-medium">I agree with...</div>
                        <div className="flex gap-0.5 justify-center">
                            {['1', '2', '3', '4', '5'].map((n, i) => (
                                <div key={i} className={cn("w-3 h-3 rounded-full border flex items-center justify-center text-[5px]", i === 3 ? "bg-neon-yellow border-neon-yellow text-black" : "border-gray-500 text-gray-500")}>
                                    {n}
                                </div>
                            ))}
                        </div>
                        <div className="flex justify-between text-[5px] text-muted-foreground">
                            <span>Disagree</span><span>Agree</span>
                        </div>
                    </div>
                );
            case 'quiz_nps':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[6px] text-foreground font-medium">How likely to recommend?</div>
                        <div className="flex gap-0.5">
                            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                                <div key={n} className={cn("w-2 h-3 rounded-sm text-[4px] flex items-center justify-center",
                                    n <= 6 ? "bg-red-500/50" : n <= 8 ? "bg-yellow-500/50" : "bg-green-500/50",
                                    n === 9 ? "ring-1 ring-neon-yellow" : ""
                                )}>{n}</div>
                            ))}
                        </div>
                    </div>
                );
            case 'quiz_ranking':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="text-[6px] text-foreground font-medium">Rank in order</div>
                        {['1. Apple', '2. Banana', '3. Cherry'].map((item, i) => (
                            <div key={i} className="flex items-center gap-1 bg-muted/40 rounded px-1 py-0.5 text-[6px] text-muted-foreground">
                                <LayoutGrid className="w-2 h-2" />
                                <span>{item}</span>
                            </div>
                        ))}
                    </div>
                );

            // Phase 2: Input-Based
            case 'quiz_fitb':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground">The capital of France is <span className="px-1 bg-neon-yellow/20 text-neon-yellow rounded">Paris</span></div>
                    </div>
                );
            case 'quiz_fitmb':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[6px] text-foreground"><span className="px-1 bg-neon-yellow/20 text-neon-yellow rounded">A</span> + <span className="px-1 bg-neon-yellow/20 text-neon-yellow rounded">B</span> = C</div>
                    </div>
                );
            case 'quiz_number':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground">What is 5 × 7?</div>
                        <div className="bg-muted/40 rounded px-2 py-1 text-[10px] text-neon-yellow font-mono">35</div>
                    </div>
                );
            case 'quiz_formula':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground">Solve: x² = 16</div>
                        <div className="bg-muted/40 rounded px-2 py-1 text-[8px] text-neon-yellow font-mono">x = ±4</div>
                    </div>
                );
            case 'quiz_date':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground">When did WWII end?</div>
                        <div className="flex items-center gap-1 bg-muted/40 rounded px-2 py-1 text-[8px] text-muted-foreground">
                            <Calendar className="w-2 h-2" />
                            <span>1945-09-02</span>
                        </div>
                    </div>
                );
            case 'quiz_essay':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground">Explain your answer</div>
                        <div className="flex-1 border border-dashed border-gray-600 rounded p-1">
                            <div className="h-0.5 w-full bg-gray-600 rounded mb-0.5" />
                            <div className="h-0.5 w-4/5 bg-gray-700 rounded mb-0.5" />
                            <div className="h-0.5 w-3/5 bg-gray-700 rounded" />
                        </div>
                    </div>
                );

            // Phase 3: Advanced Interactive
            case 'quiz_match':
                return (
                    <div className="w-full h-full flex p-2 gap-1">
                        <div className="flex-1 flex flex-col gap-0.5">
                            {['A', 'B'].map((l) => <div key={l} className="bg-muted/40 rounded px-1 py-0.5 text-[6px] text-muted-foreground">{l}</div>)}
                        </div>
                        <div className="flex items-center"><ArrowRight className="w-2 h-2 text-neon-yellow" /></div>
                        <div className="flex-1 flex flex-col gap-0.5">
                            {['1', '2'].map((r) => <div key={r} className="bg-neon-yellow/20 rounded px-1 py-0.5 text-[6px] text-neon-yellow">{r}</div>)}
                        </div>
                    </div>
                );
            case 'quiz_dropdown':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[6px] text-foreground">The <span className="px-1 bg-muted rounded text-neon-yellow">🔽 cat</span> sat on the <span className="px-1 bg-muted rounded text-neon-yellow">🔽 mat</span></div>
                    </div>
                );
            case 'quiz_code':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5 bg-charcoal-900 rounded">
                        <div className="text-[6px] text-purple-400">def</div>
                        <div className="text-[6px] text-neon-yellow">  solve():</div>
                        <div className="text-[6px] text-gray-400">    # code</div>
                    </div>
                );
            case 'quiz_upload':
                return (
                    <div className="w-full h-full flex items-center justify-center p-2">
                        <div className="border-2 border-dashed border-gray-600 rounded p-2 flex flex-col items-center">
                            <FileText className="w-4 h-4 text-muted-foreground" />
                            <div className="text-[6px] text-muted-foreground">Upload</div>
                        </div>
                    </div>
                );
            case 'quiz_image':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="flex-1 bg-gradient-to-br from-gray-700 to-gray-800 rounded flex items-center justify-center">
                            <Image className="w-4 h-4 text-muted-foreground" />
                        </div>
                        <div className="flex gap-0.5">
                            <div className="w-2 h-2 rounded-full bg-red-500/50" />
                            <div className="w-2 h-2 rounded-full bg-neon-yellow/50" />
                        </div>
                    </div>
                );

            // Phase 4: Structural & AI
            case 'quiz_text':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[8px] text-foreground font-medium">Instructions</div>
                        <div className="h-0.5 w-full bg-gray-600 rounded" />
                        <div className="h-0.5 w-4/5 bg-gray-700 rounded" />
                    </div>
                );
            case 'quiz_section':
                return (
                    <div className="w-full h-full flex items-center justify-center p-2">
                        <div className="text-[9px] font-bold text-foreground border-b-2 border-neon-yellow pb-0.5">Section 1</div>
                    </div>
                );
            case 'quiz_media':
                return (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900 rounded">
                        <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center">
                            <Play className="w-3 h-3 text-primary-foreground" />
                        </div>
                    </div>
                );
            case 'quiz_branch':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[6px] text-foreground">If answer = A</div>
                        <div className="flex items-center gap-1 text-[6px] text-neon-yellow">
                            <ArrowRight className="w-2 h-2" /><span>Go to Q5</span>
                        </div>
                    </div>
                );
            case 'quiz_ai':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="text-[7px] text-foreground">AI will grade:</div>
                        <div className="flex items-center gap-1 text-[6px] text-purple-400">
                            <MessageSquare className="w-3 h-3" />
                            <span>Evaluating...</span>
                        </div>
                    </div>
                );

            // New Blocks.so Component Previews
            case 'stats_row':
                return (
                    <div className="w-full h-full grid grid-cols-4 gap-1 p-2">
                        {[{ v: '$287K', c: '+8%' }, { v: '$9K', c: '-12%' }, { v: '$173K', c: '+3%' }, { v: '$52K', c: '-5%' }].map((s, i) => (
                            <div key={i} className="flex flex-col items-center justify-center">
                                <div className="text-[8px] font-bold text-foreground">{s.v}</div>
                                <div className={`text-[6px] ${s.c.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{s.c}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'plan_overview':
                return (
                    <div className="w-full h-full grid grid-cols-2 gap-1 p-2">
                        {['20%', '45%', '30%', '60%'].map((p, i) => (
                            <div key={i} className="flex items-center gap-1">
                                <svg viewBox="0 0 20 20" className="w-6 h-6">
                                    <circle cx="10" cy="10" r="8" fill="none" stroke="#374151" strokeWidth="2" />
                                    <circle cx="10" cy="10" r="8" fill="none" stroke="#F5C542" strokeWidth="2" strokeDasharray={`${parseInt(p) * 0.5} 50`} transform="rotate(-90 10 10)" />
                                </svg>
                                <span className="text-[6px] text-muted-foreground">{p}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'trend_cards':
                return (
                    <div className="w-full h-full grid grid-cols-3 gap-1 p-2">
                        {['+10.4%', '+6.3%', '-7.1%'].map((c, i) => (
                            <div key={i} className="flex flex-col items-center justify-center bg-muted/30 rounded p-1">
                                <div className="text-[8px] font-bold text-foreground">$168</div>
                                <div className={`text-[6px] ${c.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{c}</div>
                            </div>
                        ))}
                    </div>
                );

            case 'usage_gauge':
                return (
                    <div className="w-full h-full flex flex-col gap-1 p-2 justify-center">
                        {[35, 30, 48].map((p, i) => (
                            <div key={i} className="flex flex-col gap-0.5">
                                <div className="h-1 bg-charcoal-700 rounded-full overflow-hidden">
                                    <div className="h-full bg-neon-yellow rounded-full" style={{ width: `${p}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                );

            case 'storage_donut':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2">
                        <svg viewBox="0 0 36 36" className="w-10 h-10">
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#374151" strokeWidth="3" />
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#F5C542" strokeWidth="3" strokeDasharray="40 48" transform="rotate(-90 18 18)" />
                        </svg>
                        <div className="text-[6px] text-muted-foreground">55% used</div>
                    </div>
                );

            case 'task_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        {['🟢 Done', '🔵 Active', '🟡 Pending'].map((t, i) => (
                            <div key={i} className="flex items-center gap-1 text-[6px] text-muted-foreground">
                                <span>{t}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'inventory_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        <div className="flex gap-1 text-[6px] text-muted-foreground border-b border-border pb-0.5">
                            <span className="flex-1">SKU</span><span className="flex-1">Stock</span>
                        </div>
                        {[['8472', '245'], ['3391', '89']].map(([s, q], i) => (
                            <div key={i} className="flex gap-1 text-[6px] text-muted-foreground">
                                <span className="flex-1">{s}</span><span className="flex-1">{q}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'project_table':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-0.5">
                        {[{ n: 'Alpha', a: '$2.5K' }, { n: 'Beta', a: '$1.2K' }].map((p, i) => (
                            <div key={i} className="flex justify-between text-[6px]">
                                <span className="text-muted-foreground">{p.n}</span>
                                <span className="text-neon-yellow">{p.a}</span>
                            </div>
                        ))}
                    </div>
                );

            case 'ai_chat':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1">
                        <div className="self-end bg-neon-yellow/20 rounded-lg px-2 py-1 text-[6px] text-neon-yellow">Hello!</div>
                        <div className="self-start bg-muted rounded-lg px-2 py-1 text-[6px] text-muted-foreground">Hi there...</div>
                    </div>
                );

            case 'share_dialog':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2 gap-1">
                        <Share2 className="w-4 h-4 text-muted-foreground" />
                        <div className="text-[6px] text-muted-foreground">Share & Collab</div>
                    </div>
                );

            case 'file_upload':
                return (
                    <div className="w-full h-full flex flex-col items-center justify-center p-2 gap-1">
                        <Upload className="w-4 h-4 text-muted-foreground" />
                        <div className="text-[6px] text-muted-foreground">Drop files</div>
                    </div>
                );

            case 'form_layout':
                return (
                    <div className="w-full h-full flex flex-col p-2 gap-1 justify-center">
                        <div className="h-4 bg-muted border border-border rounded text-[6px] px-1 flex items-center text-muted-foreground">Name...</div>
                        <div className="h-4 bg-muted border border-border rounded text-[6px] px-1 flex items-center text-muted-foreground">Email...</div>
                    </div>
                );

            default:
                return (
                    <div className="w-full h-full flex items-center justify-center">
                        <Icon className="w-5 h-5 text-muted-foreground" />
                    </div>
                );
        }
    };

    return (
        <div
            draggable
            onDragStart={handleDragStart}
            className={cn(
                "group relative flex flex-col rounded-xl border-2 cursor-grab active:cursor-grabbing transition-all duration-300 overflow-hidden select-none shadow-lg",
                // Match Explorer node styling
                isSelected
                    ? "bg-muted border-neon-yellow ring-4 ring-neon-yellow/20 scale-[1.02]"
                    : "bg-card/90 border-border hover:border-primary/30 hover:scale-[1.02]"
            )}
        >
            {/* Preview Area - matches the actual card appearance with animation */}
            <div className="aspect-[2] w-full overflow-hidden bg-background/50 group-hover:bg-card/80 transition-colors">
                <div className="w-full h-full animate-in fade-in slide-in-from-bottom-1 duration-500">
                    {renderPreview()}
                </div>
            </div>

            {/* Label */}
            <div className={cn(
                "px-2 py-1 text-[10px] font-medium text-center border-t transition-colors",
                isSelected ? "bg-muted border-neon-yellow/20 text-neon-yellow" : "bg-card border-border/50 text-muted-foreground"
            )}>
                {label}
            </div>
        </div>
    );
};

const SavedAppsList = () => {
    const { savedApps, loadApp, deleteApp, editingAppId, fetchApps, renameApp } = useAppStore();
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState<'name' | 'time'>('time');
    const [editingNameId, setEditingNameId] = useState<string | null>(null);
    const [tempName, setTempName] = useState('');

    // Auto-refresh apps every 5 seconds (Pseudo Hot-Loading)
    useEffect(() => {
        fetchApps();
        const interval = setInterval(() => fetchApps(), 5000);
        return () => clearInterval(interval);
    }, [fetchApps]);

    const handleStartEdit = (e: React.MouseEvent, app: SavedApp) => {
        e.stopPropagation();
        setEditingNameId(app.id);
        setTempName(app.name);
    };

    const handleSaveEdit = async (id: string) => {
        if (tempName.trim() && tempName !== savedApps.find(a => a.id === id)?.name) {
            await renameApp(id, tempName.trim());
        }
        setEditingNameId(null);
    };

    const sortedApps = savedApps
        .filter(app => app.name.toLowerCase().includes(searchQuery.toLowerCase()))
        .sort((a, b) => {
            if (sortBy === 'name') {
                return a.name.localeCompare(b.name);
            } else {
                return (b.lastModified || 0) - (a.lastModified || 0); // Newest first
            }
        });

    return (
        <div className="flex flex-col gap-4">
            {/* Sticky Search Bar + Sort */}
            <div className="sticky top-0 px-4 pt-4 pb-2 z-20 bg-card border-b border-border/50">
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <input
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search apps..."
                        className="w-full bg-muted border border-border rounded-lg text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-neon-yellow/50 text-foreground placeholder:text-muted-foreground transition-all"
                    />
                </div>
                {/* Minimal Sort Toggle */}
                <div className="flex items-center gap-2 mt-2">
                    <span className="text-[9px] text-muted-foreground uppercase tracking-wider">Sort:</span>
                    <button
                        onClick={() => setSortBy('time')}
                        className={cn(
                            "text-[9px] uppercase tracking-wider px-2 py-0.5 rounded transition-colors",
                            sortBy === 'time'
                                ? "text-neon-yellow bg-neon-yellow/10"
                                : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        Time
                    </button>
                    <button
                        onClick={() => setSortBy('name')}
                        className={cn(
                            "text-[9px] uppercase tracking-wider px-2 py-0.5 rounded transition-colors",
                            sortBy === 'name'
                                ? "text-neon-yellow bg-neon-yellow/10"
                                : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        Name
                    </button>
                </div>
            </div>

            {/* List */}
            <div className="space-y-3 px-4 pb-4">
                {savedApps.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground text-center space-y-2 opacity-60">
                        <LayoutGrid className="w-8 h-8 opacity-20" />
                        <p className="text-xs">No saved apps yet.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {sortedApps.map(app => {
                            const isActive = app.id === editingAppId;
                            const isEditing = editingNameId === app.id;

                            return (
                                <div
                                    key={app.id}
                                    className={cn(
                                        "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                        "bg-gradient-to-br from-card to-muted/20",
                                        "hover:shadow-md",
                                        isActive
                                            ? "border-neon-yellow/40 hover:border-neon-yellow/60 bg-neon-yellow/5"
                                            : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                    )}
                                    onClick={() => !isEditing && loadApp(app.id)}
                                >
                                    <div className="flex justify-between items-start gap-0">
                                        <div className="flex-1 min-w-0">
                                            {isEditing ? (
                                                <input
                                                    autoFocus
                                                    value={tempName}
                                                    onChange={(e) => setTempName(e.target.value)}
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') handleSaveEdit(app.id);
                                                        if (e.key === 'Escape') setEditingNameId(null);
                                                    }}
                                                    onBlur={() => handleSaveEdit(app.id)}
                                                    onClick={(e) => e.stopPropagation()}
                                                    className="w-full bg-muted border border-neon-yellow/50 rounded px-2 py-1 text-[13px] font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-neon-yellow/30"
                                                />
                                            ) : (
                                                <p
                                                    onClick={(e) => handleStartEdit(e, app)}
                                                    className={cn(
                                                        "text-[13px] leading-relaxed font-medium selection:bg-neon-yellow/30",
                                                        "line-clamp-2 group-hover:line-clamp-none transition-all duration-300",
                                                        isActive ? "text-neon-yellow" : "text-foreground",
                                                        "hover:text-neon-yellow"
                                                    )}
                                                >
                                                    {app.name}
                                                </p>
                                            )}
                                        </div>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); deleteApp(app.id); }}
                                            className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-lg text-muted-foreground hover:text-red-400 transition-all duration-200"
                                            title="Delete App"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>

                                    <div className="mt-0 pt-0 border-t border-border/50 flex items-center justify-between">
                                        <span className="text-[9px] text-muted-foreground font-mono">
                                            {isActive ? "Currently Editing" : new Date(app.lastModified).toLocaleDateString()}
                                        </span>
                                        {isActive && (
                                            <span className="px-2 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-tighter bg-neon-yellow/10 text-neon-yellow">
                                                ACTIVE
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
