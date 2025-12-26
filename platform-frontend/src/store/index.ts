import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
    Run,
    PlatformNode,
    PlatformEdge,
    Snapshot,
    RAGDocument,
    ChatMessage,
    Memory,
} from '../types';
import { applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from 'reactflow';
import { api } from '../lib/api';

// --- Slices Types ---

interface RunSlice {
    runs: Run[];
    currentRun: Run | null;
    addRun: (run: Run) => void;
    setCurrentRun: (runId: string) => void;
    updateRunStatus: (input: { id: string, status: Run['status'] }) => void;
    fetchRuns: () => Promise<void>;
    createNewRun: (query: string, model: string) => Promise<void>;
    refreshCurrentRun: () => Promise<void>;
    pollingInterval: ReturnType<typeof setInterval> | null;
    startPolling: (runId: string) => void;
    stopPolling: () => void;
    deleteRun: (runId: string) => Promise<void>;
}

interface GraphSlice {
    nodes: PlatformNode[];
    edges: PlatformEdge[];
    selectedNodeId: string | null;
    setNodes: (nodes: PlatformNode[]) => void;
    setEdges: (edges: PlatformEdge[]) => void;
    onNodesChange: (changes: NodeChange[]) => void;
    onEdgesChange: (changes: EdgeChange[]) => void;
    selectNode: (nodeId: string | null) => void;
}

interface WorkspaceSlice {
    activeTab: 'code' | 'output' | 'web' | 'html';
    setActiveTab: (tab: 'code' | 'output' | 'web' | 'html') => void;
    codeContent: string;
    setCodeContent: (code: string) => void;
    webUrl: string;
    setWebUrl: (url: string) => void;
    logs: string[];
    addLog: (log: string) => void;
}

interface ReplaySlice {
    snapshots: Snapshot[];
    currentSnapshotIndex: number;
    isReplayMode: boolean;
    loadSnapshot: (index: number) => void;
    addSnapshot: (snapshot: Snapshot) => void;
    toggleReplayMode: (active: boolean) => void;
}

interface SettingsSlice {
    apiKey: string;
    setApiKey: (key: string) => void;
    theme: 'dark' | 'light'; // although we force dark mostly
    localModel: string;
    setLocalModel: (model: string) => void;
}

interface RagViewerSlice {
    viewMode: 'graph' | 'rag' | 'explorer';
    setViewMode: (mode: 'graph' | 'rag' | 'explorer') => void;
    sidebarTab: 'runs' | 'rag' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn';
    setSidebarTab: (tab: 'runs' | 'rag' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn') => void;
    openDocuments: RAGDocument[];
    activeDocumentId: string | null;
    openDocument: (doc: RAGDocument) => void;
    closeDocument: (docId: string) => void;
    closeAllDocuments: () => void;
    setActiveDocument: (docId: string) => void;
    ragSearchQuery: string;
    setRagSearchQuery: (query: string) => void;
    ragSearchResults: any[];
    setRagSearchResults: (results: any[]) => void;
    ragKeywordMatches: string[];
    setRagKeywordMatches: (matches: string[]) => void;
    addMessageToDocChat: (docId: string, message: ChatMessage) => void;
    selectedContexts: string[];
    addSelectedContext: (text: string) => void;
    removeSelectedContext: (index: number) => void;
    clearSelectedContexts: () => void;
    selectedMcpServer: string | null;
    setSelectedMcpServer: (server: string | null) => void;
}

interface RemmeSlice {
    memories: Memory[];
    setMemories: (memories: Memory[]) => void;
    fetchMemories: () => Promise<void>;
    addMemory: (text: string, category?: string) => Promise<void>;
    deleteMemory: (id: string) => Promise<void>;
    cleanupDanglingMemories: () => Promise<void>;
}

interface AnalysisHistoryItem {
    id: string;
    name: string;
    path: string;
    timestamp: number;
    type: 'local' | 'github';
    flowData?: any;
}

export interface AppCard {
    id: string;
    type: string;
    label: string;
    config: any;
    data?: any;
    style?: any;
}

export interface SavedApp {
    id: string;
    name: string;
    lastModified: number;
    cards: AppCard[];
    layout: any[];
}

interface AppsSlice {
    appCards: AppCard[];
    appLayout: any[];
    selectedAppCardId: string | null;
    selectedLibraryComponent: any | null; // For sidebar preview
    savedApps: SavedApp[];
    editingAppId: string | null;
    lastSavedState: { cards: AppCard[], layout: any[] } | null;
    setAppCards: (cards: AppCard[]) => void;
    addAppCard: (card: AppCard, layoutItem: any) => void;
    removeAppCard: (id: string) => void;
    updateAppCardConfig: (id: string, config: any) => void;
    updateAppCardStyle: (id: string, style: any) => void;
    updateAppCardData: (id: string, data: any) => void;
    updateAppCardLabel: (id: string, label: string) => void;
    setAppLayout: (layout: any[]) => void;
    selectAppCard: (id: string | null) => void;
    selectLibraryComponent: (component: any | null) => void;
    createNewApp: () => void;
    saveApp: (name?: string) => void;
    loadApp: (id: string) => void;
    revertAppChanges: () => void;
    deleteApp: (id: string) => void;
}

interface ExplorerSlice {
    explorerRootPath: string | null;
    setExplorerRootPath: (path: string | null) => void;
    explorerFiles: any[];
    setExplorerFiles: (files: any[]) => void;
    isAnalyzing: boolean;
    setIsAnalyzing: (analyzing: boolean) => void;
    flowData: any | null;
    setFlowData: (data: any | null) => void;
    selectedExplorerNodeId: string | null;
    setSelectedExplorerNodeId: (id: string | null) => void;
    analysisHistory: AnalysisHistoryItem[];
    addToHistory: (item: Omit<AnalysisHistoryItem, 'id' | 'timestamp'>) => void;
    removeFromHistory: (id: string) => void;
    updateHistoryItem: (path: string, data: Partial<AnalysisHistoryItem>) => void;
}

// --- Store Creation ---

interface AppState extends RunSlice, GraphSlice, WorkspaceSlice, ReplaySlice, SettingsSlice, RagViewerSlice, RemmeSlice, ExplorerSlice, AppsSlice { }

export const useAppStore = create<AppState>()(
    persist(
        (set, get) => ({
            // Runs
            runs: [],
            currentRun: null,
            addRun: (run) => set((state) => ({ runs: [run, ...state.runs] })),
            setCurrentRun: (runId) => {
                const run = get().runs.find((r) => r.id === runId) || null;
                // Reset panel state when switching runs
                set({
                    currentRun: run,
                    selectedNodeId: null,
                    codeContent: '',
                    logs: [],
                    nodes: [],
                    edges: []
                });
                // If run exists, fetch its latest graph immediately
                if (run) {
                    get().refreshCurrentRun();
                }
            },
            updateRunStatus: ({ id, status }) => set((state) => ({
                runs: state.runs.map((r) => r.id === id ? { ...r, status } : r),
                currentRun: state.currentRun?.id === id ? { ...state.currentRun, status } : state.currentRun
            })),

            deleteRun: async (runId) => {
                try {
                    await api.deleteRun(runId);
                    set((state) => ({
                        runs: state.runs.filter((r) => r.id !== runId),
                        currentRun: state.currentRun?.id === runId ? null : state.currentRun
                    }));
                } catch (e) {
                    console.error("Failed to delete run", e);
                }
            },

            // API Actions
            fetchRuns: async () => {
                try {
                    const fetched = await api.getRuns();
                    // Enforce sorting
                    fetched.sort((a, b) => b.createdAt - a.createdAt);
                    set({ runs: fetched });
                } catch (e: any) {
                    console.error("Failed to fetch runs. Check if backend is running at http://localhost:8000 and if CORS is allowed.");
                    if (e.response) {
                        console.error("Response data:", e.response.data);
                        console.error("Response status:", e.response.status);
                    } else if (e.request) {
                        console.error("Request was made but no response received. This often indicates a CORS block or backend offline.");
                    } else {
                        console.error("Error setting up request:", e.message);
                    }
                }
            },

            createNewRun: async (query, model) => {
                try {
                    const res = await api.createRun(query, model);
                    const newRun: Run = {
                        id: res.id,
                        name: res.query,
                        createdAt: Date.now(),
                        status: 'running',
                        model: model,
                        ragEnabled: true
                    };
                    get().addRun(newRun);

                    // Reset Graph State Immediately
                    set({ nodes: [], edges: [], selectedNodeId: null, codeContent: '', logs: [] });

                    get().setCurrentRun(newRun.id);

                    // Start polling
                    get().startPolling(newRun.id);
                } catch (e) {
                    console.error("Failed to create run", e);
                }
            },

            refreshCurrentRun: async () => {
                const runId = get().currentRun?.id;
                if (!runId) return;
                try {
                    const graphData = await api.getRunGraph(runId);
                    set({
                        nodes: graphData.nodes,
                        edges: graphData.edges,
                        isReplayMode: false, // Ensure we are in live mode
                        currentSnapshotIndex: -1
                    });
                } catch (e) {
                    console.error("Failed to refresh graph", e);
                }
            },

            // Polling Logic
            pollingInterval: null,
            startPolling: (runId) => {
                const interval = setInterval(async () => {
                    await get().refreshCurrentRun();
                    // Also refresh the sidebar list to update statuses
                    await get().fetchRuns();
                }, 2000);
                set({ pollingInterval: interval });
            },
            stopPolling: () => {
                const interval = get().pollingInterval;
                if (interval) clearInterval(interval);
                set({ pollingInterval: null });
            },

            // Graph
            nodes: [],
            edges: [],
            selectedNodeId: null,
            setNodes: (nodes) => set({ nodes }),
            setEdges: (edges) => set({ edges }),
            onNodesChange: (changes) => set({
                nodes: applyNodeChanges(changes, get().nodes) as PlatformNode[]
            }),
            onEdgesChange: (changes) => set({
                edges: applyEdgeChanges(changes, get().edges)
            }),
            selectNode: (nodeId) => {
                const node = get().nodes.find(n => n.id === nodeId);
                set({ selectedNodeId: nodeId });

                if (node && node.data) {
                    // Populate panels
                    set({
                        codeContent: node.data.output || '// Waiting for output',
                        logs: [
                            `Status: ${node.data.status}`,
                            `Type: ${node.data.type}`,
                            node.data.error ? `Error: ${node.data.error}` : ''
                        ].filter(Boolean)
                    });
                }
            },

            // Workspace
            activeTab: 'code',
            setActiveTab: (tab) => set({ activeTab: tab }),
            codeContent: '// Agent code will appear here',
            setCodeContent: (code) => set({ codeContent: code }),
            webUrl: '',
            setWebUrl: (url) => set({ webUrl: url }),
            logs: [],
            addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),

            // Replay
            snapshots: [],
            currentSnapshotIndex: -1,
            isReplayMode: false,
            loadSnapshot: (index) => {
                const snapshot = get().snapshots[index];
                if (!snapshot) return;
                set({
                    currentSnapshotIndex: index,
                    nodes: snapshot.graphState.nodes,
                    edges: snapshot.graphState.edges,
                    codeContent: snapshot.codeContent,
                    webUrl: snapshot.webUrl || '',
                    // trigger other UI updates...
                });
            },
            addSnapshot: (snapshot) => set((state) => ({
                snapshots: [...state.snapshots, snapshot],
                currentSnapshotIndex: state.snapshots.length // pointing to new one
            })),
            toggleReplayMode: (active) => set({ isReplayMode: active }),

            // Settings
            apiKey: '',
            setApiKey: (key) => set({ apiKey: key }),
            theme: 'dark',
            localModel: 'mistral:latest',
            setLocalModel: (model) => set({ localModel: model }),

            // RAG Viewer
            viewMode: 'graph',
            setViewMode: (mode) => set({ viewMode: mode }),
            openDocuments: [],
            activeDocumentId: null,
            openDocument: (doc) => {
                const alreadyOpen = get().openDocuments.find(d => d.id === doc.id);
                if (!alreadyOpen) {
                    set(state => ({
                        openDocuments: [...state.openDocuments, doc],
                        viewMode: 'rag',
                        activeDocumentId: doc.id
                    }));
                } else {
                    set({ activeDocumentId: doc.id, viewMode: 'rag' });
                }
            },
            closeDocument: (docId) => {
                const newDocs = get().openDocuments.filter(d => d.id !== docId);
                let newActiveId = get().activeDocumentId;
                if (newActiveId === docId) {
                    newActiveId = newDocs.length > 0 ? newDocs[newDocs.length - 1].id : null;
                }
                set({
                    openDocuments: newDocs,
                    activeDocumentId: newActiveId,
                    viewMode: newDocs.length === 0 ? 'graph' : 'rag'
                });
            },
            closeAllDocuments: () => set({
                openDocuments: [],
                activeDocumentId: null,
                viewMode: 'graph'
            }),
            setActiveDocument: (docId) => set({ activeDocumentId: docId, viewMode: 'rag' }),
            sidebarTab: 'runs',
            setSidebarTab: (tab) => set({ sidebarTab: tab }),
            ragSearchQuery: '',
            setRagSearchQuery: (query) => set({ ragSearchQuery: query }),
            ragSearchResults: [],
            setRagSearchResults: (results) => set({ ragSearchResults: results }),
            ragKeywordMatches: [],
            setRagKeywordMatches: (matches) => set({ ragKeywordMatches: matches }),
            addMessageToDocChat: (docId, message) => set((state) => ({
                openDocuments: state.openDocuments.map((doc) =>
                    doc.id === docId
                        ? { ...doc, chatHistory: [...(doc.chatHistory || []), message] }
                        : doc
                )
            })),
            selectedContexts: [],
            addSelectedContext: (text) => set((state) => ({
                selectedContexts: [...state.selectedContexts, text]
            })),
            removeSelectedContext: (index) => set((state) => ({
                selectedContexts: state.selectedContexts.filter((_, i) => i !== index)
            })),
            clearSelectedContexts: () => set({ selectedContexts: [] }),
            selectedMcpServer: null,
            setSelectedMcpServer: (server) => set({ selectedMcpServer: server, sidebarTab: 'mcp' }),

            // --- Remme Slice ---
            memories: [],
            setMemories: (memories) => set({ memories }),
            fetchMemories: async () => {
                try {
                    const res = await api.get('http://localhost:8000/remme/memories');
                    set({ memories: res.data.memories });
                } catch (e) {
                    console.error("Failed to fetch memories", e);
                }
            },
            addMemory: async (text, category = "general") => {
                try {
                    await api.post('http://localhost:8000/remme/add', { text, category });
                    get().fetchMemories();
                } catch (e) {
                    console.error("Failed to add memory", e);
                }
            },
            deleteMemory: async (id) => {
                try {
                    await api.delete(`http://localhost:8000/remme/memories/${id}`);
                    get().fetchMemories();
                } catch (e) {
                    console.error("Failed to delete memory", e);
                }
            },
            cleanupDanglingMemories: async () => {
                try {
                    await api.post('http://localhost:8000/remme/cleanup_dangling');
                    get().fetchMemories();
                } catch (e) {
                    console.error("Failed to cleanup dangling memories", e);
                }
            },

            // --- Explorer Slice ---
            explorerRootPath: null,
            setExplorerRootPath: (path) => set({ explorerRootPath: path }),
            explorerFiles: [],
            setExplorerFiles: (files) => set({ explorerFiles: files }),
            isAnalyzing: false,
            setIsAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),
            flowData: null,
            setFlowData: (data) => set({ flowData: data, viewMode: 'explorer' }),
            selectedExplorerNodeId: null,
            setSelectedExplorerNodeId: (id) => set({ selectedExplorerNodeId: id }),
            analysisHistory: [],
            addToHistory: (item) => set((state) => {
                const newItem: AnalysisHistoryItem = {
                    ...item,
                    id: Math.random().toString(36).substr(2, 9),
                    timestamp: Date.now()
                };
                // Pre-filter duplicates
                const filtered = state.analysisHistory.filter(h => h.path !== item.path);
                return { analysisHistory: [newItem, ...filtered].slice(0, 10) };
            }),
            removeFromHistory: (id) => set((state) => ({
                analysisHistory: state.analysisHistory.filter(h => h.id !== id)
            })),
            updateHistoryItem: (path, data) => set((state) => ({
                analysisHistory: state.analysisHistory.map(h =>
                    h.path === path ? { ...h, ...data } : h
                )
            })),

            // --- Apps Slice ---
            appCards: [],
            appLayout: [],
            selectedAppCardId: null,
            selectedLibraryComponent: null,
            savedApps: [],
            editingAppId: null,
            lastSavedState: null,
            setAppCards: (appCards) => set({ appCards }),
            addAppCard: (card, layoutItem) => set((state) => ({
                appCards: [...state.appCards, card],
                appLayout: [...state.appLayout, { ...layoutItem, i: card.id }],
                selectedAppCardId: card.id
            })),
            removeAppCard: (id) => set((state) => ({
                appCards: state.appCards.filter(c => c.id !== id),
                appLayout: state.appLayout.filter(l => l.i !== id),
                selectedAppCardId: state.selectedAppCardId === id ? null : state.selectedAppCardId
            })),
            updateAppCardConfig: (id, config) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, config: { ...c.config, ...config } } : c)
            })),
            updateAppCardStyle: (id, style) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, style: { ...c.style, ...style } } : c)
            })),
            updateAppCardData: (id, data) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, data: { ...c.data, ...data } } : c)
            })),
            updateAppCardLabel: (id, label) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, label } : c)
            })),
            setAppLayout: (appLayout) => set({ appLayout }),
            selectAppCard: (id) => set({ selectedAppCardId: id, selectedLibraryComponent: null }), // Clear lib selection when canvas card selected
            selectLibraryComponent: (component) => set({ selectedLibraryComponent: component, selectedAppCardId: null }), // Clear canvas selection when lib item selected

            createNewApp: () => set({
                appCards: [],
                appLayout: [],
                editingAppId: null,
                lastSavedState: null,
                selectedAppCardId: null
            }),

            saveApp: (name) => set((state) => {
                if (state.editingAppId) {
                    // Update existing
                    const updatedApps = state.savedApps.map(app =>
                        app.id === state.editingAppId
                            ? { ...app, name: name || app.name, cards: state.appCards, layout: state.appLayout, lastModified: Date.now() }
                            : app
                    );
                    return {
                        savedApps: updatedApps,
                        lastSavedState: { cards: state.appCards, layout: state.appLayout }
                    };
                } else {
                    // Create new
                    const newApp: SavedApp = {
                        id: Math.random().toString(36).substr(2, 9),
                        name: name || 'Untitled App',
                        lastModified: Date.now(),
                        cards: state.appCards,
                        layout: state.appLayout
                    };
                    return {
                        savedApps: [newApp, ...state.savedApps],
                        editingAppId: newApp.id,
                        lastSavedState: { cards: state.appCards, layout: state.appLayout }
                    };
                }
            }),

            loadApp: (id) => set((state) => {
                const app = state.savedApps.find(a => a.id === id);
                if (app) {
                    return {
                        appCards: app.cards,
                        appLayout: app.layout,
                        editingAppId: id,
                        lastSavedState: { cards: app.cards, layout: app.layout },
                        selectedAppCardId: null
                    };
                }
                return state;
            }),

            revertAppChanges: () => set((state) => {
                if (state.lastSavedState) {
                    return {
                        appCards: state.lastSavedState.cards,
                        appLayout: state.lastSavedState.layout,
                        selectedAppCardId: null
                    };
                } else {
                    // If never saved, revert means clear
                    return {
                        appCards: [],
                        appLayout: [],
                        selectedAppCardId: null
                    };
                }
            }),

            deleteApp: (id) => set((state) => ({
                savedApps: state.savedApps.filter(a => a.id !== id),
                editingAppId: state.editingAppId === id ? null : state.editingAppId,
                lastSavedState: state.editingAppId === id ? null : state.lastSavedState
            })),
        }),
        {
            name: 'agent-platform-storage',
            partialize: (state) => ({
                // Only persist user settings, not runs (which should come fresh from API)
                apiKey: state.apiKey,
                localModel: state.localModel,
                viewMode: state.viewMode,
                sidebarTab: state.sidebarTab,
                activeDocumentId: state.activeDocumentId,
                openDocuments: state.openDocuments,
                selectedContexts: state.selectedContexts,
                analysisHistory: state.analysisHistory,
                appCards: state.appCards,
                appLayout: state.appLayout,
                savedApps: state.savedApps,
                editingAppId: state.editingAppId,
                lastSavedState: state.lastSavedState
            }),
        }
    )
);
