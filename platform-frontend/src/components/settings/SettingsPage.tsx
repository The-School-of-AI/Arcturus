import React, { useState, useEffect } from 'react';
import {
    Settings, Cpu, FileText, Brain, Wrench, RotateCcw, Save, AlertTriangle,
    Loader2, RefreshCw, Download, Check, X, Terminal, Code, Play, Bot, CheckCircle2,
    Search, LayoutList, ShieldAlert, MessageSquare, Clock, Layout, Zap, KeyRound, Eye, EyeOff, Dices, Info, Box
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE } from '@/lib/api';
import { useAppStore } from '@/store';
import axios from 'axios';
import { GEMINI_MODELS_FALLBACK, type GeminiModel } from '@/lib/gemini-models';
import { McpPanel } from '@/components/sidebar/McpPanel';
import { McpInspector } from '@/components/mcp/McpInspector';

interface OllamaModel {
    name: string;
    size_gb: number;
    capabilities: string[];
    modified_at: string;
}

interface Prompt {
    name: string;
    filename: string;
    content: string;
    lines: number;
    has_backup?: boolean;
}

interface SettingsData {
    ollama: { base_url: string; timeout: number };
    models: {
        embedding: string;
        semantic_chunking: string;
        image_captioning: string;
        memory_extraction: string;
        insights_provider: string;
    };
    rag: {
        chunk_size: number;
        chunk_overlap: number;
        max_chunk_length: number;
        semantic_word_limit: number;
        top_k: number;
    };
    agent: {
        model_provider: 'gemini' | 'ollama';
        default_model: string;
        overrides?: Record<string, { model_provider: 'gemini' | 'ollama'; model: string }>;
        max_steps: number;
        max_lifelines_per_step: number;
        planning_mode: string;
        rate_limit_interval: number;
        enforce_local_verifier?: boolean;
    };
    remme: { extraction_prompt: string };
    gemini: {
        mode: 'api_key' | 'vertex_ai';
        api_key_env: string;
        vertex_ai: { project: string; location: string };
    };
}

interface ApiKeyDef {
    env: string;
    label: string;
    type: 'secret' | 'url' | 'text';
    configured: boolean;
    preview: string | null;
    generate?: boolean;
    has_default?: boolean;
}

interface ApiKeyGroup {
    label: string;
    keys: ApiKeyDef[];
    configured_count: number;
    total_count: number;
}

type TabId = 'models' | 'rag' | 'agent' | 'ide' | 'prompts' | 'skills' | 'keys' | 'advanced' | 'about' | 'mcp';

const TABS: { id: TabId; label: string; icon: typeof Cpu; description: string }[] = [
    { id: 'models', label: 'Models', icon: Cpu, description: 'Ollama & Gemini model selection' },
    { id: 'rag', label: 'RAG Pipeline', icon: FileText, description: 'Document chunking and search' },
    { id: 'agent', label: 'Agent', icon: Brain, description: 'Execution & Model (Gemini/Ollama)' },
    { id: 'ide', label: 'IDE', icon: Layout, description: 'IDE, Test, and Debugging Agents' },
    { id: 'prompts', label: 'Prompts', icon: Terminal, description: 'Edit agent system prompts' },
    { id: 'skills', label: 'Skills', icon: Zap, description: 'Manage agent skills' },
    { id: 'keys', label: 'API Keys', icon: KeyRound, description: 'Manage tokens & secrets' },
    { id: 'mcp', label: 'MCP Servers', icon: Box, description: 'Model Context Protocol servers' },
    { id: 'advanced', label: 'Advanced', icon: Wrench, description: 'URLs, timeouts, restart' },
    { id: 'about', label: 'About', icon: Info, description: 'Features & reference guide' },
];

const ABOUT_FEATURES = [
    { name: 'Runs', description: 'Start and manage agent task executions. View run history, execution graphs, and token usage.' },
    { name: 'RAG', description: 'Knowledge base manager. Upload, index, and search documents (PDFs, code, text) for agent retrieval.' },
    { name: 'Notes', description: 'Markdown note-taking with folder hierarchy, full-text search, and AI-powered analysis.' },
    { name: 'MCP', description: 'Model Context Protocol server manager. Add external tool servers (from PyPI or GitHub) to extend agent capabilities.' },
    { name: 'RemMe', description: 'Persistent memory and user profiling. Stores facts and preferences the agent learns to personalize behavior.' },
    { name: 'Graph', description: 'Neo4j knowledge graph explorer. Visualize entities and relationships extracted from your memories.' },
    { name: 'Explorer', description: 'Local filesystem browser. Open any folder, browse files with syntax-aware icons, and open them in the IDE.' },
    { name: 'Canvas', description: 'Real-time interactive surface via WebSocket. Agents render React widgets or arbitrary HTML/JS for dynamic UIs.' },
    { name: 'Swarm', description: 'Multi-agent orchestration. Decompose complex tasks across specialized agents (Planner, Coder, Evaluator) running in parallel with a live DAG view.' },
    { name: 'Apps', description: 'Dashboard builder with 60+ widget types (charts, tables, metrics, forms). Drag-and-drop grid layout. Generate apps from agent run reports.' },
    { name: 'IDE', description: 'Full VS Code-style editor with Monaco, terminal, git sidebar, test runner, and AI coding assistant. Includes auto-commit system.' },
    { name: 'Scheduler', description: 'Cron job manager. Automate recurring agent tasks with simple frequency picker or advanced cron expressions.' },
    { name: 'Skills', description: 'Agent plugin system. Browse and install reusable skills from the community store, assign them to specific agents.' },
    { name: 'Forge', description: 'AI document studio. Generate slides, documents, and spreadsheets from prompts. Outline approval, revision history, export to PPTX/DOCX/PDF.' },
    { name: 'Console', description: 'Real-time system event log (Mission Control). Monitor tool calls, agent steps, and errors in a terminal-style view.' },
    { name: 'Echo', description: 'Voice assistant. Say "Hey Arcturus" for hands-free interaction. Supports cloud (Deepgram/Azure) or fully-local (Whisper/Piper) privacy modes.' },
    { name: 'News', description: 'RSS feed reader and web browser. Aggregate feeds, search the web, bookmark articles, and use AI to analyze content.' },
    { name: 'Learn', description: 'Learning resources and tutorials. (Coming soon)' },
    { name: 'Admin', description: 'Watchtower ops dashboard with 10 sub-tabs: Traces, Cost, Errors, Health, Flags, Config, Doctor, Throttle, Audit, Cache.' },
    { name: 'Settings', description: 'System configuration. Models, RAG pipeline, agent behavior, API keys, prompts, skills, and advanced options.' },
];

