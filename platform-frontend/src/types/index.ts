import type { Node, Edge } from 'reactflow';

export type AgentType = 'Planner' | 'Retriever' | 'Thinker' | 'Coder' | 'Executor' | 'Evaluator' | 'Summarizer' | 'User';

export type RunStatus = 'running' | 'completed' | 'failed' | 'paused';

export interface Run {
    id: string;
    name: string;
    createdAt: number;
    status: RunStatus;
    model: string;
    ragEnabled: boolean;
    total_tokens?: number;
}

export interface AgentNodeData {
    label: string;
    type: AgentType | 'Generic';
    status: 'pending' | 'running' | 'completed' | 'failed' | 'waiting_input' | 'stale';
    description?: string;
    prompt?: string;
    agent_prompt?: string; // Explicit field from backend
    reads?: string[];
    writes?: string[];
    cost?: number;
    execution_time?: number | string;
    output?: string;
    error?: string;
    result?: string;
    logs?: string[];
    execution_logs?: string;
    iterations?: any[];
    calls?: any[];
    execution_result?: any;
    isDark?: boolean; // For styling
}

export type PlatformNode = Node<AgentNodeData>;
export type PlatformEdge = Edge;

export interface Snapshot {
    id: string;
    timestamp: number;
    nodeId: string | null;
    chatHistory: ChatMessage[];
    codeContent: string;
    webUrl: string | null;
    webContent: string | null;
    htmlOutput: string | null;
    graphState: {
        nodes: PlatformNode[];
        edges: PlatformEdge[];
    };
}

export interface FileContext {
    name: string;
    path: string;
}

export interface ContextItem {
    id: string;
    text: string;
    file?: string;
    range?: {
        startLine: number;
        endLine: number;
    };
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string | any; // Supports mixed content (thinking)
    contexts?: ContextItem[]; // Attached rich context pills
    fileContexts?: FileContext[]; // Attached file pills
    images?: string[]; // Attached images (base64)క్ష
    timestamp: number;
}

export interface Memory {
    id: string;
    text: string;
    category: string;
    created_at: string;
    updated_at: string;
    source: string;
    source_exists?: boolean;
    faiss_id?: number;
}
export interface RAGDocument {
    id: string;
    title: string;
    type: string;
    content?: string;
    chatHistory?: ChatMessage[];
    targetPage?: number;
    targetLine?: number;  // NEW: Support ripgrep line jumping
    searchText?: string;  // Text to auto-search when opening from SEEK result
    language?: string;    // Programming language for syntax highlighting
    originalContent?: string; // For Git Diffs
    modifiedContent?: string; // For Git Diffs
    isDirty?: boolean; // Track unsaved changes
}
