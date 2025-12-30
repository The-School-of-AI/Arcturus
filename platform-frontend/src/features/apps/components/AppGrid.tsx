import React, { useState, useCallback, useRef, useEffect } from 'react';
import { ResponsiveGridLayout as RGLResponsiveBase } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

// Cast to any to allow legacy props that types don't include
const RGLResponsive = RGLResponsiveBase as any;
import { Maximize2, Minimize2, Trash2, Save, Plus, RotateCcw, FileText, Eye, Edit, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { getDefaultData, getDefaultStyle } from '../utils/defaults';
import { COMPONENT_CATEGORIES } from './AppsSidebar';
import { MetricCard } from './cards/MetricCard';
import { TrendMetric } from './cards/TrendMetric';
import { ChartCard } from './cards/ChartCard';
import { PieChartCard } from './cards/PieChartCard';
import { SankeyCard } from './cards/SankeyCard';
import { HeatmapCard } from './cards/HeatmapCard';
import { ScatterCard } from './cards/ScatterCard';
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
    AccordionTableCard,
    StatsRowCard,
    PlanOverviewCard,
    TrendCardsCard,
    UsageGaugeCard,
    StorageDonutCard,
    TaskTableCard,
    InventoryTableCard,
    ProjectTableCard,
    AiChatCard,
    ShareDialogCard,
    FileUploadCard,
    FormLayoutCard
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
import {
    QuizMCQCard,
    QuizTFCard,
    QuizMultiCard,
    QuizRatingCard,
    QuizLikertCard,
    QuizNPSCard,
    QuizRankingCard,
    QuizFITBCard,
    QuizFITMBCard,
    QuizNumberCard,
    QuizFormulaCard,
    QuizDateCard,
    QuizEssayCard,
    QuizMatchCard,
    QuizDropdownCard,
    QuizCodeCard,
    QuizUploadCard,
    QuizImageCard,
    QuizTextCard,
    QuizSectionCard,
    QuizMediaCard,
    QuizBranchCard,
    QuizAICard
} from './cards/QuizBlocks';


interface AppGridProps {
    className?: string;
    isFullScreen: boolean;
    onToggleFullScreen: () => void;
}

// Helper for Smart Default Dimensions
const getSmartDimensions = (type: string) => {
    for (const category of COMPONENT_CATEGORIES) {
        const item = category.items.find(i => i.type === type);
        if (item && item.defaultW && item.defaultH) {
            return { w: item.defaultW, h: item.defaultH };
        }
    }
    // Fallback default
    return { w: 4, h: 4 };
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
        setIsAppViewMode,
        updateAppCardData,
        hydrateApp
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
        const commonProps = {
            config,
            data,
            style: { ...style, accentColor: style.accentColor || '#F5C542' },
            onUpdate,
            isInteractive: isAppViewMode
        };

        // Match with sidebar types
        switch (type) {
            // Basics
            case 'header':
                if (config.showTitle === false) return null;
                return (
                    <div className="p-4 h-full flex items-center" style={{ color: style.textColor }}>
                        <h1 className={cn("text-2xl font-bold w-full", config.centered && "text-center")} style={{ fontWeight: config.bold !== false ? 'bold' : 'normal' }}>
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
            case 'sankey':
                return <SankeyCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'scatter':
                return <ScatterCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
            case 'heatmap':
                return <HeatmapCard title={config.showTitle !== false ? label : ''} {...commonProps} />;
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

            // Quiz Blocks
            case 'quiz_mcq':
                return <QuizMCQCard {...commonProps} />;
            case 'quiz_tf':
                return <QuizTFCard {...commonProps} />;
            case 'quiz_multi':
                return <QuizMultiCard {...commonProps} />;
            case 'quiz_rating':
                return <QuizRatingCard {...commonProps} />;
            case 'quiz_likert':
                return <QuizLikertCard {...commonProps} />;
            case 'quiz_nps':
                return <QuizNPSCard {...commonProps} />;
            case 'quiz_ranking':
                return <QuizRankingCard {...commonProps} />;
            case 'quiz_fitb':
                return <QuizFITBCard {...commonProps} />;
            case 'quiz_fitmb':
                return <QuizFITMBCard {...commonProps} />;
            case 'quiz_number':
                return <QuizNumberCard {...commonProps} />;
            case 'quiz_formula':
                return <QuizFormulaCard {...commonProps} />;
            case 'quiz_date':
                return <QuizDateCard {...commonProps} />;
            case 'quiz_essay':
                return <QuizEssayCard {...commonProps} />;
            case 'quiz_match':
                return <QuizMatchCard {...commonProps} />;
            case 'quiz_dropdown':
                return <QuizDropdownCard {...commonProps} />;
            case 'quiz_code':
                return <QuizCodeCard {...commonProps} />;
            case 'quiz_upload':
                return <QuizUploadCard {...commonProps} />;
            case 'quiz_image':
                return <QuizImageCard {...commonProps} />;
            case 'quiz_text':
                return <QuizTextCard {...commonProps} />;
            case 'quiz_section':
                return <QuizSectionCard {...commonProps} />;
            case 'quiz_media':
                return <QuizMediaCard {...commonProps} />;
            case 'quiz_branch':
                return <QuizBranchCard {...commonProps} />;
            case 'quiz_ai':
                return <QuizAICard {...commonProps} />;

            // New Blocks.so Components
            case 'stats_row':
                return <StatsRowCard {...commonProps} />;
            case 'plan_overview':
                return <PlanOverviewCard {...commonProps} />;
            case 'trend_cards':
                return <TrendCardsCard {...commonProps} />;
            case 'usage_gauge':
                return <UsageGaugeCard {...commonProps} />;
            case 'storage_donut':
                return <StorageDonutCard {...commonProps} />;
            case 'task_table':
                return <TaskTableCard {...commonProps} />;
            case 'inventory_table':
                return <InventoryTableCard {...commonProps} />;
            case 'project_table':
                return <ProjectTableCard {...commonProps} />;
            case 'ai_chat':
                return <AiChatCard {...commonProps} />;
            case 'share_dialog':
                return <ShareDialogCard {...commonProps} />;
            case 'file_upload':
                return <FileUploadCard {...commonProps} />;
            case 'form_layout':
                return <FormLayoutCard {...commonProps} />;

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
            className={cn("h-full w-full flex flex-col bg-background relative overflow-hidden", className)}
            onClick={() => selectAppCard(null)} // Auto-deselect on background click
        >
            {/* Management Toolbar (Top Left) - Hidden in View Mode */}
            {!isAppViewMode && (
                <div className="absolute top-4 left-4 z-50 flex gap-2">
                    {/* Actions */}
                    <div className="flex items-center bg-muted/80 backdrop-blur rounded-lg border border-border shadow-lg p-1 gap-1">
                        <button
                            onClick={(e) => { e.stopPropagation(); createNewApp(); }}
                            className="p-1.5 hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors rounded"
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
                {/* PREVIEW / EDIT Mode Toggle - Always visible */}
                <button
                    onClick={(e) => { e.stopPropagation(); setIsAppViewMode(!isAppViewMode); }}
                    className={cn(
                        "flex items-center gap-2 px-3 py-2 rounded-lg border shadow-lg transition-all",
                        isAppViewMode
                            ? "bg-muted/80 backdrop-blur border-border text-muted-foreground hover:text-foreground"
                            : "bg-primary/20 border-primary text-primary"
                    )}
                    title={isAppViewMode ? "Switch to Edit Mode" : "Preview App"}
                >
                    {isAppViewMode ? (
                        <>
                            <Edit className="w-4 h-4" />
                            <span className="text-xs font-bold">EDIT</span>
                        </>
                    ) : (
                        <>
                            <Eye className="w-4 h-4" />
                            <span className="text-xs font-bold">PREVIEW</span>
                        </>
                    )}
                </button>

                {/* Refresh Data Button - Only visible when editing a saved app */}
                {activeApp && (
                    <button
                        onClick={async (e) => {
                            e.stopPropagation();
                            const btn = e.currentTarget;
                            btn.disabled = true;
                            btn.querySelector('.refresh-icon')?.classList.add('animate-spin');
                            btn.querySelector('.refresh-text')!.textContent = 'REFRESHING...';
                            try {
                                await hydrateApp(activeApp.id);  // Use the ID from the loaded JSON
                            } catch (err) {
                                console.error('Hydration failed:', err);
                                alert('Hydration failed. Check console for details.');
                            } finally {
                                btn.disabled = false;
                                btn.querySelector('.refresh-icon')?.classList.remove('animate-spin');
                                btn.querySelector('.refresh-text')!.textContent = 'REFRESH';
                            }
                        }}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border shadow-lg transition-all bg-muted/80 backdrop-blur border-border text-muted-foreground hover:text-foreground hover:border-primary disabled:opacity-50"
                        title="Refresh data using AI based on component contexts"
                    >
                        <RefreshCw className="w-4 h-4 refresh-icon" />
                        <span className="text-xs font-bold refresh-text">ReFETCH</span>
                    </button>
                )}

                <div className="flex items-center bg-muted/80 backdrop-blur rounded-lg border border-border shadow-lg mr-2">
                    <button
                        onClick={(e) => { e.stopPropagation(); setZoomLevel(prev => Math.max(0.5, prev - 0.1)); }}
                        className="p-2 hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors border-r border-border w-6 h-4 flex items-center justify-center font-bold"
                        title="Zoom Out"
                    >
                        -
                    </button>
                    <span className="px-2 text-[10px] font-bold text-muted-foreground min-w-[3rem] text-center uppercase tracking-tighter">{Math.round(zoomLevel * 100)}%</span>
                    <button
                        onClick={(e) => { e.stopPropagation(); setZoomLevel(prev => Math.min(1.5, prev + 0.1)); }}
                        className="p-2 hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors w-6 h-4 flex items-center border-l justify-center font-bold"
                        title="Zoom In"
                    >
                        +
                    </button>
                </div>
                {/* Hide resize button in preview mode */}
                {!isAppViewMode && (
                    <button
                        onClick={(e) => { e.stopPropagation(); onToggleFullScreen(); }}
                        className="p-2 bg-muted/80 backdrop-blur rounded-lg border border-border hover:bg-white/10 transition-colors text-muted-foreground hover:text-foreground shadow-lg"
                        title={isFullScreen ? "Exit Full Screen" : "Full Screen"}
                    >
                        {isFullScreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                    </button>
                )}
            </div>

            {/* Grid Area */}
            <div
                ref={containerRef}
                className="flex-1 overflow-auto px-4 py-16 custom-scrollbar"
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
                    <div
                        style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top left', width: `${CANVAS_WIDTH}px` }}
                        className={cn(!isAppViewMode && "bg-grid-lines")}
                    >
                        <RGLResponsive
                            className="layout min-h-[500px]"
                            width={CANVAS_WIDTH}
                            layouts={{ lg: appLayout.map(item => ({ ...item, static: isAppViewMode })) }}
                            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                            cols={{ lg: 24, md: 24, sm: 24, xs: 24, xxs: 24 }} // Force 24 cols at all breakpoints
                            rowHeight={40} // Reduced rowHeight for finer control (was 60)
                            margin={[16, 16]} // No margin so columns = exactly 50px (1200/24)
                            containerPadding={[0, 0]} // No internal padding
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
                                const showBorder = cardStyle.showBorder === true;
                                const borderWidth = cardStyle.borderWidth || 2;
                                const borderColor = cardStyle.borderColor || 'hsl(var(--border))';
                                const borderRadius = cardStyle.borderRadius ?? 12;
                                const opacity = (cardStyle.opacity || 100) / 100;
                                // Default to card background if not set
                                const backgroundColor = cardStyle.backgroundColor || 'hsl(var(--card))';
                                const isTransparentBg = backgroundColor === 'transparent';

                                return (
                                    <div
                                        key={card.id}
                                        className={cn(
                                            // Match FlowStepNode styling exactly
                                            "relative flex flex-col overflow-hidden group transition-all duration-500",
                                            // Shadow: always in view mode (except divider/spacer), or when border is visible in edit mode
                                            card.type !== 'divider' && card.type !== 'spacer' && (isAppViewMode ? "shadow-lg" : ((showBorder || isSelected) && "shadow-2xl")),
                                            // Selected state glow - only in edit mode
                                            isSelected && !isAppViewMode && "ring-4 ring-neon-yellow/20 z-50",
                                            // Hover effect for transparent backgrounds
                                            isTransparentBg && !isSelected && !isAppViewMode && "hover:bg-white/5",
                                        )}
                                        style={{
                                            // Apply custom styles
                                            opacity,
                                            borderRadius: card.type === 'divider' ? 0 : borderRadius,
                                            // Border styling - completely remove border when not shown
                                            ...(showBorder || (isSelected && !isAppViewMode)) ? {
                                                borderWidth: borderWidth,
                                                borderStyle: 'solid',
                                                borderColor: (isSelected && !isAppViewMode) ? '#F5C542' : borderColor,
                                            } : {
                                                border: 'none',
                                            },
                                            // Background - transparent for divider/spacer, otherwise use card background
                                            backgroundColor: (card.type === 'divider' || card.type === 'spacer') ? 'transparent' : backgroundColor,
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
                                                    className="p-1 bg-muted/80 hover:bg-red-500/20 hover:text-red-400 rounded transition-colors text-muted-foreground border border-border"
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
                                    <div className="text-4xl font-bold tracking-tighter text-foreground">BUILDER CANVAS</div>
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