export const SettingsPage: React.FC = () => {
    const { settingsActiveTab: activeTab, ollamaModels, fetchOllamaModels, setLocalModel } = useAppStore();
    const [settings, setSettings] = useState<SettingsData | null>(null);
    const [prompts, setPrompts] = useState<Prompt[]>([]);
    const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null);
    const [promptContent, setPromptContent] = useState('');
    const [geminiStatus, setGeminiStatus] = useState<{
        configured: boolean;
        mode: string;
        api_key_preview: string | null;
        vertex_project: string | null;
        vertex_location: string;
    } | null>(null);

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [pulling, setPulling] = useState(false);
    const [newModelName, setNewModelName] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [warnings, setWarnings] = useState<string[]>([]);
    const [hasChanges, setHasChanges] = useState(false);

    const [skills, setSkills] = useState<any[]>([]);
    const [assignments, setAssignments] = useState<Record<string, string[]>>({});

    // Gemini models (dynamic from API)
    const [geminiModels, setGeminiModels] = useState<GeminiModel[]>(GEMINI_MODELS_FALLBACK);
    const [geminiModelsLoading, setGeminiModelsLoading] = useState(false);

    // API Keys tab state
    const [apiKeysStatus, setApiKeysStatus] = useState<Record<string, ApiKeyGroup> | null>(null);
    const [apiKeyEdits, setApiKeyEdits] = useState<Record<string, string>>({});
    const [apiKeyVisibility, setApiKeyVisibility] = useState<Record<string, boolean>>({});
    const [savingKeys, setSavingKeys] = useState(false);

    useEffect(() => {
        fetchAll();
        fetchGeminiModels();
    }, []);

    const fetchGeminiModels = async () => {
        setGeminiModelsLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/settings/gemini/models`);
            if (res.data.status === 'success' && res.data.models?.length > 0) {
                setGeminiModels(res.data.models);
            }
        } catch {
            // Keep fallback models
        } finally {
            setGeminiModelsLoading(false);
        }
    };

    const fetchAll = async () => {
        setLoading(true);
        setError(null);
        try {
            const [settingsRes, promptsRes, geminiRes, skillsRes, assignRes, apiKeysRes] = await Promise.all([
                axios.get(`${API_BASE}/settings`),
                axios.get(`${API_BASE}/prompts`),
                axios.get(`${API_BASE}/gemini/status`).catch(() => ({ data: { configured: false, key_preview: null } })),
                axios.get(`${API_BASE}/skills/list`).catch(() => ({ data: { skills: [] } })),
                axios.get(`${API_BASE}/skills/assignments`).catch(() => ({ data: {} })),
                axios.get(`${API_BASE}/apikeys/status`).catch(() => ({ data: { groups: null } })),
            ]);
            await fetchOllamaModels();
            setSettings(settingsRes.data.settings);
            setPrompts(promptsRes.data.prompts || []);
            setGeminiStatus(geminiRes.data);
            setSkills(Array.isArray(skillsRes.data) ? skillsRes.data : []);
            setAssignments(assignRes.data || {});
            setApiKeysStatus(apiKeysRes.data.groups || null);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to load settings');
        } finally {
            setLoading(false);
        }
    };

    const renderSkillsTab = () => (
        <div className="space-y-6">
            <div className="p-4 rounded-lg border border-border bg-muted/20">
                <div className="flex items-center gap-2 mb-2">
                    <Brain className="w-5 h-5 text-purple-400" />
                    <h3 className="font-bold text-lg">Skill Registry</h3>
                </div>
                <p className="text-sm text-muted-foreground mb-4">
                    Skills are specialized capabilities (e.g., Python Coding, Market Analysis) injected into agents based on the task.
                    Add them to <code>config/agent_config.yaml</code> to enable them.
                </p>
                <div className="grid gap-3">
                    {skills.length === 0 ? (
                        <p className="text-sm text-muted-foreground italic">No skills discovered in <code>core/skills/library</code></p>
                    ) : (
                        skills.map((skill: any) => (
                            <div key={skill.name} className="flex items-center justify-between p-3 bg-background border border-border rounded-lg">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-sm">{skill.name}</span>
                                        <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded border border-primary/20">v{skill.version}</span>
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-0.5">{skill.description}</p>
                                </div>
                                <div className="flex flex-col items-end gap-1">
                                    <span className="text-[10px] text-muted-foreground">Triggers:</span>
                                    <div className="flex gap-1">
                                        {skill.intent_triggers.map((t: string) => (
                                            <span key={t} className="text-[9px] bg-muted px-1.5 py-0.5 rounded border border-border">{t}</span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );

    const saveSettings = async () => {
        if (!settings) return;
        setSaving(true);
        setError(null);
        setWarnings([]);
        try {
            const res = await axios.put(`${API_BASE}/settings`, { settings });
            if (res.data.warnings) setWarnings(res.data.warnings);
            setHasChanges(false);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const savePrompt = async () => {
        if (!selectedPrompt) return;
        setSaving(true);
        try {
            const res = await axios.put(`${API_BASE}/prompts/${selectedPrompt.name}`, { content: promptContent });
            // Refresh prompts and update selected
            const promptsRes = await axios.get(`${API_BASE}/prompts`);
            setPrompts(promptsRes.data.prompts || []);
            // Update selectedPrompt to reflect has_backup
            const updated = promptsRes.data.prompts.find((p: Prompt) => p.name === selectedPrompt.name);
            if (updated) setSelectedPrompt(updated);
            setHasChanges(false);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to save prompt');
        } finally {
            setSaving(false);
        }
    };

    const resetPrompt = async () => {
        if (!selectedPrompt) return;
        if (!confirm(`Reset "${selectedPrompt.name}" to original? This will undo all changes.`)) return;
        try {
            const res = await axios.post(`${API_BASE}/prompts/${selectedPrompt.name}/reset`);
            setPromptContent(res.data.content);
            // Refresh prompts
            const promptsRes = await axios.get(`${API_BASE}/prompts`);
            setPrompts(promptsRes.data.prompts || []);
            const updated = promptsRes.data.prompts.find((p: Prompt) => p.name === selectedPrompt.name);
            if (updated) setSelectedPrompt(updated);
            setHasChanges(false);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to reset prompt');
        }
    };

    const pullModel = async () => {
        if (!newModelName.trim()) return;
        setPulling(true);
        setError(null);
        try {
            await axios.post(`${API_BASE}/ollama/pull`, { name: newModelName });
            setNewModelName('');
            // Refresh models via store
            await fetchOllamaModels();
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to pull model');
        } finally {
            setPulling(false);
        }
    };

    const resetSettings = async () => {
        if (!confirm('Reset all settings to defaults? This cannot be undone.')) return;
        try {
            await axios.post(`${API_BASE}/settings/reset`);
            await fetchAll();
            setHasChanges(false);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to reset');
        }
    };

    const restartServer = async () => {
        try {
            const res = await axios.post(`${API_BASE}/settings/restart`);
            // Show manual restart instructions
            alert(`${res.data.message}\n\n${res.data.instructions?.join('\n') || 'Please restart manually.'}`);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to get restart instructions');
        }
    };

    const updateSetting = (section: keyof SettingsData, key: string, value: any) => {
        if (!settings) return;
        setSettings({ ...settings, [section]: { ...settings[section], [key]: value } });
        setHasChanges(true);
    };

    const updateOverride = (agentType: string, provider: 'gemini' | 'ollama', model: string) => {
        if (!settings) return;
        const overrides = { ...(settings.agent.overrides || {}) };
        overrides[agentType] = { model_provider: provider, model };

        setSettings({
            ...settings,
            agent: {
                ...settings.agent,
                overrides
            }
        });
        setHasChanges(true);
    };

    const resetOverride = (agentType: string) => {
        if (!settings || !settings.agent.overrides) return;
        const overrides = { ...settings.agent.overrides };
        delete overrides[agentType];

        setSettings({
            ...settings,
            agent: {
                ...settings.agent,
                overrides
            }
        });
        setHasChanges(true);
    };

    // Get models by capability
    const getModelsByCapability = (cap: string) => ollamaModels.filter(m => m.capabilities.includes(cap));
    const textModels = getModelsByCapability('text');
    const embeddingModels = getModelsByCapability('embedding');
    const visionModels = ollamaModels.filter(m => m.capabilities.includes('image'));

    const ModelSelect: React.FC<{
        label: string;
        description: string;
        value: string;
        options: OllamaModel[];
        onChange: (v: string) => void;
        filterCap?: string;
    }> = ({ label, description, value, options, onChange }) => (
        <div className="space-y-2">
            <div>
                <label className="text-sm font-medium text-foreground">{label}</label>
                <p className="text-xs text-muted-foreground">{description}</p>
            </div>
            <select
                value={value}
                onChange={(e) => { onChange(e.target.value); setHasChanges(true); }}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm"
            >
                {options.length === 0 ? (
                    <option value={value}>{value} (current)</option>
                ) : (
                    options.map((m) => (
                        <option key={m.name} value={m.name}>
                            {m.name} ({m.size_gb}GB) [{m.capabilities.join(', ')}]
                        </option>
                    ))
                )}
            </select>
        </div>
    );

    const renderModelsTab = () => (
        <div className="space-y-6">
            {/* Ollama Status */}
            <div className="p-4 rounded-lg border border-border bg-muted/20">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <h3 className="font-medium text-foreground">Ollama Models</h3>
                        <p className="text-xs text-muted-foreground">{ollamaModels.length} models available locally</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={fetchAll}>
                        <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                    </Button>
                </div>
                {/* Pull New Model */}
                <div className="flex gap-2 mt-2">
                    <Input
                        placeholder="e.g. llama3:8b, gemma2:9b, nomic-embed-text"
                        value={newModelName}
                        onChange={(e) => setNewModelName(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && pullModel()}
                        className="flex-1"
                    />
                    <Button onClick={pullModel} disabled={pulling || !newModelName.trim()}>
                        {pulling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4 mr-1" />}
                        Pull Model
                    </Button>
                </div>
            </div>

            <ModelSelect
                label="Embedding Model"
                description="Used for document indexing and semantic search (needs embedding capability)"
                value={settings?.models.embedding || ''}
                options={embeddingModels}
                onChange={(v) => updateSetting('models', 'embedding', v)}
            />
            <ModelSelect
                label="Semantic Chunking Model"
                description="LLM for intelligent document splitting"
                value={settings?.models.semantic_chunking || ''}
                options={textModels}
                onChange={(v) => updateSetting('models', 'semantic_chunking', v)}
            />
            <ModelSelect
                label="Image Captioning Model"
                description="Vision model for extracting text from images (needs vision capability)"
                value={settings?.models.image_captioning || ''}
                options={visionModels.length > 0 ? visionModels : textModels}
                onChange={(v) => updateSetting('models', 'image_captioning', v)}
            />
            <ModelSelect
                label="Memory Extraction Model"
                description="Model for RemMe memory extraction"
                value={settings?.models.memory_extraction || ''}
                options={textModels}
                onChange={(v) => updateSetting('models', 'memory_extraction', v)}
            />

            {/* Gemini Mode & Status */}
            <SettingGroup title="Gemini Provider" description="Choose between API key (Developer API) or Vertex AI (Google Cloud)">
                <div className="space-y-3">
                    <select
                        value={settings?.gemini?.mode || 'api_key'}
                        onChange={(e) => {
                            if (!settings) return;
                            const mode = e.target.value as 'api_key' | 'vertex_ai';
                            setSettings({
                                ...settings,
                                gemini: { ...settings.gemini, mode },
                            });
                            setHasChanges(true);
                        }}
                        className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm"
                    >
                        <option value="api_key">Gemini Developer API (API Key)</option>
                        <option value="vertex_ai">Vertex AI (Google Cloud Project)</option>
                    </select>

                    <div className="p-3 rounded-lg border border-border bg-muted/10">
                        <div className="flex items-center gap-2">
                            {geminiStatus?.configured ? (
                                <Check className="w-4 h-4 text-green-500" />
                            ) : (
                                <X className="w-4 h-4 text-red-500" />
                            )}
                            <span className="text-sm font-medium">
                                {geminiStatus?.configured ? 'Connected' : 'Not configured'}
                            </span>
                        </div>
                        {(settings?.gemini?.mode || 'api_key') === 'api_key' ? (
                            <div className="mt-2 text-xs text-muted-foreground space-y-1">
                                {geminiStatus?.api_key_preview ? (
                                    <p>API Key: <span className="font-mono">{geminiStatus.api_key_preview}</span></p>
                                ) : (
                                    <p>Set <span className="font-mono">GEMINI_API_KEY</span> in the API Keys tab or as an environment variable.</p>
                                )}
                            </div>
                        ) : (
                            <div className="mt-2 text-xs text-muted-foreground space-y-1">
                                {geminiStatus?.vertex_project ? (
                                    <p>Project: <span className="font-mono">{geminiStatus.vertex_project}</span> ({geminiStatus?.vertex_location || 'us-central1'})</p>
                                ) : (
                                    <p>Set <span className="font-mono">GOOGLE_CLOUD_PROJECT</span> in the API Keys tab and run <span className="font-mono">gcloud auth application-default login</span>.</p>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </SettingGroup>

            <SettingGroup title="Insights Provider" description="Choose Ollama (local) or Gemini (cloud) for document insights">
                <select
                    value={settings?.models.insights_provider || 'ollama'}
                    onChange={(e) => updateSetting('models', 'insights_provider', e.target.value)}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm"
                >
                    <option value="ollama">Ollama (Local)</option>
                    <option value="gemini" disabled={!geminiStatus?.configured}>
                        Gemini (Cloud) {!geminiStatus?.configured && '- API key required'}
                    </option>
                </select>
            </SettingGroup>
        </div>
    );

    const renderRagTab = () => (
        <div className="space-y-6">
            <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 shrink-0" />
                <p className="text-xs text-yellow-500/90">
                    Changing chunk settings requires re-indexing all documents to take effect.
                </p>
            </div>
            <SettingGroup title="Chunk Size" description="Base number of words per chunk">
                <Input type="number" value={settings?.rag.chunk_size || 256} onChange={(e) => updateSetting('rag', 'chunk_size', parseInt(e.target.value))} />
            </SettingGroup>
            <SettingGroup title="Chunk Overlap" description="Overlapping words between chunks">
                <Input type="number" value={settings?.rag.chunk_overlap || 40} onChange={(e) => updateSetting('rag', 'chunk_overlap', parseInt(e.target.value))} />
            </SettingGroup>
            <SettingGroup title="Max Chunk Length" description="Maximum characters per chunk">
                <Input type="number" value={settings?.rag.max_chunk_length || 512} onChange={(e) => updateSetting('rag', 'max_chunk_length', parseInt(e.target.value))} />
            </SettingGroup>
            <SettingGroup title="Semantic Word Limit" description="Words per block for semantic chunking">
                <Input type="number" value={settings?.rag.semantic_word_limit || 1024} onChange={(e) => updateSetting('rag', 'semantic_word_limit', parseInt(e.target.value))} />
            </SettingGroup>
            <SettingGroup title="Top-K Results" description="Number of search results to return">
                <Input type="number" value={settings?.rag.top_k || 3} onChange={(e) => updateSetting('rag', 'top_k', parseInt(e.target.value))} />
            </SettingGroup>
        </div>
    );

    const renderAgentTab = () => {
        // Get text-capable Ollama models for agent execution
        const ollamaTextModels = ollamaModels.filter(m =>
            m.capabilities.includes('text') && !m.capabilities.includes('embedding')
        );

        // Handle model selection - updates both provider and model atomically
        const handleAgentModelChange = (value: string) => {
            if (!settings) return;

            // Find the first colon to split provider:model
            const colonIndex = value.indexOf(':');
            if (colonIndex === -1) return;

            const provider = value.substring(0, colonIndex);
            const modelName = value.substring(colonIndex + 1);

            if (provider === 'gemini' || provider === 'ollama') {
                // Update both fields in a single state update to prevent stale state issues
                setSettings({
                    ...settings,
                    agent: {
                        ...settings.agent,
                        model_provider: provider as 'gemini' | 'ollama',
                        default_model: modelName
                    }
                });
                setHasChanges(true);
            }
        };

        // Current composite value for the select
        const currentValue = `${settings?.agent.model_provider || 'gemini'}:${settings?.agent.default_model || 'gemini-2.5-flash'}`;

        return (
            <div className="space-y-6">
                <SettingGroup title="Default Agent Model" description="Model used for agent execution (Cloud or Local)">
                    <div className="flex items-center gap-2">
                        <select
                            value={currentValue}
                            onChange={(e) => handleAgentModelChange(e.target.value)}
                            className="flex-1 bg-background border border-border rounded-lg px-3 py-2 text-sm"
                        >
                            {/* Gemini Cloud Models */}
                            <option disabled value="" className="text-muted-foreground font-semibold">
                                {geminiStatus?.mode === 'vertex_ai' ? 'Gemini (Vertex AI)' : 'Gemini (Cloud)'}
                            </option>
                            {geminiModels.map((m) => (
                                <option key={`gemini:${m.value}`} value={`gemini:${m.value}`}>
                                    &nbsp;&nbsp;{m.label} — {m.description}
                                </option>
                            ))}

                            {/* Show current model if not in list */}
                            {settings?.agent.model_provider === 'gemini' &&
                             !geminiModels.some(m => m.value === settings?.agent.default_model) && (
                                <option value={currentValue}>
                                    &nbsp;&nbsp;{settings?.agent.default_model} (custom)
                                </option>
                            )}

                        {/* Ollama Local Models */}
                        {ollamaTextModels.length > 0 && (
                            <>
                                <option disabled value="" className="text-muted-foreground font-semibold">
                                    Ollama (Local)
                                </option>
                                {ollamaTextModels.map((m) => (
                                    <option key={`ollama:${m.name}`} value={`ollama:${m.name}`}>
                                        &nbsp;&nbsp;{m.name} — Local ({m.size_gb}GB)
                                    </option>
                                ))}
                            </>
                        )}
                        </select>
                        <button
                            onClick={fetchGeminiModels}
                            disabled={geminiModelsLoading}
                            className="p-2 rounded-lg border border-border hover:bg-accent transition-colors"
                            title="Refresh available models"
                        >
                            <RefreshCw className={cn("w-4 h-4", geminiModelsLoading && "animate-spin")} />
                        </button>
                    </div>

                    {/* Provider indicator */}
                    <div className="mt-2 flex items-center gap-2 text-xs">
                        {settings?.agent.model_provider === 'ollama' ? (
                            <span className="px-2 py-0.5 rounded bg-green-500/20 text-green-400 border border-green-500/30">
                                Local Execution
                            </span>
                        ) : geminiStatus?.mode === 'vertex_ai' ? (
                            <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 border border-purple-500/30">
                                Vertex AI
                            </span>
                        ) : (
                            <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                Gemini API
                            </span>
                        )}
                        <span className="text-muted-foreground">
                            {settings?.agent.model_provider === 'ollama'
                                ? 'Running on your machine via Ollama'
                                : geminiStatus?.mode === 'vertex_ai'
                                    ? `Vertex AI — ${geminiStatus?.vertex_project || 'project'} (${geminiStatus?.vertex_location || 'us-central1'})`
                                    : 'Using Google Gemini API'}
                        </span>
                    </div>
                </SettingGroup>
                <div className="flex flex-row gap-4 items-start">
                    <SettingGroup title="Max Steps" description="Maximum reasoning steps per agent run">
                        <Input type="number" value={settings?.agent.max_steps || 3} onChange={(e) => updateSetting('agent', 'max_steps', parseInt(e.target.value))} />
                    </SettingGroup>

                    <SettingGroup title="Lifelines per Step" description="Retry attempts on failure">
                        <Input type="number" value={settings?.agent.max_lifelines_per_step || 3} onChange={(e) => updateSetting('agent', 'max_lifelines_per_step', parseInt(e.target.value))} />
                    </SettingGroup>

                    <SettingGroup title="Planning Mode" description="Agent planning strategy">
                        <select value={settings?.agent.planning_mode || 'conservative'} onChange={(e) => updateSetting('agent', 'planning_mode', e.target.value)} className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm">
                            <option value="conservative">Conservative</option>
                            <option value="exploratory">Exploratory</option>
                        </select>
                    </SettingGroup>

                    <div className="flex items-center space-x-2 pt-8">
                        <input
                            type="checkbox"
                            checked={settings?.agent.enforce_local_verifier || false}
                            onChange={(e) => updateSetting('agent', 'enforce_local_verifier', e.target.checked)}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <div>
                            <label className="text-sm font-medium text-foreground">Enforce Local Verifier</label>
                            <p className="text-xs text-muted-foreground">Force "Verifier" role to use local model (Ollama) to save cloud costs.</p>
                        </div>
                    </div>
                </div>

                {/* Per-Agent Overrides */}
                <div className="pt-6 border-t border-border">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-bold text-foreground">Per-Agent Model Overrides</h3>
                        {settings?.agent.overrides && Object.keys(settings.agent.overrides).length > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    if (!settings) return;
                                    setSettings({
                                        ...settings,
                                        agent: {
                                            ...settings.agent,
                                            overrides: {}
                                        }
                                    });
                                    setHasChanges(true);
                                }}
                                className="h-7 px-2 text-[10px] uppercase tracking-wider font-bold text-muted-foreground hover:text-primary hover:bg-primary/10 gap-1.5"
                            >
                                <RotateCcw className="w-3 h-3" />
                                Reset to Globals
                            </Button>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground mb-4">
                        Override the default model for specific agent types. If not set, the default model above is used.
                    </p>

                    <div className="space-y-3">
                        {[
                            { id: "PlannerAgent", icon: LayoutList, color: "text-blue-500" },
                            { id: "RetrieverAgent", icon: Search, color: "text-purple-500" },
                            { id: "ThinkerAgent", icon: Brain, color: "text-pink-500" },
                            { id: "DistillerAgent", icon: FileText, color: "text-orange-500" },
                            { id: "CoderAgent", icon: Code, color: "text-green-500" },
                            { id: "FormatterAgent", icon: LayoutList, color: "text-indigo-500" },
                            { id: "QAAgent", icon: ShieldAlert, color: "text-red-500" },
                            { id: "ClarificationAgent", icon: MessageSquare, color: "text-yellow-500" },
                            { id: "SchedulerAgent", icon: Clock, color: "text-cyan-500" },
                            { id: "optimizer", icon: Zap, color: "text-yellow-600" }
                        ].map(({ id: agentType, icon: Icon, color }) => {
                            const override = settings?.agent.overrides?.[agentType];
                            const overrideValue = override ? `${override.model_provider}:${override.model}` : 'default';

                            const handleOverrideChange = (value: string) => {
                                if (!settings) return;
                                const newOverrides = { ...(settings.agent.overrides || {}) };

                                if (value === 'default') {
                                    delete newOverrides[agentType];
                                } else {
                                    const colonIndex = value.indexOf(':');
                                    const provider = value.substring(0, colonIndex);
                                    const model = value.substring(colonIndex + 1);

                                    newOverrides[agentType] = {
                                        model_provider: provider as 'gemini' | 'ollama',
                                        model
                                    };
                                }

                                setSettings({
                                    ...settings,
                                    agent: {
                                        ...settings.agent,
                                        overrides: newOverrides
                                    }
                                });
                                setHasChanges(true);
                            };

                            return (
                                <div key={agentType} className={cn(
                                    "flex items-center justify-between gap-4 p-3 rounded-lg border transition-all duration-200",
                                    override
                                        ? "border-primary/40 bg-primary/5 shadow-sm"
                                        : "border-border/50 bg-background/30 hover:bg-background/50"
                                )}>
                                    <div className="flex items-center gap-3">
                                        <div className={cn("p-2 rounded-md bg-background border border-border/50", color)}>
                                            <Icon className="w-4 h-4" />
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="text-sm font-bold text-foreground">{agentType}</span>
                                            <span className={cn(
                                                "text-[9px] uppercase tracking-widest font-bold",
                                                override ? "text-primary" : "text-muted-foreground"
                                            )}>
                                                {override ? `${override.model_provider} — ${override.model}` : "Using Global Default"}
                                            </span>
                                        </div>
                                    </div>
                                    <select
                                        value={overrideValue}
                                        onChange={(e) => handleOverrideChange(e.target.value)}
                                        className={cn(
                                            "min-w-[220px] bg-background border rounded-md px-3 py-1.5 text-xs font-medium cursor-pointer transition-all",
                                            override
                                                ? "border-primary text-primary bg-primary/5 focus:ring-1 focus:ring-primary"
                                                : "border-border text-muted-foreground hover:border-muted-foreground/50"
                                        )}
                                    >
                                        <option value="default" className="text-foreground">Global Default Model</option>
                                        <optgroup label="Gemini (Cloud)">
                                            {geminiModels.map(m => (
                                                <option key={`gemini:${m.value}`} value={`gemini:${m.value}`}>
                                                    Gemini: {m.label}
                                                </option>
                                            ))}
                                        </optgroup>
                                        {ollamaTextModels.length > 0 && (
                                            <optgroup label="Ollama (Local)">
                                                {ollamaTextModels.map(m => (
                                                    <option key={`ollama:${m.name}`} value={`ollama:${m.name}`}>
                                                        Ollama: {m.name}
                                                    </option>
                                                ))}
                                            </optgroup>
                                        )}
                                    </select>

                                    <div className="pt-4 border-t border-border mt-4">
                                        <h4 className="text-xs font-bold text-muted-foreground uppercase mb-2">Capabilities & Skills</h4>
                                        <div className="grid grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-2">
                                            {skills.map(skill => {
                                                const assigned = assignments[agentType]?.includes(skill.name);
                                                return (
                                                    <div key={skill.name} className="flex items-center space-x-2 bg-muted/20 p-2 rounded border border-transparent hover:border-border transition-colors">
                                                        <Checkbox
                                                            id={`${agentType}-${skill.name}`}
                                                            checked={!!assigned}
                                                            onCheckedChange={async (checked) => {
                                                                // Optimistic update
                                                                const newAssign = { ...assignments };
                                                                if (!newAssign[agentType]) newAssign[agentType] = [];

                                                                if (checked) {
                                                                    if (!newAssign[agentType].includes(skill.name)) newAssign[agentType].push(skill.name);
                                                                } else {
                                                                    newAssign[agentType] = newAssign[agentType].filter(s => s !== skill.name);
                                                                }
                                                                setAssignments(newAssign);

                                                                try {
                                                                    await axios.post(`${API_BASE}/skills/toggle`, {
                                                                        agent_name: agentType,
                                                                        skill_name: skill.name,
                                                                        active: !!checked
                                                                    });
                                                                } catch (e) {
                                                                    console.error("Failed", e);
                                                                    fetchAll(); // Revert
                                                                }
                                                            }}
                                                        />
                                                        <label
                                                            htmlFor={`${agentType}-${skill.name}`}
                                                            className="text-xs font-medium leading-none cursor-pointer select-none truncate"
                                                            title={skill.description}
                                                        >
                                                            {skill.name.replace(/_/g, ' ')}
                                                        </label>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                        {skills.length === 0 && <p className="text-xs text-muted-foreground italic">No skills installed.</p>}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div >
        );
    };

    const renderIdeTab = () => {
        const ollamaTextModels = ollamaModels.filter(m =>
            m.capabilities.includes('text') && !m.capabilities.includes('embedding')
        );

        const handleOverrideChange = (agentType: string, value: string) => {
            const colonIndex = value.indexOf(':');
            if (colonIndex === -1) return;

            const provider = value.substring(0, colonIndex) as 'gemini' | 'ollama';
            const modelName = value.substring(colonIndex + 1);

            updateOverride(agentType, provider, modelName);

            // Special case for IDEAgent: Sync with global store for immediate IDE effect
            if (agentType === 'IDEAgent') {
                setLocalModel(modelName);
            }
        };

        const renderAgentSelector = (agentType: string, label: string, description: string) => {
            const override = settings?.agent.overrides?.[agentType];
            const currentValue = override
                ? `${override.model_provider}:${override.model}`
                : `${settings?.agent.model_provider || 'gemini'}:${settings?.agent.default_model || 'gemini-3.0-flash'}`;

            return (
                <div className="space-y-3 p-4 bg-muted/30 border border-border/50 rounded-xl transition-all hover:bg-muted/40 group">
                    <div className="flex items-center justify-between">
                        <div>
                            <label className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{label}</label>
                            <p className="text-xs text-muted-foreground">{description}</p>
                        </div>
                        {override && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => resetOverride(agentType)}
                                className="h-7 text-[10px] text-muted-foreground hover:text-foreground"
                            >
                                <RotateCcw className="w-3 h-3 mr-1" />
                                Reset to Default
                            </Button>
                        )}
                    </div>
                    <select
                        value={currentValue}
                        onChange={(e) => handleOverrideChange(agentType, e.target.value)}
                        className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 outline-none transition-shadow"
                    >
                        <option disabled value="" className="text-muted-foreground font-semibold">Gemini (Cloud)</option>
                        {geminiModels.map((m) => (
                            <option key={`gemini:${m.value}`} value={`gemini:${m.value}`}>
                                {m.label} — {m.description}
                            </option>
                        ))}
                        {ollamaTextModels.length > 0 && (
                            <>
                                <option disabled value="" className="mt-2 text-muted-foreground font-semibold">Ollama (Local)</option>
                                {ollamaTextModels.map((m) => (
                                    <option key={`ollama:${m.name}`} value={`ollama:${m.name}`}>
                                        {m.name} — Local ({m.size_gb}GB)
                                    </option>
                                ))}
                            </>
                        )}
                    </select>
                </div>
            );
        };

        return (
            <div className="space-y-6 max-w">
                <div className="flex items-center gap-2 pb-2 border-b border-border/50">
                    <Layout className="w-5 h-5 text-primary" />
                    <h3 className="font-bold text-lg">IDE Agent Settings</h3>
                </div>

                <div className="grid gap-4">
                    {renderAgentSelector(
                        "IDEAgent",
                        "IDE Interaction Agent",
                        "The primary model for code chat and file operations in the Right Sidebar."
                    )}
                    {renderAgentSelector(
                        "TestAgent",
                        "Test Generation Agent",
                        "The model responsible for creating and updating unit tests (Pytest)."
                    )}
                    {renderAgentSelector(
                        "DebuggerAgent",
                        "Fix & Debug Agent",
                        "The model used to analyze test failures and automatically suggest/apply fixes."
                    )}
                </div>

                <div className="mt-8 p-4 rounded-xl border border-blue-500/20 bg-blue-500/5 flex gap-3">
                    <Bot className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                    <div className="text-xs text-muted-foreground leading-relaxed">
                        <strong className="text-blue-400 block mb-1">How it works</strong>
                        Each task can use its own optimized model. If no override is set, the <strong>Default Agent Model</strong> (from the Agent tab) will be used. Changes to the IDE Interaction Agent are reflected instantly in the sidebar.
                    </div>
                </div>
            </div>
        );
    };

    const renderPromptsTab = () => {
        const agentPrompts = prompts.filter(p => !['remme_extraction', 'rag_semantic_chunking'].includes(p.name));
        const otherPrompts = prompts.filter(p => ['remme_extraction', 'rag_semantic_chunking'].includes(p.name));

        return (
            <div className="flex gap-4 h-[calc(100vh-240px)]">
                {/* Prompt List */}
                <div className="w-56 border-r border-border pr-4 overflow-y-auto">
                    <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Agent Prompts</h3>
                    <div className="space-y-1 mb-6">
                        {agentPrompts.map((p) => (
                            <button
                                key={p.name}
                                onClick={() => { setSelectedPrompt(p); setPromptContent(p.content); setHasChanges(false); }}
                                className={cn(
                                    "w-full text-left px-2 py-1.5 rounded text-sm transition-colors",
                                    selectedPrompt?.name === p.name
                                        ? "bg-primary/10 text-primary border border-primary/20"
                                        : "hover:bg-muted/50 text-muted-foreground"
                                )}
                            >
                                <span className="block truncate">{p.name}</span>
                                <span className="text-[10px] text-muted-foreground opacity-70">({p.lines} lines)</span>
                            </button>
                        ))}
                    </div>

                    <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Other Prompts</h3>
                    <div className="space-y-1">
                        {otherPrompts.map((p) => (
                            <button
                                key={p.name}
                                onClick={() => { setSelectedPrompt(p); setPromptContent(p.content); setHasChanges(false); }}
                                className={cn(
                                    "w-full text-left px-2 py-1.5 rounded text-sm transition-colors",
                                    selectedPrompt?.name === p.name
                                        ? "bg-primary/10 text-primary border border-primary/20"
                                        : "hover:bg-muted/50 text-muted-foreground"
                                )}
                            >
                                <span className="block truncate">{p.name.replace('_', ' ')}</span>
                                <span className="text-[10px] text-muted-foreground opacity-70">({p.lines} lines)</span>
                            </button>
                        ))}
                    </div>
                </div>
                {/* Editor */}
                <div className="flex-1 flex flex-col">
                    {selectedPrompt ? (
                        <>
                            <div className="flex items-center justify-between mb-2">
                                <h3 className="font-medium text-foreground">{selectedPrompt.filename}</h3>
                                <div className="flex gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={resetPrompt}
                                        disabled={!selectedPrompt.has_backup}
                                        title={selectedPrompt.has_backup ? "Reset to original" : "No changes to reset"}
                                    >
                                        <RotateCcw className="w-3 h-3 mr-1" />
                                        Reset to Default
                                    </Button>
                                    <Button size="sm" onClick={savePrompt} disabled={saving || !hasChanges}>
                                        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                                        Save Prompt
                                    </Button>
                                </div>
                            </div>
                            <textarea
                                value={promptContent}
                                onChange={(e) => { setPromptContent(e.target.value); setHasChanges(true); }}
                                className="flex-1 w-full bg-background border border-border rounded-lg p-3 text-sm font-mono resize-none"
                                placeholder="Prompt content..."
                            />
                        </>
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-muted-foreground">
                            Select a prompt to edit
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderAdvancedTab = () => (
        <div className="space-y-6">
            <SettingGroup title="Ollama Base URL" description="Base URL for local Ollama server">
                <Input value={settings?.ollama.base_url || ''} onChange={(e) => updateSetting('ollama', 'base_url', e.target.value)} placeholder="http://127.0.0.1:11434" />
            </SettingGroup>
            <SettingGroup title="Ollama Timeout" description="Request timeout in seconds">
                <Input type="number" value={settings?.ollama.timeout || 300} onChange={(e) => updateSetting('ollama', 'timeout', parseInt(e.target.value))} />
            </SettingGroup>
            <SettingGroup title="Gemini Rate Limit" description="Minimum seconds between API calls">
                <Input type="number" step="0.1" value={settings?.agent.rate_limit_interval || 4.5} onChange={(e) => updateSetting('agent', 'rate_limit_interval', parseFloat(e.target.value))} />
            </SettingGroup>

            <div className="pt-6 border-t border-border">
                <h3 className="text-sm font-bold text-foreground mb-4">Server Actions</h3>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={resetSettings}><RotateCcw className="w-4 h-4 mr-1" /> Reset to Defaults</Button>
                    <Button variant="destructive" onClick={restartServer}><RefreshCw className="w-4 h-4 mr-1" /> Restart Server</Button>
                </div>
            </div>
        </div>
    );

    // === API Keys Tab ===

    const updateApiKeyEdit = (envName: string, value: string) => {
        setApiKeyEdits(prev => ({ ...prev, [envName]: value }));
    };

    const toggleKeyVisibility = (envName: string) => {
        setApiKeyVisibility(prev => ({ ...prev, [envName]: !prev[envName] }));
    };

    const generateRandomSecret = (envName: string) => {
        const bytes = new Uint8Array(32);
        crypto.getRandomValues(bytes);
        const base64 = btoa(String.fromCharCode(...bytes));
        updateApiKeyEdit(envName, base64);
        // Make it visible so the user can see/copy the generated value
        setApiKeyVisibility(prev => ({ ...prev, [envName]: true }));
    };

    const saveApiKeys = async () => {
        const keysToSave: Record<string, string> = {};
        for (const [envName, value] of Object.entries(apiKeyEdits)) {
            keysToSave[envName] = value;
        }
        if (Object.keys(keysToSave).length === 0) return;

        setSavingKeys(true);
        setError(null);
        try {
            await axios.put(`${API_BASE}/apikeys`, { keys: keysToSave });
            // Refresh status to show updated state
            const [res, geminiRes] = await Promise.all([
                axios.get(`${API_BASE}/apikeys/status`),
                axios.get(`${API_BASE}/gemini/status`).catch(() => ({ data: { configured: false, key_preview: null } })),
            ]);
            setApiKeysStatus(res.data.groups || null);
            setGeminiStatus(geminiRes.data);
            setApiKeyEdits({});
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to save API keys');
        } finally {
            setSavingKeys(false);
        }
    };

    const renderKeysTab = () => (
        <div className="space-y-8">
            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-start gap-2">
                <KeyRound className="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />
                <p className="text-xs text-blue-500/90">
                    API keys are stored in <code className="font-mono bg-blue-500/10 px-1 rounded">.env</code> and loaded into the server environment.
                    Changes take effect immediately without restart.
                </p>
            </div>

            {apiKeysStatus && Object.entries(apiKeysStatus).map(([groupId, group]) => (
                <div key={groupId} className="space-y-3">
                    {/* Group header */}
                    <div className="flex items-center gap-2 pb-2 border-b border-border">
                        <h3 className="text-sm font-bold text-foreground">{group.label}</h3>
                        <span className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded-full border",
                            group.configured_count === group.total_count
                                ? "bg-green-500/10 text-green-500 border-green-500/30"
                                : group.configured_count > 0
                                ? "bg-yellow-500/10 text-yellow-500 border-yellow-500/30"
                                : "bg-muted text-muted-foreground border-border"
                        )}>
                            {group.configured_count}/{group.total_count}
                        </span>
                    </div>

                    {/* Key inputs */}
                    <div className="grid gap-3">
                        {group.keys.map((keyDef) => {
                            const isEditing = keyDef.env in apiKeyEdits;
                            const isVisible = apiKeyVisibility[keyDef.env] || false;
                            const isSecret = keyDef.type === 'secret';

                            return (
                                <div key={keyDef.env} className="flex items-start gap-3 p-3 rounded-lg border border-border bg-muted/10">
                                    <div className="mt-2.5">
                                        {keyDef.configured ? (
                                            <Check className="w-4 h-4 text-green-500" />
                                        ) : (
                                            <X className="w-4 h-4 text-red-500/50" />
                                        )}
                                    </div>
                                    <div className="flex-1 space-y-1.5">
                                        <div className="flex items-center gap-2">
                                            <label className="text-sm font-medium text-foreground">{keyDef.label}</label>
                                            <code className="text-[10px] text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded">
                                                {keyDef.env}
                                            </code>
                                            {keyDef.has_default && keyDef.configured && (
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                                    auto
                                                </span>
                                            )}
                                        </div>
                                        {keyDef.configured && !isEditing && keyDef.preview && (
                                            <p className="text-xs text-muted-foreground font-mono">
                                                Current: {keyDef.preview}
                                            </p>
                                        )}
                                        <div className="flex gap-2">
                                            <div className="relative flex-1">
                                                <Input
                                                    type={isSecret && !isVisible ? 'password' : 'text'}
                                                    value={isEditing ? apiKeyEdits[keyDef.env] : ''}
                                                    onChange={(e) => updateApiKeyEdit(keyDef.env, e.target.value)}
                                                    placeholder={keyDef.configured ? 'Enter new value to update...' : `Enter ${keyDef.label}...`}
                                                    className="pr-10 font-mono text-sm"
                                                />
                                                {isSecret && (
                                                    <button
                                                        type="button"
                                                        onClick={() => toggleKeyVisibility(keyDef.env)}
                                                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                                    >
                                                        {isVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                                    </button>
                                                )}
                                            </div>
                                            {keyDef.generate && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => generateRandomSecret(keyDef.env)}
                                                    title="Generate random secret"
                                                    className="shrink-0 px-2"
                                                >
                                                    <Dices className="w-4 h-4 mr-1" />
                                                    Generate
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}

            {/* Sticky save bar */}
            {Object.keys(apiKeyEdits).length > 0 && (
                <div className="sticky bottom-0 pt-4 pb-2 bg-background/80 backdrop-blur-sm border-t border-border">
                    <div className="flex items-center justify-between">
                        <p className="text-xs text-muted-foreground">
                            {Object.keys(apiKeyEdits).length} key(s) modified
                        </p>
                        <div className="flex gap-2">
                            <Button variant="outline" onClick={() => setApiKeyEdits({})}>
                                Discard
                            </Button>
                            <Button onClick={saveApiKeys} disabled={savingKeys}>
                                {savingKeys ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
                                Save API Keys
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );

    const renderAboutTab = () => (
        <div className="space-y-6">
            <div className="p-4 rounded-lg border border-border bg-muted/20">
                <h3 className="text-lg font-bold text-foreground mb-1">Arcturus</h3>
                <p className="text-sm text-muted-foreground">
                    A modular AI platform with 20 integrated apps for agent orchestration, knowledge management, code editing, and more.
                </p>
            </div>

            <div>
                <h3 className="text-sm font-bold text-foreground mb-3">Feature Reference</h3>
                <div className="rounded-lg border border-border overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-muted/30 border-b border-border">
                                <th className="text-left px-4 py-2.5 font-semibold text-foreground w-[120px]">Feature</th>
                                <th className="text-left px-4 py-2.5 font-semibold text-foreground">Description</th>
                            </tr>
                        </thead>
                        <tbody>
                            {ABOUT_FEATURES.map((f, i) => (
                                <tr key={f.name} className={cn("border-b border-border last:border-0", i % 2 === 0 ? "bg-transparent" : "bg-muted/10")}>
                                    <td className="px-4 py-2.5 font-medium text-foreground whitespace-nowrap">{f.name}</td>
                                    <td className="px-4 py-2.5 text-muted-foreground">{f.description}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );

    const renderMcpTab = () => (
        <div className="flex gap-4 h-[calc(100vh-220px)] -mx-6 -mt-2">
            {/* Server list (left) */}
            <div className="w-[300px] shrink-0 border border-border/50 rounded-xl overflow-hidden">
                <McpPanel />
            </div>
            {/* Inspector / tool toggles (right) */}
            <div className="flex-1 border border-border/50 rounded-xl overflow-hidden">
                <McpInspector />
            </div>
        </div>
    );

    const renderTabContent = () => {
        switch (activeTab) {
            case 'models': return renderModelsTab();
            case 'rag': return renderRagTab();
            case 'agent': return renderAgentTab();
            case 'ide': return renderIdeTab();
            case 'prompts': return renderPromptsTab();
            case 'skills': return renderSkillsTab();
            case 'keys': return renderKeysTab();
            case 'mcp': return renderMcpTab();
            case 'advanced': return renderAdvancedTab();
            case 'about': return renderAboutTab();
        }
    };

    if (loading) {
        return <div className="h-full flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;
    }

    return (
        <div className="h-full flex flex-col bg-transparent overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-transparent backdrop-blur-sm shrink-0">
                <div>
                    <h2 className="font-bold text-foreground">{TABS.find(t => t.id === activeTab)?.label}</h2>
                    <p className="text-xs text-muted-foreground">{TABS.find(t => t.id === activeTab)?.description}</p>
                </div>
                {activeTab !== 'prompts' && activeTab !== 'keys' && activeTab !== 'skills' && activeTab !== 'about' && activeTab !== 'mcp' && (
                    <Button onClick={saveSettings} disabled={saving || !hasChanges}>
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
                        Save Changes
                    </Button>
                )}
            </div>
            <div className="flex-1 overflow-y-auto p-6">
                {error && <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-500 text-sm">{error}</div>}
                {warnings.length > 0 && (
                    <div className="mb-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 space-y-1">
                        {warnings.map((w, i) => <div key={i} className="flex items-start gap-2 text-yellow-500 text-xs"><AlertTriangle className="w-3 h-3 mt-0.5" />{w}</div>)}
                    </div>
                )}
                {renderTabContent()}
            </div>
        </div>
    );
};

const SettingGroup: React.FC<{ title: string; description: string; children: React.ReactNode }> = ({ title, description, children }) => (
    <div className="space-y-2">
        <div>
            <label className="text-sm font-medium text-foreground">{title}</label>
            <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        {children}
    </div>
);
