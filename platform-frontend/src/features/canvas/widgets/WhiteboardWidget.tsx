import React, { useState, useEffect, useRef } from 'react';
import { Excalidraw, getSceneVersion, WelcomeScreen } from '@excalidraw/excalidraw';
import type { A2UIElement } from './ExcalidrawTransformer';
import { transformToExcalidraw } from './ExcalidrawTransformer';

// IMPORTANT: Excalidraw requires its own CSS to render correctly
import "@excalidraw/excalidraw/index.css";

interface WhiteboardWidgetProps {
    elements?: readonly any[];
    appState?: any;
    onDrawingChange?: (elements: readonly any[], appState: any) => void;
    title?: string;
    readOnly?: boolean;
}

// --- Error Boundary for Widget Isolation ---
class WhiteboardErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean, error?: any }> {
    constructor(props: { children: React.ReactNode }) {
        super(props);
        this.state = { hasError: false };
    }
    static getDerivedStateFromError(error: any) { return { hasError: true, error }; }
    componentDidCatch(error: any, errorInfo: any) {
        console.error("[Whiteboard] Widget crashed:", error, errorInfo);
    }

    handleRecover = () => {
        console.log("[Whiteboard] Manual recovery: Clearing excalidraw storage");
        Object.keys(localStorage).forEach(key => {
            if (key.includes('excalidraw')) localStorage.removeItem(key);
        });
        window.location.reload();
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center h-[600px] bg-gray-900 text-red-400 p-8 text-center border border-red-900/30 rounded-lg">
                    <svg className="w-12 h-12 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <h3 className="text-lg font-bold mb-2">Whiteboard Component Failed</h3>
                    <p className="text-sm opacity-70 mb-2">A critical error occurred while rendering the drawing surface.</p>
                    <p className="text-[10px] font-mono opacity-50 mb-4 px-4 py-2 bg-black/30 rounded max-w-md overflow-hidden">{this.state.error?.toString()}</p>
                    <div className="flex gap-2">
                        <button
                            onClick={() => window.location.reload()}
                            className="px-4 py-2 bg-red-900 text-white rounded text-xs transition-colors"
                        >
                            Reload
                        </button>
                        <button
                            onClick={this.handleRecover}
                            className="px-4 py-2 bg-gray-800 text-gray-300 rounded text-xs transition-colors border border-gray-700"
                        >
                            Reset Component State
                        </button>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

const WhiteboardWidget: React.FC<WhiteboardWidgetProps> = ({
    elements: incomingElements = [],
    appState: incomingAppState = {},
    onDrawingChange,
    title,
    readOnly = false
}) => {
    const excalidrawAPI = useRef<any>(null);
    const isDrawingLocally = useRef<boolean>(false);
    const lastLocalUpdateAt = useRef<number>(0);
    const syncTimeout = useRef<any>(null);
    const lastElementsRef = useRef<readonly any[]>([]);

    // Helper to strip non-serializable or transient state from Excalidraw appState
    const sanitizeAppState = (state: any) => {
        if (!state) return {};
        const {
            // Excalidraw internals that shouldn't be persisted as objects/Maps
            collaborators,
            currentChartType,
            pasteDialog,
            toast,

            // Transient UI state
            exportBackground,
            exportEmbedScene,
            exportWithBlur,
            activeTool,
            openMenu,
            openPopup,
            draggingElement,
            resizingElement,
            multiElement,
            selectionElement,
            isResizing,
            isRotating,
            newElement,
            editingElement,

            ...persistentState
        } = state;
        return persistentState;
    };

    // 1. Determine final elements for initial mount and updates
    const transformElements = (els: readonly any[]) => {
        try {
            if (!els || els.length === 0) {
                return [{
                    id: "dummy-suppressor",
                    type: "rectangle",
                    x: -1000,
                    y: -1000,
                    width: 1,
                    height: 1,
                    strokeColor: "transparent",
                    backgroundColor: "transparent",
                    opacity: 0,
                    version: 1,
                    versionNonce: 1,
                    isDeleted: false,
                }];
            }

            // Check if elements need transformation (abstract A2UI types)
            const needsTransform = els.some(el =>
                el && ['rectangle', 'circle', 'arrow', 'text', 'diamond', 'ellipse'].includes(el.type) &&
                !el.seed
            );

            const transformed = needsTransform
                ? transformToExcalidraw(els as A2UIElement[])
                : els;

            // Always return clones to ensure Excalidraw recognizes changes
            return JSON.parse(JSON.stringify(transformed));
        } catch (err) {
            console.error("[Whiteboard] transformElements error:", err, els);
            throw err;
        }
    };

    const initialElements = transformElements(incomingElements);

    // Synchronize elements and state when they change via props OR when API becomes ready
    useEffect(() => {
        if (!excalidrawAPI.current) return;

        // CRITICAL: Block server updates if we recently drew something locally
        if (isDrawingLocally.current || (Date.now() - lastLocalUpdateAt.current < 1500)) {
            console.log("[Whiteboard] Skipping server sync: local drawing active");
            return;
        }

        try {
            const currentElements = excalidrawAPI.current.getSceneElements();
            const incomingElementsList = incomingElements || [];
            const incomingVersion = getSceneVersion(incomingElementsList);
            const currentVersion = getSceneVersion(currentElements || []);

            const targetTheme = (incomingAppState?.theme as "light" | "dark") || "dark";
            const sanitizedIncomingState = sanitizeAppState(incomingAppState);

            // If we are blank but server has data, or version changed
            const isBlankLocal = currentElements.length <= 1 && currentVersion === 0;
            const hasIncomingData = incomingElementsList.length > 0;

            if (incomingVersion !== currentVersion || (isBlankLocal && hasIncomingData)) {
                console.log(`[Whiteboard] Syncing with server: incoming v${incomingVersion}, local v${currentVersion}`);

                const finalElements = transformElements(incomingElementsList);
                excalidrawAPI.current.updateScene({
                    elements: finalElements,
                    appState: {
                        ...excalidrawAPI.current.getAppState(),
                        ...sanitizedIncomingState,
                        theme: targetTheme,
                        viewModeEnabled: readOnly
                    },
                    commitToHistory: false
                });
            }
        } catch (err) {
            console.error("[Whiteboard] Sync error:", err);
        }
    }, [incomingElements, incomingAppState, readOnly]); // Adding readOnly

    // Diagnostic/Manual Refresh - Ensures we pull the ABSOLUTE LATEST from props
    useEffect(() => {
        (window as any).__EXCALIDRAW_DIAGNOSTIC = {
            api: excalidrawAPI.current,
            lastElements: incomingElements,
            forceUpdate: () => {
                if (excalidrawAPI.current) {
                    console.log('[Whiteboard] FORCE REFRESH: Overwriting scene with props');
                    const final = transformElements(incomingElements);
                    const targetTheme = (incomingAppState.theme as "light" | "dark") || "dark";
                    excalidrawAPI.current.updateScene({
                        elements: final,
                        appState: {
                            ...incomingAppState,
                            theme: targetTheme
                        },
                        commitToHistory: true
                    });
                }
            }
        };
    }, [incomingElements, incomingAppState]);

    // 4. Stable Ref for callback to prevent infinite loops with the unmount flush
    const onDrawingChangeRef = useRef(onDrawingChange);
    useEffect(() => {
        onDrawingChangeRef.current = onDrawingChange;
    }, [onDrawingChange]);

    // 5. Flush on unmount to prevent loss during navigation
    useEffect(() => {
        return () => {
            if (syncTimeout.current) {
                clearTimeout(syncTimeout.current);
                // Synchronous-ish flush: if we have an API, get current state and call onDrawingChange
                if (excalidrawAPI.current) {
                    const els = excalidrawAPI.current.getSceneElements();
                    const state = excalidrawAPI.current.getAppState();
                    const persistentState = sanitizeAppState(state);
                    console.log("[Whiteboard] UNMOUNT FLUSH: Sending final state before navigation");
                    onDrawingChangeRef.current?.(els, persistentState);
                }
            }
        };
    }, []); // Only run once on mount, flush on unmount

    const handleDrawingChange = (els: readonly any[], state: any) => {
        if (readOnly) return;

        // Detect active drawing to block incoming sync
        const active = state.isResizing || state.isRotating || state.draggingElement || state.editingElement || state.newElement;
        isDrawingLocally.current = active;
        if (active) lastLocalUpdateAt.current = Date.now();

        // Only emit if something meaningful changed
        const currentLocalVersion = getSceneVersion(els);
        const localVersionKey = `__LAST_VERSION_${title}`;
        const lastKnownVersion = (window as any)[localVersionKey] || 0;

        // Compare essential appState properties
        const lastBg = (window as any)[`__LAST_BG_${title}`];
        const lastTheme = (window as any)[`__LAST_THEME_${title}`];

        // GUARD: If current version is 0 but we previously had a higher version,
        // this is likely an initial mount "blank" render. Do not sync yet.
        const isBlankMount = currentLocalVersion === 0 && lastKnownVersion > 0;

        const stateChanged = !isBlankMount && (
            currentLocalVersion !== lastKnownVersion ||
            state.viewBackgroundColor !== lastBg ||
            state.theme !== lastTheme
        );

        if (stateChanged) {
            (window as any)[localVersionKey] = currentLocalVersion;
            (window as any)[`__LAST_BG_${title}`] = state.viewBackgroundColor;
            (window as any)[`__LAST_THEME_${title}`] = state.theme;

            if (syncTimeout.current) clearTimeout(syncTimeout.current);
            syncTimeout.current = setTimeout(() => {
                syncTimeout.current = null; // Mark as processed
                lastLocalUpdateAt.current = Date.now();

                const persistentState = sanitizeAppState(state);
                onDrawingChange?.(els, persistentState);
                console.log(`[Whiteboard] Local change (v${currentLocalVersion}) synced. Theme: ${state.theme}`);
            }, 800); // Slightly longer debounce for stability
        }
    };

    const [isSaved, setIsSaved] = useState(false);

    const handleManualSave = () => {
        if (!excalidrawAPI.current) {
            console.warn("[Whiteboard] Save called but API not ready");
            return;
        }

        const els = excalidrawAPI.current.getSceneElements();
        const state = excalidrawAPI.current.getAppState();

        const persistentState = sanitizeAppState(state);

        console.log("[Whiteboard] MANUAL SAVE: Flushing to cloud");
        onDrawingChange?.(els, persistentState);

        // Trigger a visual snapshot capture in the parent
        const event = new CustomEvent('arcturus:capture-snapshot', {
            detail: { surfaceId: (window as any).CURRENT_SURFACE_ID || 'ops-command-v1' }
        });
        window.dispatchEvent(event);

        setIsSaved(true);
        setTimeout(() => setIsSaved(false), 2000);
    };

    return (
        <WhiteboardErrorBoundary>
            <div className={`w-full h-[600px] bg-gray-900 rounded-lg overflow-hidden border border-gray-700 shadow-xl flex flex-col`}>
                {title && (
                    <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold text-gray-300">{title}</h3>
                        </div>

                        {/* Quick Background Presets - Improved UI Visibility */}
                        <div className="flex items-center gap-1.5 px-3 border-x border-gray-700/50">
                            {[
                                { name: 'White', color: '#ffffff' },
                                { name: 'Midnight', color: '#111827' },
                                { name: 'Deep Blue', color: '#1e293b' },
                                { name: 'Charcoal', color: '#374151' },
                                { name: 'Navy', color: '#1e3a8a' }
                            ].map(bg => (
                                <button
                                    key={bg.color}
                                    onClick={() => {
                                        if (excalidrawAPI.current) {
                                            const newTheme = bg.color === '#ffffff' ? 'light' : 'dark';
                                            excalidrawAPI.current.updateScene({
                                                appState: {
                                                    viewBackgroundColor: bg.color,
                                                    theme: newTheme
                                                }
                                            });
                                            // Force a direct update call
                                            handleDrawingChange(excalidrawAPI.current.getSceneElements(), {
                                                ...excalidrawAPI.current.getAppState(),
                                                viewBackgroundColor: bg.color,
                                                theme: newTheme
                                            });
                                        }
                                    }}
                                    title={bg.name}
                                    className={`w-4 h-4 rounded border ${bg.color === '#ffffff' ? 'border-gray-400' : 'border-white/30'} hover:scale-110 transition-transform shadow-md ring-1 ring-black/50`}
                                    style={{ backgroundColor: bg.color }}
                                />
                            ))}
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                id={`save-btn-${title}`}
                                onClick={handleManualSave}
                                className={`flex items-center gap-1.5 text-[10px] px-3 py-1 rounded transition-all border ${isSaved
                                    ? 'bg-green-600/40 text-green-200 border-green-500/50'
                                    : 'bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 hover:text-white border-blue-500/30'
                                    }`}
                            >
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                                </svg>
                                {isSaved ? 'Saved! ✓' : 'Save to Cloud'}
                            </button>
                            <button
                                onClick={() => (window as any).__EXCALIDRAW_DIAGNOSTIC?.forceUpdate()}
                                className="text-[9px] bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-neon-yellow hover:text-white transition-colors border border-neon-yellow/20"
                            >
                                Force Refresh
                            </button>
                            {readOnly && <span className="text-[10px] bg-gray-700 px-2 py-1 rounded text-gray-400 uppercase tracking-tighter">Read Only</span>}
                        </div>
                    </div>
                )}
                <div className="flex-1 relative">
                    <Excalidraw
                        key={title || 'whiteboard'}
                        excalidrawAPI={(api) => {
                            console.log("[Whiteboard] API Initialized");
                            excalidrawAPI.current = api;
                            // Trigger an immediate sync check now that API is ready
                            if (incomingElements && incomingElements.length > 0) {
                                const final = transformElements(incomingElements);
                                const sanitizedState = sanitizeAppState(incomingAppState);
                                api.updateScene({
                                    elements: final,
                                    appState: {
                                        ...sanitizedState,
                                        theme: incomingAppState?.theme || 'dark'
                                    }
                                });
                            }
                        }}
                        initialData={{
                            elements: initialElements,
                            appState: {
                                ...sanitizeAppState(incomingAppState),
                                zenModeEnabled: false,
                                gridSize: 20
                            },
                        }}
                        viewModeEnabled={readOnly}
                        onChange={handleDrawingChange}
                        theme={(incomingAppState.theme as "light" | "dark") || "dark"}
                        UIOptions={{
                            canvasActions: {
                                changeViewBackgroundColor: true,
                                loadScene: false,
                                export: false,
                                saveAsImage: false,
                                saveToActiveFile: false,
                                toggleTheme: true,
                            }
                        }}
                    >
                        <WelcomeScreen />
                    </Excalidraw>
                </div>
            </div>
        </WhiteboardErrorBoundary>
    );
};

export default WhiteboardWidget;
