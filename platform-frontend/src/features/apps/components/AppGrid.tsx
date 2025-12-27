import React, { useState, useCallback, useRef, useEffect } from 'react';
import { ResponsiveGridLayout as RGLResponsiveBase } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

// Cast to any to allow legacy props that types don't include
const RGLResponsive = RGLResponsiveBase as any;
import { Maximize2, Minimize2, Trash2, Save, Plus, RotateCcw, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { getDefaultData, getDefaultStyle } from '../utils/defaults';
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
import {
    StatsTrendingCard,
    StatsGridCard,
    StatsStatusCard,
    StatsLinksCard,
    SimpleTableCard,
    Stats01Card,
    UsageStatsCard,
    StorageCard,
    AccordionTableCard
} from './cards/BlocksCards';
import {
    CheckboxCard,
    SwitchCard,
    RadioGroupCard,
    SliderCard,
    TagsInputCard,
    TextareaCard,
    NumberInputCard,
    ColorPickerCard,
    RatingCard,
    TimePickerCard
} from './cards/ControlCards';


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
    const CANVAS_WIDTH = 1200; // Fixed large canvas width
    const [zoomLevel, setZoomLevel] = useState(1);

    // Connect to Store
    const {
        appCards,
        appLayout,
        selectedAppCardId,
        addAppCard,
        setAppLayout,
        selectAppCard,
        removeAppCard,
        editingAppId,
        savedApps,
        createNewApp,
        saveApp,
        revertAppChanges,
        isAppViewMode,
        updateAppCardData
    } = useAppStore();

    const activeApp = savedApps.find(a => a.id === editingAppId);

    // Handle keyboard delete
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.key === 'Delete' || e.key === 'Backspace') &&
                selectedAppCardId &&
                !(document.activeElement instanceof HTMLInputElement) &&
                !(document.activeElement instanceof HTMLTextAreaElement)) {
                removeAppCard(selectedAppCardId);
            }
        };

        window.addEventListener('keydown', handleKeyDown);

        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [selectedAppCardId, removeAppCard]);

    // Handle drop from external drag (sidebar components)
    const onDrop = (layout: any, layoutItem: any, _event: Event) => {
        console.log('onDrop triggered', { layout, layoutItem, _event });
        const event = _event as DragEvent;
        const data = event.dataTransfer?.getData('application/json');
        console.log('Drop data:', data);
        if (!data) return;

        try {
            const { type, label } = JSON.parse(data);
            const newId = `${type}-${Date.now()}`;

            // Get smart dimensions
            const dims = getSmartDimensions(type);

            // Create new card with default style
            const newCard = {
                id: newId,
                type,
                label,
                config: {},
                data: getDefaultData(type),
                style: getDefaultStyle()
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
        const { id, type, label, config = {}, data = {}, style = {} } = card;

        // Callback to update card data (interactive mode)
        const onUpdate = (newData: any) => {
            updateAppCardData(id, newData);
        };

        // Common props to pass to all cards
        const commonProps = { config, data, style, onUpdate, isInteractive: isAppViewMode };

        // Match with sidebar types
        switch (type) {
            // Basics
            case 'header':
                if (config.showTitle === false) return null;
                return (
                    <div className="p-4" style={{ color: style.textColor }}>
                        <h1 className={cn("text-2xl font-bold", config.centered && "text-center")} style={{ fontWeight: config.bold !== false ? 'bold' : 'normal' }}>
                            {data.text || label}
                        </h1>
                    </div>
                );
            case 'text':
                return (
                    <div className="p-4 text-sm" style={{ color: style.textColor || '#9ca3af' }}>
                        {data.text || 'Basic paragraph text block. Select to edit.'}
                    </div>
                );
            case 'markdown':
                return <MarkdownCard content={data.content} {...commonProps} />;
            case 'image':
                return <ImageCard title={label} {...commonProps} />;
            case 'spacer':
                return <div className="w-full h-full" />;
            case 'divider':
                return <DividerCard {...commonProps} />;

            // Charts & Data
            case 'metric':
                return (
                    <MetricCard
                        title={config.showTitle !== false ? label : ''}
                        value={data.value || '2.4M'}
                        change={config.showPercent !== false ? (data.change || 12.5) : undefined}
                        trend={config.showTrend !== false ? (data.trend || 'up') : undefined}
                        {...commonProps}
                    />
                );
            case 'trend':
                return (
                    <TrendMetric
                        title={config.showTitle !== false ? label : ''}
                        value={data.value || '$145.2'}
                        change={config.showChange !== false ? (data.change || 2.4) : undefined}
                        showSparkline={config.showSparkline !== false}
                        {...commonProps}
                    />
                );
            case 'line_chart':
                return <ChartCard title={config.showTitle !== false ? label : ''} type="line" {...commonProps} />;
            case 'bar_chart':
                return <ChartCard title={config.showTitle !== false ? label : ''} type="bar" {...commonProps} />;
            case 'area_chart':
                return <ChartCard title={config.showTitle !== false ? label : ''} type="area" {...commonProps} />;
            case 'pie_chart':
                return <PieChartCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'candlestick':
                return <CandlestickCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'table':
                return <TableCard title={config.showTitle !== false ? label : ''} {...commonProps} />;

            // Finance
            case 'profile':
                return (
                    <ProfileCard
                        showLogo={config.showLogo !== false}
                        showTicker={config.showTicker !== false}
                        showDescription={config.showDescription !== false}
                        showSector={config.showSector !== false}
                        config={config}
                        data={data}
                        style={style}
                    />
                );
            case 'valuation':
                return (
                    <ValuationGauge
                        title={config.showTitle !== false ? label : ''}
                        marketPrice={data.marketPrice}
                        fairValue={data.fairValue}
                        showPrices={config.showPrices !== false}
                        showGauge={config.showGauge !== false}
                        showLabel={config.showLabel !== false}
                        config={config}
                        style={style}
                    />
                );
            case 'score_card':
                return (
                    <ScoreCard
                        title={config.showTitle !== false ? label : ''}
                        score={data.score || 78}
                        subtext={data.subtext || 'Healthy'}
                        {...commonProps}
                    />
                );
            case 'grade_card':
                return (
                    <GradeCard
                        title={config.showTitle !== false ? label : ''}
                        grade={data.grade || 'A-'}
                        subtext={data.subtext || 'Top Tier'}
                        {...commonProps}
                    />
                );
            case 'peer_table':
                return <PeerTableCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'ratios':
                // Transform ratios data array into table format
                const ratiosData = data.ratios || [];
                const ratiosHeaders = ["Ratio", "Value", "Health"];
                const ratiosRows = ratiosData.map((r: any) => [r.name || '', String(r.value || ''), r.status || '']);
                return <TableCard title={config.showTitle !== false ? label : 'Key Ratios'} headers={ratiosHeaders} rows={ratiosRows.length > 0 ? ratiosRows : [["P/E", "24.5", "Fair"]]} {...commonProps} />;
            case 'summary':
                return <SummaryGrid title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'cash_flow':
            case 'balance_sheet':
            case 'income_stmt':
                return <TableCard title={config.showTitle !== false ? label : ''} {...commonProps} />;

            // Controls
            case 'button':
                return <ActionButtonCard label={label} {...commonProps} />;
            case 'input':
                return <InputCard label={label} {...commonProps} />;
            case 'select':
                return <SelectCard label={label} {...commonProps} />;
            case 'date_picker':
                return <DateRangeCard label={label} {...commonProps} />;

            // New Building Blocks
            case 'checkbox':
                return <CheckboxCard label={label} {...commonProps} />;
            case 'switch':
                return <SwitchCard label={label} {...commonProps} />;
            case 'radio_group':
                return <RadioGroupCard label={label} {...commonProps} />;
            case 'slider':
                return <SliderCard label={label} {...commonProps} />;
            case 'tags_input':
                return <TagsInputCard label={label} {...commonProps} />;
            case 'textarea':
                return <TextareaCard label={label} {...commonProps} />;
            case 'number_input':
                return <NumberInputCard label={label} {...commonProps} />;
            case 'color_picker':
                return <ColorPickerCard label={label} {...commonProps} />;
            case 'rating':
                return <RatingCard label={label} {...commonProps} />;
            case 'time_picker':
                return <TimePickerCard label={label} {...commonProps} />;

            // Dev & Feeds
            case 'feed':
                return <FeedCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'log':
                return <LogStreamCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'json':
                return <JSONViewerCard title={config.showTitle !== false ? label : ''} jsonData={data.json} config={config} style={style} />;
            case 'code':
                return <CodeBlockCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'chat':
                return <div className="p-4 flex flex-col items-center justify-center h-full opacity-20"><span className="text-xs uppercase font-bold">Chat UI Placeholder</span></div>;

            // blocks.so Cards (existing wrappers)
            case 'stats_trending':
                return <StatsTrendingCard title={config.showTitle !== false ? label : 'Key Metrics'} {...commonProps} />;
            case 'stats_grid':
                return <StatsGridCard title={config.showTitle !== false ? label : 'Analytics'} {...commonProps} />;
            case 'stats_status':
                return <StatsStatusCard title={config.showTitle !== false ? label : 'System Status'} {...commonProps} />;
            case 'stats_links':
                return <StatsLinksCard title={config.showTitle !== false ? label : 'Quick Links'} {...commonProps} />;
            case 'simple_table':
                return <SimpleTableCard title={config.showTitle !== false ? label : 'Tasks'} {...commonProps} />;

            // blocks.so Data-Bound Cards (new wrappers)
            case 'stats_01':
                return <Stats01Card title={config.showTitle !== false ? label : 'Financial Overview'} {...commonProps} />;
            case 'usage_stats':
                return <UsageStatsCard title={config.showTitle !== false ? label : 'Resource Usage'} {...commonProps} />;
            case 'storage_card':
                return <StorageCard title={config.showTitle !== false ? label : 'Storage Usage'} {...commonProps} />;
            case 'accordion_table':
                return <AccordionTableCard title={config.showTitle !== false ? label : 'Projects'} {...commonProps} />;

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
            {/* Management Toolbar (Top Left) - Hidden in View Mode */}
            {!isAppViewMode && (
                <div className="absolute top-4 left-4 z-50 flex gap-2">
                    {/* Active App Title - Editable */}
                    <div className="flex items-center gap-2 px-3 py-1 bg-charcoal-800/80 backdrop-blur rounded-lg border border-white/10 shadow-lg mr-2 group/title">
                        <FileText className="w-3.5 h-3.5 text-neon-yellow" />
                        <input
                            className="bg-transparent border-none outline-none text-xs font-bold text-foreground w-[150px] focus:ring-1 focus:ring-neon-yellow/30 rounded px-1"
                            value={activeApp ? activeApp.name : "Untitled App"}
                            onChange={(e) => {
                                if (activeApp) {
                                    saveApp(e.target.value);
                                }
                            }}
                            placeholder="App Name..."
                        />
                        {!activeApp && <span className="text-[10px] text-muted-foreground animate-pulse ml-1">(unsaved)</span>}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center bg-charcoal-800/80 backdrop-blur rounded-lg border border-white/10 shadow-lg p-1 gap-1">
                        <button
                            onClick={(e) => { e.stopPropagation(); createNewApp(); }}
                            className="p-1.5 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors rounded"
                            title="New App (Clear Canvas)"
                        >
                            <Plus className="w-4 h-4" />
                        </button>
                        <button
                            onClick={(e) => { e.stopPropagation(); saveApp(); }}
                            className="p-1.5 hover:bg-neon-yellow/10 text-muted-foreground hover:text-neon-yellow transition-colors rounded"
                            title={activeApp ? "Save All Changes" : "Save as New App"}
                        >
                            <Save className="w-4 h-4" />
                        </button>
                        <button
                            onClick={(e) => { e.stopPropagation(); if (confirm("Discard all unsaved changes?")) revertAppChanges(); }}
                            className="p-1.5 hover:bg-red-500/10 text-muted-foreground hover:text-red-400 transition-colors rounded"
                            title="Revert to Last Saved State"
                        >
                            <RotateCcw className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}

            {/* View Controls (Top Right) */}
            <div className="absolute top-4 right-4 z-50 flex gap-2">
                <div className="flex items-center bg-charcoal-800/80 backdrop-blur rounded-lg border border-white/10 shadow-lg mr-2">
                    <button
                        onClick={(e) => { e.stopPropagation(); setZoomLevel(prev => Math.max(0.5, prev - 0.1)); }}
                        className="p-2 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors border-r border-white/10 w-8 h-8 flex items-center justify-center font-bold"
                        title="Zoom Out"
                    >
                        -
                    </button>
                    <span className="px-2 text-[10px] font-bold text-muted-foreground min-w-[3rem] text-center uppercase tracking-tighter">{Math.round(zoomLevel * 100)}%</span>
                    <button
                        onClick={(e) => { e.stopPropagation(); setZoomLevel(prev => Math.min(1.5, prev + 0.1)); }}
                        className="p-2 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors w-8 h-8 flex items-center justify-center font-bold"
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
            <div
                ref={containerRef}
                className="flex-1 overflow-auto p-8 custom-scrollbar bg-grid-dots"
                onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'copy';
                }}
                onDrop={(e) => {
                    // Fallback handler for external drops
                    e.preventDefault();
                    const data = e.dataTransfer?.getData('application/json');
                    console.log('Fallback onDrop triggered on container', data);
                    if (!data) return;

                    try {
                        const { type, label } = JSON.parse(data);
                        const newId = `${type}-${Date.now()}`;
                        const dims = getSmartDimensions(type);

                        const newCard = {
                            id: newId,
                            type,
                            label,
                            config: {},
                            data: getDefaultData(type),
                            style: getDefaultStyle()
                        };

                        // Calculate grid position from mouse coordinates
                        const rect = containerRef.current?.getBoundingClientRect();
                        // Use CANVAS_WIDTH for colWidth calculation
                        const colWidth = CANVAS_WIDTH / 24;
                        const rowHeight = 40;
                        const x = rect ? Math.max(0, Math.floor((e.clientX - rect.left - 32) / colWidth)) : 0;
                        const y = rect ? Math.max(0, Math.floor((e.clientY - rect.top - 32) / rowHeight)) : 0;

                        const adjustedDims = { ...dims, w: dims.w * 2 };
                        addAppCard(newCard, { x, y, ...adjustedDims });
                    } catch (err) {
                        console.error('Fallback drop error:', err);
                    }
                }}
            >
                {!RGLResponsive ? (
                    <div className="flex flex-col items-center justify-center h-full text-red-400 space-y-4">
                        <div className="p-4 bg-red-500/10 rounded-lg border border-red-500/20">
                            <h3 className="font-bold">Library Load Error</h3>
                            <p className="text-xs">Could not load react-grid-layout. Check console for details.</p>
                        </div>
                    </div>
                ) : (
                    <div style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top left', width: `${CANVAS_WIDTH}px` }}>
                        <RGLResponsive
                            className="layout min-h-[500px]"
                            width={CANVAS_WIDTH}
                            layouts={{ lg: appLayout.map(item => ({ ...item, static: isAppViewMode })) }}
                            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                            cols={{ lg: 24, md: 20, sm: 12, xs: 8, xxs: 4 }} // Double columns for finer granularity
                            rowHeight={40} // Reduced rowHeight for finer control (was 60)
                            onLayoutChange={handleLayoutChange}
                            isDroppable={!isAppViewMode}
                            onDrop={onDrop}
                            droppingItem={{ i: 'dropping-placeholder', w: 8, h: 4 }} // Default drop size adjusted for 24 cols
                            draggableHandle={!isAppViewMode ? ".drag-handle" : undefined}
                            isDraggable={!isAppViewMode}
                            isResizable={!isAppViewMode}
                            resizeHandles={['se', 's', 'e']}
                        >
                            {appCards.map(card => {
                                const isSelected = selectedAppCardId === card.id;
                                const isTransparent = ['divider', 'spacer'].includes(card.type);

                                // Get style settings with defaults
                                const cardStyle = card.style || {};
                                const showBorder = cardStyle.showBorder !== false;
                                const borderWidth = cardStyle.borderWidth || 2;
                                const borderColor = cardStyle.borderColor || 'rgba(255,255,255,0.1)';
                                const borderRadius = cardStyle.borderRadius ?? 12;
                                const opacity = (cardStyle.opacity || 100) / 100;
                                // Default to black if not set, transparent only if explicitly set
                                const backgroundColor = cardStyle.backgroundColor || '#000000';
                                const isTransparentBg = backgroundColor === 'transparent';

                                return (
                                    <div
                                        key={card.id}
                                        className={cn(
                                            // Match FlowStepNode styling exactly
                                            "relative flex flex-col overflow-hidden group transition-all duration-500 shadow-2xl",
                                            // Selected state glow - only in edit mode
                                            isSelected && !isAppViewMode && "ring-4 ring-neon-yellow/20 z-50",
                                            // Hover effect for transparent backgrounds
                                            isTransparentBg && !isSelected && !isAppViewMode && "hover:bg-white/5",
                                        )}
                                        style={{
                                            // Apply custom styles
                                            opacity,
                                            borderRadius: card.type === 'divider' ? 0 : borderRadius,
                                            // Border styling
                                            borderWidth: (showBorder || (isSelected && !isAppViewMode)) ? borderWidth : 0,
                                            borderStyle: 'solid',
                                            borderColor: (isSelected && !isAppViewMode) ? '#eaff00' : (showBorder ? borderColor : 'transparent'),
                                            // Background - always apply it
                                            backgroundColor: backgroundColor,
                                        }}
                                        onClick={(e) => {
                                            // Only stop prop if NOT in view mode (to allow selecting).
                                            // In view mode, we want clicks to pass through to inputs/buttons if valid.
                                            // But actually, for standard selects/inputs, we don't need to stop prop on the container
                                            // unless we are selecting the card itself.
                                            if (!isAppViewMode) {
                                                e.stopPropagation();
                                                selectAppCard(card.id);
                                            }
                                        }}
                                    >
                                        {/* Glow effect when selected - match FlowStepNode */}
                                        {isSelected && !isAppViewMode && (
                                            <div
                                                className="absolute inset-0 bg-neon-yellow/5 blur-xl -z-10 animate-pulse"
                                                style={{ borderRadius: borderRadius }}
                                            />
                                        )}

                                        {/* Minimal Drag Handle - Only visible on hover, top-right corner. Hidden in view mode */}
                                        {!isAppViewMode && (
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
                                        )}

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

