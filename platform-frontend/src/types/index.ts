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
}

export interface AgentNodeData {
    label: string;
    type: AgentType | 'Generic';
    status: 'pending' | 'running' | 'completed' | 'failed' | 'waiting_input';
    description?: string;
    prompt?: string;
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

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string | any; // Supports mixed content (thinking)
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
}
