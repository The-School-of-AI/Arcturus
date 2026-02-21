import React, { useState, useEffect, useCallback } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import SandboxFrame from './SandboxFrame';
import { getWidget } from './WidgetRegistry';

interface CanvasHostProps {
    surfaceId: string;
}

const CanvasHost: React.FC<CanvasHostProps> = ({ surfaceId }) => {
    const [components, setComponents] = useState<any[]>([]);
    const [dataModel, setDataModel] = useState<any>({});
    const [isSandbox, setIsSandbox] = useState(false);
    const [htmlContent, setHtmlContent] = useState('');

    // WebSocket connection to the backend
    const socketUrl = `ws://localhost:8000/api/canvas/ws/${surfaceId}`;

    const { lastJsonMessage, readyState, sendJsonMessage } = useWebSocket(socketUrl, {
        shouldReconnect: (closeEvent) => true,
        reconnectInterval: 3000,
    });

    // PERSISTENCE: Stop clearing local storage on mount. 
    // This allows the whiteboard to keep its local state during internal sidebar navigation
    // while the sync from server handles eventual consistency.
    /*
    useEffect(() => {
        console.log('[Canvas] Cleaning up stale storage for surface:', surfaceId);
        Object.keys(localStorage).forEach(key => {
            if (key.startsWith('excalidraw') || key.includes('arcturus')) {
                localStorage.removeItem(key);
            }
        });
        sessionStorage.clear();
    }, [surfaceId]);
    */

    // Handle incoming messages
    useEffect(() => {
        if (lastJsonMessage) {
            const msg = lastJsonMessage as any;
            console.log('[Canvas] Received message:', msg.type, msg.surfaceId);

            (async () => {
                switch (msg.type) {
                    case 'updateComponents':
                        console.log('[Canvas] Components update count:', msg.components?.length);
                        setComponents(msg.components);
                        setIsSandbox(false);
                        break;
                    case 'updateDataModel':
                        setDataModel((prev: any) => ({ ...prev, ...msg.data }));
                        break;
                    case 'captureSnapshot':
                        await handleCaptureSnapshot();
                        break;
                }
            })();
        }
    }, [lastJsonMessage]);

    const handleCaptureSnapshot = async () => {
        try {
            const { toPng } = await import('html-to-image');
            const node = document.getElementById(`canvas-surface-${surfaceId}`);
            if (node) {
                const dataUrl = await toPng(node, {
                    backgroundColor: '#111827',
                    style: { transform: 'scale(1)' } // Ensure no scaling distortion
                });
                sendJsonMessage({
                    type: 'snapshotResult',
                    surfaceId,
                    snapshot: dataUrl
                });
            }
        } catch (error) {
            console.error('[Canvas] Snapshot failed:', error);
        }
    };

    // Listen for manual save triggers to capture image snapshots
    useEffect(() => {
        const handleTrigger = async (e: any) => {
            console.log('[Canvas] Snapshot trigger received');
            await handleCaptureSnapshot();
        };
        window.addEventListener('arcturus:capture-snapshot', handleTrigger);
        return () => window.removeEventListener('arcturus:capture-snapshot', handleTrigger);
    }, [handleCaptureSnapshot]);

    const handleUserEvent = useCallback((componentId: string, eventType: string, data: any = {}) => {
        sendJsonMessage({
            type: 'user_event',
            surfaceId,
            component_id: componentId,
            event_type: eventType,
            data
        });
    }, [surfaceId, sendJsonMessage]);

    const handleLocalComponentUpdate = useCallback((componentId: string, updates: Partial<any>) => {
        setComponents(prev => prev.map(c =>
            c.id === componentId
                ? { ...c, props: { ...c.props, ...updates } }
                : c
        ));
    }, []);

    const renderComponent = (comp: any) => {
        const Widget = getWidget(comp.component);

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
            <Widget
                key={comp.id}
                {...resolvedProps}
                onClick={() => handleUserEvent(comp.id, 'click')}
                onCodeChange={(code: string) => {
                    handleLocalComponentUpdate(comp.id, { code });
                    handleUserEvent(comp.id, 'change', { code });
                }}
                onDrawingChange={(elements: any, appState: any) => {
                    // Update locally immediately to prevent "revert" during re-render
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
        );
    };

    return (
        <div className="flex flex-col h-full bg-gray-900 text-white rounded-xl overflow-hidden shadow-2xl border border-gray-700">
            <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
                <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${readyState === ReadyState.OPEN ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                        Live Surface: {surfaceId === 'ops-command-v1' ? 'Operations Command' : surfaceId}
                    </span>
                </div>
                <div className="flex space-x-1">
                    <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
                    <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
                    <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
                </div>
            </div>

            <div
                id={`canvas-surface-${surfaceId}`}
                className="flex-1 p-4 overflow-auto bg-gray-900"
            >
                {isSandbox ? (
                    <SandboxFrame
                        html={htmlContent}
                        onEvent={(e) => handleUserEvent('sandbox', e.type, e.data)}
                    />
                ) : (
                    <div className="space-y-4">
                        {components.length > 0 ? (
                            components.filter(c => !components.some(other => other.children?.includes(c.id))).map(renderComponent)
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-gray-500 italic space-y-2">
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
