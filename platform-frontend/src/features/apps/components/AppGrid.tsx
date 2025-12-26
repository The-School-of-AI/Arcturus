import React, { useState, useCallback, useRef, useEffect } from 'react';
import { ResponsiveGridLayout as RGLResponsiveBase } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

// Cast to any to allow legacy props that types don't include
const RGLResponsive = RGLResponsiveBase as any;
import { Maximize2, Minimize2, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { MetricCard } from './cards/MetricCard';
import { TrendMetric } from './cards/TrendMetric';
import { ChartCard } from './cards/ChartCard';
import { PieChartCard } from './cards/PieChartCard';
import { CandlestickCard } from './cards/CandlestickCard';
import { ProfileCard } from './cards/ProfileCard';
import { GradeCard } from './cards/GradeCard';
import { ScoreCard } from './cards/ScoreCard';
import { ValuationGauge } from './cards/ValuationGauge';
import { SummaryGrid } from './cards/SummaryGrid';
import { PeerTableCard } from './cards/PeerTableCard';
import { TableCard } from './cards/TableCard';
import { MarkdownCard } from './cards/MarkdownCard';
import { ImageCard } from './cards/ImageCard';
import { DividerCard } from './cards/DividerCard';
import { FeedCard } from './cards/FeedCard';
import { InputCard, ActionButtonCard, SelectCard, DateRangeCard } from './cards/ControlCards';
import { LogStreamCard } from './cards/LogStreamCard';
import { JSONViewerCard } from './cards/JSONViewerCard';
import { CodeBlockCard } from './cards/CodeBlockCard';

interface AppGridProps {
    className?: string;
    isFullScreen: boolean;
    onToggleFullScreen: () => void;
}

// Helper for Smart Default Dimensions
const getSmartDimensions = (type: string) => {
    switch (type) {
        // Full Width, Short Height
        case 'divider':
        case 'spacer':
        case 'header':
            return { w: 12, h: 2 };

        // Compact Metrics
        case 'metric':
        case 'trend':
        case 'score_card':
        case 'grade_card':
            return { w: 3, h: 3 };

        // Standard Charts
        case 'line_chart':
        case 'bar_chart':
        case 'area_chart':
        case 'candlestick':
        case 'scatter':
        case 'valuation':
            return { w: 6, h: 6 };

        // Large Views
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

        // Default
        default:
            return { w: 4, h: 4 };
    }
};

export const AppGrid: React.FC<AppGridProps> = ({ className, isFullScreen, onToggleFullScreen }) => {
    // Container ref for width measurement
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState(1200);
    const [zoomLevel, setZoomLevel] = useState(1);

    // Connect to Store
    const {
        appCards,
        appLayout,
        selectedAppCardId,
        addAppCard,
        setAppLayout,
        selectAppCard,
        removeAppCard
    } = useAppStore();

    // Measure container width
    useEffect(() => {
        const updateWidth = () => {
            if (containerRef.current) {
                setContainerWidth(containerRef.current.offsetWidth - 64); // minus padding
            }
        };
        updateWidth();
        window.addEventListener('resize', updateWidth);
        return () => window.removeEventListener('resize', updateWidth);
    }, []);

    const onDrop = (layout: any, layoutItem: any, _event: Event) => {
        const event = _event as DragEvent;
        const data = event.dataTransfer?.getData('application/json');
        if (!data) return;

        try {
            const { type, label } = JSON.parse(data);
            const newId = `${type}-${Date.now()}`;

            // Get smart dimensions
            const dims = getSmartDimensions(type);

            // Create new card
            const newCard = {
                id: newId,
                type,
                label,
                config: {},
                data: {}
            };

            // Add to store with smart dimensions override
            // layoutItem has x, y from drop, but we enforce w, h
            // We also need to double the width if we moved to 24 cols,
            // but for now let's keep dims relative to the column count or adjust them.
            // If we move to 24 cols, everything becomes half width if we keep same w.
            // So let's double the smart dimensions w for 24-col layout.
            const adjustedDims = { ...dims, w: dims.w * 2 }; // Scale for 24 cols

            addAppCard(newCard, { ...layoutItem, ...adjustedDims });

        } catch (e) {
            console.error("Failed to parse drop data", e);
        }
    };

    const handleLayoutChange = (newLayout: any) => {
        setAppLayout(newLayout);
    };

    const renderCardContent = (card: any) => {
        const { type, label } = card;

        // Match with sidebar types
        switch (type) {
            // Basics
            case 'header':
                return <div className="p-4"><h1 className="text-2xl font-bold text-foreground">{label}</h1></div>;
            case 'text':
                return <div className="p-4 text-sm text-muted-foreground">Basic paragraph text block. Select to edit.</div>;
            case 'markdown':
                return <MarkdownCard />;
            case 'image':
                return <ImageCard title={label} />;
            case 'spacer':
                return <div className="w-full h-full" />;
            case 'divider':
                return <DividerCard />;

            // Charts & Data
            case 'metric':
                return <MetricCard title={label} value="2.4M" change={12.5} trend="up" />;
            case 'trend':
                return <TrendMetric title={label} value="$145.2" change={2.4} />;
            case 'line_chart':
                return <ChartCard title={label} type="line" />;
            case 'bar_chart':
                return <ChartCard title={label} type="bar" />;
            case 'area_chart':
                return <ChartCard title={label} type="area" />;
            case 'pie_chart':
                return <PieChartCard title={label} />;
            case 'candlestick':
                return <CandlestickCard title={label} />;
            case 'table':
                return <TableCard title={label} />;

            // Finance
            case 'profile':
                return <ProfileCard />;
            case 'valuation':
                return <ValuationGauge title={label} />;
            case 'score_card':
                return <ScoreCard title={label} score={78} subtext="Healthy" />;
            case 'grade_card':
                return <GradeCard title={label} grade="A-" subtext="Top Tier" />;
            case 'peer_table':
                return <PeerTableCard title={label} />;
            case 'ratios':
                return <TableCard title="Key Ratios" headers={["Ratio", "Value", "Health"]} rows={[["P/E", "24.5", "Fair"], ["PEG", "1.1", "Good"], ["ROE", "22%", "Excellent"]]} />;
            case 'summary':
                return <SummaryGrid title={label} />;
            case 'cash_flow':
            case 'balance_sheet':
            case 'income_stmt':
                return <TableCard title={label} />;

            // Controls
            case 'button':
                return <ActionButtonCard label={label} />;
            case 'input':
                return <InputCard label={label} />;
            case 'select':
                return <SelectCard label={label} />;
            case 'date_picker':
                return <DateRangeCard label={label} />;

            // Dev & Feeds
            case 'feed':
                return <FeedCard title={label} />;
            case 'log':
                return <LogStreamCard title={label} />;
            case 'json':
                return <JSONViewerCard title={label} />;
            case 'code':
                return <CodeBlockCard title={label} />;
            case 'chat':
                return <div className="p-4 flex flex-col items-center justify-center h-full opacity-20"><span className="text-xs uppercase font-bold">Chat UI Placeholder</span></div>;

            default:
                return (
                    <div className="flex-1 flex items-center justify-center p-4 text-xs text-muted-foreground/30">
                        {type} implementation pending
                    </div>
                );
        }
    };

    return (
        <div
            className={cn("h-full w-full flex flex-col bg-charcoal-950 relative overflow-hidden", className)}
            onClick={() => selectAppCard(null)} // Auto-deselect on background click
        >
            {/* Toolbar Overlay */}
            <div className="absolute top-4 right-4 z-50 flex gap-2">
                <div className="flex items-center bg-charcoal-800/80 backdrop-blur rounded-lg border border-white/10 shadow-lg mr-2">
                    <button
                        onClick={(e) => { e.stopPropagation(); setZoomLevel(prev => Math.max(0.5, prev - 0.1)); }}
                        className="p-2 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors border-r border-white/10"
                        title="Zoom Out"
                    >
                        -
                    </button>
                    <span className="px-2 text-xs text-muted-foreground min-w-[3rem] text-center">{Math.round(zoomLevel * 100)}%</span>
                    <button
                        onClick={(e) => { e.stopPropagation(); setZoomLevel(prev => Math.min(1.5, prev + 0.1)); }}
                        className="p-2 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors"
                        title="Zoom In"
                    >
                        +
                    </button>
                </div>
                <button
                    onClick={(e) => { e.stopPropagation(); onToggleFullScreen(); }}
                    className="p-2 bg-charcoal-800/80 backdrop-blur rounded-lg border border-white/10 hover:bg-white/10 transition-colors text-muted-foreground hover:text-white shadow-lg"
                    title={isFullScreen ? "Exit Full Screen" : "Full Screen"}
                >
                    {isFullScreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                </button>
            </div>

            {/* Grid Area */}
            <div ref={containerRef} className="flex-1 overflow-y-auto p-8 custom-scrollbar bg-grid-dots">
                {!RGLResponsive ? (
                    <div className="flex flex-col items-center justify-center h-full text-red-400 space-y-4">
                        <div className="p-4 bg-red-500/10 rounded-lg border border-red-500/20">
                            <h3 className="font-bold">Library Load Error</h3>
                            <p className="text-xs">Could not load react-grid-layout. Check console for details.</p>
                        </div>
                    </div>
                ) : (
                    <div style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top left', width: `${100 / zoomLevel}%` }}>
                        <RGLResponsive
                            className="layout min-h-[500px]"
                            width={containerWidth} // We might need to adjust this based on scale effectively
                            layouts={{ lg: appLayout }}
                            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                            cols={{ lg: 24, md: 20, sm: 12, xs: 8, xxs: 4 }} // Double columns for finer granularity
                            rowHeight={40} // Reduced rowHeight for finer control (was 60)
                            onLayoutChange={handleLayoutChange}
                            isDroppable={true}
                            onDrop={onDrop}
                            droppingItem={{ i: 'dropping-placeholder', w: 8, h: 4 }} // Default drop size adjusted for 24 cols
                            draggableHandle=".drag-handle"
                            resizeHandles={['se', 's', 'e']}
                        >
                            {appCards.map(card => {
                                const isSelected = selectedAppCardId === card.id;
                                const isTransparent = ['divider', 'spacer'].includes(card.type);

                                return (
                                    <div key={card.id} className={cn(
                                        // Match FlowStepNode styling exactly
                                        "relative flex flex-col overflow-hidden group transition-all duration-500 shadow-2xl",
                                        // Base styles - match Explorer node
                                        isTransparent ? "bg-transparent" : "bg-charcoal-900/90",
                                        // Border / State styles - match Explorer node
                                        isSelected
                                            ? "border-2 border-neon-yellow ring-4 ring-neon-yellow/20 z-50"
                                            : isTransparent
                                                ? "border border-transparent hover:border-white/10 hover:bg-white/5"
                                                : "border-2 border-white/10 hover:border-white/30",
                                        // Rounding - match Explorer node
                                        card.type === 'divider' ? "rounded-none" : "rounded-xl"
                                    )}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            selectAppCard(card.id);
                                        }}
                                    >
                                        {/* Glow effect when selected - match FlowStepNode */}
                                        {isSelected && (
                                            <div className="absolute inset-0 rounded-xl bg-neon-yellow/5 blur-xl -z-10 animate-pulse" />
                                        )}

                                        {/* Minimal Drag Handle - Only visible on hover, top-right corner */}
                                        <div className={cn(
                                            "drag-handle absolute top-1.5 right-1.5 flex items-center gap-1 cursor-move select-none transition-all duration-300 z-50",
                                            isSelected 
                                                ? "opacity-100" 
                                                : "opacity-0 group-hover:opacity-100",
                                        )}>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    removeAppCard(card.id);
                                                }}
                                                className="p-1 bg-charcoal-800/80 hover:bg-red-500/20 hover:text-red-400 rounded transition-colors text-gray-500 border border-white/10"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>

                                        {/* Card Content - Full height now since header is overlay */}
                                        <div className="flex-1 overflow-hidden relative w-full h-full">
                                            {renderCardContent(card)}
                                        </div>
                                    </div>
                                );
                            })}
                        </RGLResponsive>

                        {appCards.length === 0 && (
                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                <div className="text-center space-y-2 opacity-30">
                                    <div className="text-4xl font-bold tracking-tighter text-white">BUILDER CANVAS</div>
                                    <p className="text-sm">Select a component from the library to start building</p>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

