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
                default:
                    console.warn('Unknown message type:', msg.type);
            }
        }
    }, [lastJsonMessage]);

    const handleUserEvent = useCallback((componentId: string, eventType: string, data: any = {}) => {
        sendJsonMessage({
            type: 'user_event',
            surfaceId,
            component_id: componentId,
            event_type: eventType,
            data
        });
    }, [surfaceId, sendJsonMessage]);

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
                    <span className="text-xs font-mono uppercase tracking-wider text-gray-400">
                        Surface: {surfaceId}
                    </span>
                </div>
                <div className="flex space-x-1">
                    <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
                    <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
                    <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
                </div>
            </div>

            <div className="flex-1 p-4 overflow-auto">
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
