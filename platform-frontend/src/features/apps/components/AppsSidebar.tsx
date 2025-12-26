import React, { useState } from 'react';
import { cn } from '@/lib/utils';
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

const ComponentLibrary = () => {
    return (
        <div className="space-y-6">
            <div className="relative">
                <Search className="absolute left-2.5 top-2.5 w-3 h-3 text-muted-foreground" />
                <input
                    className="w-full bg-background/50 border border-input rounded text-xs pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground"
                    placeholder="Search components..."
                />
            </div>

            {/* Basics */}
            <div className="space-y-3">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Basics</div>
                <div className="grid grid-cols-2 gap-2">
                    <DraggableCard type="header" label="Header" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="text" label="Text Block" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="metric" label="Metric" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="image" label="Image" icon={<LayoutGrid className="w-3 h-3" />} />
                </div>
            </div>

            {/* Charts */}
            <div className="space-y-3">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Charts</div>
                <div className="grid grid-cols-2 gap-2">
                    <DraggableCard type="line_chart" label="Line Chart" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="bar_chart" label="Bar Chart" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="pie_chart" label="Pie Chart" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="table" label="Table" icon={<LayoutGrid className="w-3 h-3" />} />
                </div>
            </div>

            {/* Finance */}
            <div className="space-y-3">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Finance</div>
                <div className="grid grid-cols-2 gap-2">
                    <DraggableCard type="score_card" label="Score Card" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="valuation" label="Valuation" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="profile" label="Profile" icon={<LayoutGrid className="w-3 h-3" />} />
                    <DraggableCard type="ratios" label="Key Ratios" icon={<LayoutGrid className="w-3 h-3" />} />
                </div>
            </div>
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
const DraggableCard = ({ type, label, icon }: { type: string, label: string, icon: React.ReactNode }) => {
    const handleDragStart = (e: React.DragEvent) => {
        e.dataTransfer.setData('application/json', JSON.stringify({ type, label }));
        e.dataTransfer.effectAllowed = 'copy';
    };

    return (
        <div
            draggable
            onDragStart={handleDragStart}
            className="group relative flex flex-col items-center justify-center gap-2 p-3 rounded-lg border border-border bg-card hover:border-primary/50 hover:bg-accent/50 cursor-grab active:cursor-grabbing transition-all hover:scale-[1.02] shadow-sm"
            title={`Drag to add ${label}`}
        >
            {/* Mini Preview Placeholder */}
            <div className="w-full aspect-[1.5] bg-background/50 rounded border border-white/5 mb-1 flex items-center justify-center">
                <div className="w-8 h-1 bg-white/10 rounded-full" />
            </div>

            <div className="text-[10px] font-medium text-center text-foreground w-full truncate">{label}</div>

            <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 text-muted-foreground">
                <GripVertical className="w-3 h-3" />
            </div>
        </div>
    );
};
