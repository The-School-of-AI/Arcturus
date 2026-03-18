import React, { useState, useEffect, useCallback } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import SandboxFrame from './SandboxFrame';
import { getWidget } from './WidgetRegistry';
import { GenerateDiagramModal } from './GenerateDiagramModal';
import { useTheme } from '@/components/theme';
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';
import { LayoutTemplate, MoreHorizontal, Trash2, Edit3, Copy } from 'lucide-react';
import axios from 'axios';

interface CanvasHostProps {
    surfaceId: string;
}

const CanvasHost: React.FC<CanvasHostProps> = ({ surfaceId }) => {
    const { theme } = useTheme();
    const selectedCanvasWidgetId = useAppStore((s: any) => s.selectedCanvasWidgetId);
    const selectCanvasWidget = useAppStore((s: any) => s.selectCanvasWidget);
    const [components, setComponents] = useState<any[]>([]);
    const [dataModel, setDataModel] = useState<any>({});
    const [isSandbox, setIsSandbox] = useState(false);
    const [htmlContent, setHtmlContent] = useState('');
    const [htmlTitle, setHtmlTitle] = useState<string | null>(null);
    const [generateModalOpen, setGenerateModalOpen] = useState(false);
    // WebSocket connection to the backend
    const socketUrl = `ws://localhost:8000/api/canvas/ws/${surfaceId}`;

    const { lastJsonMessage, readyState, sendJsonMessage } = useWebSocket(socketUrl, {
        shouldReconnect: (_closeEvent: CloseEvent) => true,
        reconnectInterval: 3000,
    });

    // Handle incoming messages
    useEffect(() => {
        if (lastJsonMessage) {
            const msg = lastJsonMessage as any;
            console.log('[Canvas] Received:', msg);

            switch (msg.type) {
                case 'updateComponents':
                    setComponents(msg.components);
                    setIsSandbox(false); // Switch to widget mode if components are sent
                    break;
                case 'updateDataModel':
                    setDataModel((prev: any) => ({ ...prev, ...msg.data }));
                    break;
                case 'createSurface':
                    // Initialization if needed
                    break;
                case 'evalJS':
                    // If we are in sandbox mode, we'd forward this. 
                    // For widget mode, we might handle it differently.
                    break;
                case 'updateHtml':
                    setHtmlContent(msg.html ?? '');
                    setHtmlTitle(msg.title ?? null);
                    setIsSandbox(true);
                    break;
                default:
                    console.warn('Unknown message type:', msg.type);
            }
        }
    }, [lastJsonMessage]);

    const handleGenerateSuccess = useCallback(async (html: string, title: string) => {
        const res = await fetch(`${API_BASE}/canvas/test-update/${surfaceId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ html, title }),
        });
        if (!res.ok) {
            throw new Error(await res.text());
        }
    }, [surfaceId]);

    const handleUserEvent = useCallback((componentId: string, eventType: string, data: any = {}) => {
        sendJsonMessage({
            type: 'user_event',
            surfaceId,
            component_id: componentId,
            event_type: eventType,
            data
        });
    }, [surfaceId, sendJsonMessage]);

    // Optimistic local update + persist to backend
    const handleLocalComponentUpdate = useCallback(async (componentId: string, propsUpdate: any) => {
        setComponents(prev => {
            const updated = prev.map(c =>
                c.id === componentId
                    ? { ...c, props: { ...c.props, ...propsUpdate } }
                    : c
            );
            // Persist to backend
            axios.post(`${API_BASE}/canvas/test-update/${surfaceId}`, {
                components: updated
            }).catch(err => console.error('[Canvas] Failed to persist update:', err));
            return updated;
        });
    }, [surfaceId]);

    const handleDeleteWidget = useCallback(async (componentId: string) => {
        setComponents(prev => {
            const filtered = prev.filter(c => c.id !== componentId);
            axios.post(`${API_BASE}/canvas/test-update/${surfaceId}`, {
                components: filtered
            }).catch(err => console.error('[Canvas] Failed to delete:', err));
            return filtered;
        });
        selectCanvasWidget(null);
    }, [surfaceId, selectCanvasWidget]);

    const handleRenameWidget = useCallback(async (componentId: string) => {
        const newTitle = window.prompt("New widget title:");
        if (!newTitle) return;
        handleLocalComponentUpdate(componentId, { title: newTitle });
    }, [handleLocalComponentUpdate]);

    const handleDuplicateWidget = useCallback(async (comp: any) => {
        const dupeId = `${comp.component.toLowerCase()}_${Math.random().toString(36).substr(2, 5)}`;
        const dupe = { ...comp, id: dupeId, props: { ...comp.props, title: `${comp.props?.title || comp.component} (copy)` } };
        setComponents(prev => {
            const updated = [...prev, dupe];
            axios.post(`${API_BASE}/canvas/test-update/${surfaceId}`, {
                components: updated
            }).catch(err => console.error('[Canvas] Failed to duplicate:', err));
            return updated;
        });
        selectCanvasWidget(dupeId);
    }, [surfaceId, selectCanvasWidget]);

    const renderComponent = (comp: any) => {
        const Widget = getWidget(comp.component);
        const isSelected = selectedCanvasWidgetId === comp.id;

        // Resolve props if they reference the data model (e.g., "$ref:path.to.data")
        const resolvedProps = { ...comp.props };
        Object.keys(resolvedProps).forEach(key => {
            const val = resolvedProps[key];
            if (typeof val === 'string' && val.startsWith('$ref:')) {
                const path = val.replace('$ref:', '');
                resolvedProps[key] = dataModel[path] || val;
            }
        });

        return (
            <div
                key={comp.id}
                onClick={(e) => { e.stopPropagation(); selectCanvasWidget(comp.id); }}
                className={`group/widget relative transition-all ${isSelected ? 'ring-2 ring-primary/60 rounded-lg' : ''}`}
            >
                {/* Per-widget action menu */}
                <div className={`absolute top-1 right-1 z-20 flex items-center gap-0.5 rounded-md bg-background/90 border border-border/60 shadow-sm px-0.5 py-0.5 transition-opacity ${isSelected ? 'opacity-100' : 'opacity-0 group-hover/widget:opacity-100'}`}>
                    <button onClick={(e) => { e.stopPropagation(); handleRenameWidget(comp.id); }} className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors" title="Rename">
                        <Edit3 className="w-3 h-3" />
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); handleDuplicateWidget(comp); }} className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors" title="Duplicate">
                        <Copy className="w-3 h-3" />
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); handleDeleteWidget(comp.id); }} className="p-1 rounded hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-colors" title="Delete">
                        <Trash2 className="w-3 h-3" />
                    </button>
                    <span className="text-[8px] font-mono text-muted-foreground/50 px-1 border-l border-border/40">{comp.component}</span>
                </div>
                <Widget
                    {...resolvedProps}
                    onClick={() => handleUserEvent(comp.id, 'click')}
                    onCodeChange={(code: string) => {
                        handleLocalComponentUpdate(comp.id, { code });
                        handleUserEvent(comp.id, 'change', { code });
                    }}
                    onDrawingChange={(elements: any, appState: any) => {
                        handleLocalComponentUpdate(comp.id, { elements, appState });
                        handleUserEvent(comp.id, 'drawing_change', { elements, appState });
                    }}
                    onTaskUpdate={(tasks: any[]) => {
                        handleLocalComponentUpdate(comp.id, { initialTasks: tasks });
                        handleUserEvent(comp.id, 'kanban_update', { initialTasks: tasks });
                    }}
                >
                    {comp.children?.map((childId: string) => {
                        const child = components.find(c => c.id === childId);
                        return child ? renderComponent(child) : null;
                    })}
                </Widget>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-full bg-card text-card-foreground rounded-xl overflow-hidden shadow-sm border border-border">
            <div className="flex items-center justify-between px-4 py-2 bg-muted/50 border-b border-border">
                <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${readyState === ReadyState.OPEN ? 'bg-green-500' : 'bg-destructive'}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                        Surface: {surfaceId}
                        {isSandbox && htmlTitle ? ` - ${htmlTitle}` : ''}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={() => setGenerateModalOpen(true)}
                        className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-primary/10 hover:bg-primary/20 text-primary border border-border text-xs font-medium uppercase tracking-wider transition-colors"
                        title="Generate diagram"
                    >
                        <LayoutTemplate className="w-3.5 h-3.5" />
                        Generate diagram
                    </button>
                    <div className="flex space-x-1">
                        <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/30" />
                        <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/30" />
                        <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/30" />
                    </div>
                </div>
            </div>
            <GenerateDiagramModal
                open={generateModalOpen}
                onClose={() => setGenerateModalOpen(false)}
                onSuccess={handleGenerateSuccess}
            />

            <div className="flex-1 p-4 overflow-auto bg-background/30">
                {isSandbox ? (
                    <SandboxFrame
                        html={htmlContent}
                        theme={theme}
                        onEvent={(e) => handleUserEvent('sandbox', e.type, e.data)}
                    />
                ) : (
                    <div className="space-y-4">
                        {components.length > 0 ? (
                            components.filter(c => !components.some(other => other.children?.includes(c.id))).map(renderComponent)
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-muted-foreground italic space-y-2">
                                <svg className="w-12 h-12 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                                <span>Awaiting Agent instructions...</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default CanvasHost;
