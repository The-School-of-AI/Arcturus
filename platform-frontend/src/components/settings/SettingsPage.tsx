import React, { useState, useEffect } from 'react';
import {
    Settings, Cpu, FileText, Brain, Wrench, RotateCcw, Save, AlertTriangle,
    Loader2, RefreshCw, Download, Check, X, Terminal
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE } from '@/lib/api';
import { useAppStore } from '@/store';
import axios from 'axios';

// Gemini model names (December 2025)
const GEMINI_MODELS = [
    { value: 'gemini-3.0-flash', label: 'Gemini 3.0 Flash', description: 'Latest, fast (Dec 2025)' },
    { value: 'gemini-3.0-pro', label: 'Gemini 3.0 Pro', description: 'Best multimodal (Nov 2025)' },
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', description: 'Fast, grounded' },
    { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro', description: 'Advanced reasoning' },
    { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite', description: 'Low cost' },
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash', description: 'Stable workhorse' },
];

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
        default_model: string;
        max_steps: number;
        max_lifelines_per_step: number;
        planning_mode: string;
        rate_limit_interval: number;
    };
    remme: { extraction_prompt: string };
    gemini: { api_key_env: string };
}

type TabId = 'models' | 'rag' | 'agent' | 'prompts' | 'advanced';

const TABS: { id: TabId; label: string; icon: typeof Cpu; description: string }[] = [
    { id: 'models', label: 'Models', icon: Cpu, description: 'Ollama & Gemini model selection' },
    { id: 'rag', label: 'RAG Pipeline', icon: FileText, description: 'Document chunking and search' },
    { id: 'agent', label: 'Agent', icon: Brain, description: 'Execution behavior & Gemini model' },
    { id: 'prompts', label: 'Prompts', icon: Terminal, description: 'Edit agent system prompts' },
    { id: 'advanced', label: 'Advanced', icon: Wrench, description: 'URLs, timeouts, restart' },
];

export const SettingsPage: React.FC = () => {
    const { settingsActiveTab: activeTab } = useAppStore();
    const [settings, setSettings] = useState<SettingsData | null>(null);
    const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
    const [prompts, setPrompts] = useState<Prompt[]>([]);
    const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null);
    const [promptContent, setPromptContent] = useState('');
    const [geminiStatus, setGeminiStatus] = useState<{ configured: boolean; key_preview: string | null } | null>(null);

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [pulling, setPulling] = useState(false);
    const [newModelName, setNewModelName] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [warnings, setWarnings] = useState<string[]>([]);
    const [hasChanges, setHasChanges] = useState(false);

    useEffect(() => {
        fetchAll();
    }, []);

    const fetchAll = async () => {
        setLoading(true);
        setError(null);
        try {
            const [settingsRes, modelsRes, promptsRes, geminiRes] = await Promise.all([
                axios.get(`${API_BASE}/settings`),
                axios.get(`${API_BASE}/ollama/models`).catch(() => ({ data: { models: [] } })),
                axios.get(`${API_BASE}/prompts`),
                axios.get(`${API_BASE}/gemini/status`).catch(() => ({ data: { configured: false, key_preview: null } }))
            ]);
            setSettings(settingsRes.data.settings);
            setOllamaModels(modelsRes.data.models || []);
            setPrompts(promptsRes.data.prompts || []);
            setGeminiStatus(geminiRes.data);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to load settings');
        } finally {
            setLoading(false);
        }
    };

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
            // Refresh models
            const res = await axios.get(`${API_BASE}/ollama/models`);
            setOllamaModels(res.data.models || []);
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

            {/* Gemini Status */}
            <div className="p-4 rounded-lg border border-border bg-muted/20 mt-6">
                <div className="flex items-center gap-2">
                    {geminiStatus?.configured ? (
                        <Check className="w-4 h-4 text-green-500" />
                    ) : (
                        <X className="w-4 h-4 text-red-500" />
                    )}
                    <span className="text-sm font-medium">
                        Gemini API Key: {geminiStatus?.configured ? 'Configured' : 'Not configured'}
                    </span>
                    {geminiStatus?.key_preview && (
                        <span className="text-xs text-muted-foreground font-mono">({geminiStatus.key_preview})</span>
                    )}
                </div>
                {!geminiStatus?.configured && (
                    <p className="text-xs text-muted-foreground mt-2">
                        Set GEMINI_API_KEY environment variable and restart the server.
                    </p>
                )}
            </div>

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

    const renderAgentTab = () => (
        <div className="space-y-6">
            <SettingGroup title="Default Gemini Model" description="Model used for agent execution">
                <select
                    value={settings?.agent.default_model || 'gemini-2.5-flash'}
                    onChange={(e) => updateSetting('agent', 'default_model', e.target.value)}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm"
                >
                    {GEMINI_MODELS.map((m) => (
                        <option key={m.value} value={m.value}>
                            {m.label} — {m.description}
                        </option>
                    ))}
                </select>
            </SettingGroup>
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
        </div>
    );

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

    const renderTabContent = () => {
        switch (activeTab) {
            case 'models': return renderModelsTab();
            case 'rag': return renderRagTab();
            case 'agent': return renderAgentTab();
            case 'prompts': return renderPromptsTab();
            case 'advanced': return renderAdvancedTab();
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
                {activeTab !== 'prompts' && (
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
