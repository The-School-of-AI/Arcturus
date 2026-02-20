import React, { useState, useEffect } from 'react';
import { Excalidraw } from '@excalidraw/excalidraw';

interface WhiteboardWidgetProps {
    elements?: readonly any[];
    appState?: any;
    onDrawingChange?: (elements: readonly any[], appState: any) => void;
    title?: string;
    readOnly?: boolean;
}

const WhiteboardWidget: React.FC<WhiteboardWidgetProps> = ({
    elements: initialElements = [],
    appState: initialAppState = {},
    onDrawingChange,
    title,
    readOnly = false
}) => {
    const [elements, setElements] = useState<readonly any[]>(initialElements);

    // Update elements if they change from props (e.g., from agent update)
    useEffect(() => {
        if (JSON.stringify(initialElements) !== JSON.stringify(elements)) {
            setElements(initialElements);
        }
    }, [initialElements]);

    return (
        <div className="w-full h-[500px] bg-gray-900 rounded-lg overflow-hidden border border-gray-700 shadow-xl flex flex-col">
            {title && (
                <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-300">{title}</h3>
                    {readOnly && <span className="text-[10px] bg-gray-700 px-2 py-0.5 rounded text-gray-400 uppercase">Read Only</span>}
                </div>
            )}
            <div className="flex-1 relative">
                <Excalidraw
                    initialData={{
                        elements: initialElements,
                        appState: { ...initialAppState, viewBackgroundColor: "#111827", theme: "dark" },
                        scrollToContent: true
                    }}
                    viewModeEnabled={readOnly}
                    onChange={(els, state) => {
                        setElements(els);
                        if (!readOnly) {
                            onDrawingChange?.(els, state);
                        }
                    }}
                    theme="dark"
                />
            </div>
        </div>
    );
};

export default WhiteboardWidget;
