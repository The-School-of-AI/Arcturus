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
import { ChartCard } from './cards/ChartCard';
import { ProfileCard } from './cards/ProfileCard';
import { GradeCard } from './cards/GradeCard';
import { ScoreCard } from './cards/ScoreCard';
import { TableCard } from './cards/TableCard';

interface AppGridProps {
    className?: string;
    isFullScreen: boolean;
    onToggleFullScreen: () => void;
}

export const AppGrid: React.FC<AppGridProps> = ({ className, isFullScreen, onToggleFullScreen }) => {
    // Container ref for width measurement
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState(1200);
    
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

    // Placeholder State - eventually moved to a specialized store
    const [layout, setLayout] = useState<any[]>([]);
    const [cards, setCards] = useState<any[]>([]);
    const [selectedCardId, setSelectedCardId] = useState<string | null>(null);

    const onDrop = (layout: any, layoutItem: any, _event: Event) => {
        const event = _event as DragEvent;
        const data = event.dataTransfer?.getData('application/json');
        if (!data) return;

        try {
            const { type, label } = JSON.parse(data);
            const newId = `${type}-${Date.now()}`;

            // Create new card
            const newCard = {
                id: newId,
                type,
                label,
                data: {}
            };

            setCards(prev => [...prev, newCard]);
            setSelectedCardId(newId);

            // Let the grid layout handle the positioning, but ensure we save it
            // layoutItem contains the grid-calculated position
        } catch (e) {
            console.error("Failed to parse drop data", e);
        }
    };

    const handleLayoutChange = (newLayout: any) => {
        setLayout(newLayout);
    };

    return (
        <div className={cn("h-full w-full flex flex-col bg-charcoal-950 relative overflow-hidden", className)}>
            {/* Toolbar Overlay */}
            <div className="absolute top-4 right-4 z-50 flex gap-2">
                <button
                    onClick={onToggleFullScreen}
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
                    <>
                    <RGLResponsive
                        className="layout min-h-[500px]"
                        width={containerWidth}
                        layouts={{ lg: layout }}
                        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                        rowHeight={60}
                        onLayoutChange={handleLayoutChange}
                        draggableHandle=".drag-handle"
                        isDroppable={true}
                        onDrop={onDrop}
                    >
                        {cards.map(card => (
                            <div key={card.id} className={cn(
                                "bg-charcoal-800 rounded-lg border shadow-sm flex flex-col overflow-hidden group transition-colors",
                                selectedCardId === card.id ? "border-primary ring-1 ring-primary/50" : "border-white/5 hover:border-white/20"
                            )}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedCardId(card.id);
                                }}
                            >
                                {/* Card Header / Drag Handle */}
                                <div className="drag-handle h-8 px-3 bg-white/5 border-b border-white/5 flex items-center justify-between cursor-move select-none">
                                    <span className="text-[10px] uppercase font-bold text-muted-foreground truncate">{card.label}</span>
                                    <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setCards(prev => prev.filter(c => c.id !== card.id));
                                            }}
                                            className="p-1 hover:bg-red-500/20 hover:text-red-400 rounded"
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    </div>
                                </div>

                                {/* Card Content */}
                                <div className="flex-1 overflow-hidden relative">
                                    {card.type === 'metric' && <MetricCard title={card.label} value="2.4M" change={12.5} trend="up" />}
                                    {card.type === 'line_chart' && <ChartCard title={card.label} type="line" />}
                                    {card.type === 'bar_chart' && <ChartCard title={card.label} type="bar" />}
                                    {card.type === 'pie_chart' && <ChartCard title={card.label} type="bar" />} {/* Placeholder */}

                                    {card.type === 'profile' && <ProfileCard />}
                                    {card.type === 'valuation' && <GradeCard title={card.label} grade="B+" subtext="Undervalued by 15%" />}
                                    {card.type === 'score_card' && <ScoreCard title={card.label} score={78} subtext="Healthy" />}

                                    {card.type === 'table' && <TableCard title={card.label} />}
                                    {card.type === 'ratios' && <TableCard title="Key Ratios" rows={[["P/E", "24.5", ""], ["PEG", "1.2", ""], ["P/B", "5.4", ""]]} />}

                                    {card.type === 'header' && <div className="p-4"><h1 className="text-2xl font-bold text-foreground">{card.label}</h1></div>}
                                    {card.type === 'text' && <div className="p-4 text-sm text-muted-foreground">Add your text content here. Markdown supported.</div>}
                                    {card.type === 'image' && <div className="w-full h-full bg-black/20 flex items-center justify-center text-muted-foreground text-xs">Image Placeholder</div>}

                                    {/* Default Fallback */}
                                    {!['metric', 'line_chart', 'bar_chart', 'pie_chart', 'profile', 'valuation', 'score_card', 'table', 'ratios', 'header', 'text', 'image'].includes(card.type) && (
                                        <div className="p-4 text-xs text-muted-foreground/50">
                                            {card.type} placeholder
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </RGLResponsive>

                    {cards.length === 0 && (
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div className="text-center space-y-2 opacity-30">
                                <div className="text-4xl font-bold tracking-tighter text-white">BUILDER CANVAS</div>
                                <p className="text-sm">Drag components from the library to start building</p>
                            </div>
                        </div>
                    )}
                    </>
                )}
            </div>
        </div>
    );
};
