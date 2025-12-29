import React, { useState, useEffect } from 'react';
import {
    Settings, Cpu, FileText, Brain, Wrench, RotateCcw, Save, AlertTriangle,
    ChevronRight, Loader2, RefreshCw
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE } from '@/lib/api';
import axios from 'axios';

interface SettingsData {
    ollama: {
        base_url: string;
        timeout: number;
    };
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
    remme: {
        extraction_prompt: string;
    };
    gemini: {
        api_key_env: string;
    };
}

type TabId = 'models' | 'rag' | 'agent' | 'remme' | 'advanced';

const TABS: { id: TabId; label: string; icon: typeof Cpu; description: string }[] = [
    { id: 'models', label: 'Models', icon: Cpu, description: 'Configure AI models for different tasks' },
    { id: 'rag', label: 'RAG Pipeline', icon: FileText, description: 'Document chunking and search settings' },
    { id: 'agent', label: 'Agent', icon: Brain, description: 'Agent execution behavior' },
    { id: 'remme', label: 'RemMe', icon: Brain, description: 'Memory extraction settings' },
    { id: 'advanced', label: 'Advanced', icon: Wrench, description: 'URLs, timeouts, and rate limits' },
];

export const SettingsPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<TabId>('models');
    const [settings, setSettings] = useState<SettingsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [warnings, setWarnings] = useState<string[]>([]);
    const [hasChanges, setHasChanges] = useState(false);

    // Fetch settings on mount
    useEffect(() => {
        fetchSettings();
    }, []);

    const fetchSettings = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get(`${API_BASE}/settings`);
            setSettings(res.data.settings);
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
            if (res.data.warnings) {
                setWarnings(res.data.warnings);
            }
            setHasChanges(false);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const resetSettings = async () => {
        if (!confirm('Reset all settings to defaults? This cannot be undone.')) return;
        try {
            await axios.post(`${API_BASE}/settings/reset`);
            await fetchSettings();
            setHasChanges(false);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to reset settings');
        }
    };

    const restartServer = async () => {
        if (!confirm('Restart server? This will temporarily disconnect all clients.')) return;
        try {
            await axios.post(`${API_BASE}/settings/restart`);
            alert('Server restart initiated. Page will reload in 5 seconds...');
            setTimeout(() => window.location.reload(), 5000);
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to restart server');
        }
    };

    const updateSetting = (section: keyof SettingsData, key: string, value: any) => {
        if (!settings) return;
        setSettings({
            ...settings,
            [section]: {
                ...settings[section],
                [key]: value
            }
        });
        setHasChanges(true);
    };

    const renderModelsTab = () => (
        <div className="space-y-6">
            <SettingGroup title="Embedding Model" description="Used for document indexing and semantic search">
                <Input
                    value={settings?.models.embedding || ''}
                    onChange={(e) => updateSetting('models', 'embedding', e.target.value)}
                    placeholder="nomic-embed-text"
                />
            </SettingGroup>
            <SettingGroup title="Semantic Chunking Model" description="LLM for intelligent document splitting">
                <Input
                    value={settings?.models.semantic_chunking || ''}
                    onChange={(e) => updateSetting('models', 'semantic_chunking', e.target.value)}
                    placeholder="gemma3:4b"
                />
            </SettingGroup>
            <SettingGroup title="Image Captioning Model" description="Vision model for extracting text from images">
                <Input
                    value={settings?.models.image_captioning || ''}
                    onChange={(e) => updateSetting('models', 'image_captioning', e.target.value)}
                    placeholder="gemma3:4b"
                />
            </SettingGroup>
            <SettingGroup title="Memory Extraction Model" description="Model for RemMe memory extraction">
                <Input
                    value={settings?.models.memory_extraction || ''}
                    onChange={(e) => updateSetting('models', 'memory_extraction', e.target.value)}
                    placeholder="qwen3-vl:8b"
                />
            </SettingGroup>
            <SettingGroup title="Insights Provider" description="Provider for document insights (ollama or gemini)">
                <select
                    value={settings?.models.insights_provider || 'ollama'}
                    onChange={(e) => updateSetting('models', 'insights_provider', e.target.value)}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm"
                >
                    <option value="ollama">Ollama (Local)</option>
                    <option value="gemini">Gemini (Cloud)</option>
                </select>
            </SettingGroup>
            <SettingGroup title="Gemini API Key Environment Variable" description="Environment variable containing your Gemini API key">
                <Input
                    value={settings?.gemini.api_key_env || ''}
                    onChange={(e) => updateSetting('gemini', 'api_key_env', e.target.value)}
                    placeholder="GEMINI_API_KEY"
                />
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
            <SettingGroup title="Chunk Size" description="Base number of words per chunk (for fallback chunking)">
                <Input
                    type="number"
                    value={settings?.rag.chunk_size || 256}
                    onChange={(e) => updateSetting('rag', 'chunk_size', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Chunk Overlap" description="Number of overlapping words between chunks">
                <Input
                    type="number"
                    value={settings?.rag.chunk_overlap || 40}
                    onChange={(e) => updateSetting('rag', 'chunk_overlap', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Max Chunk Length" description="Maximum characters per chunk (safety limit)">
                <Input
                    type="number"
                    value={settings?.rag.max_chunk_length || 512}
                    onChange={(e) => updateSetting('rag', 'max_chunk_length', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Semantic Word Limit" description="Words per block for semantic chunking">
                <Input
                    type="number"
                    value={settings?.rag.semantic_word_limit || 1024}
                    onChange={(e) => updateSetting('rag', 'semantic_word_limit', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Top-K Results" description="Number of search results to return">
                <Input
                    type="number"
                    value={settings?.rag.top_k || 3}
                    onChange={(e) => updateSetting('rag', 'top_k', parseInt(e.target.value))}
                />
            </SettingGroup>
        </div>
    );

    const renderAgentTab = () => (
        <div className="space-y-6">
            <SettingGroup title="Default Model" description="Model used for agent execution">
                <Input
                    value={settings?.agent.default_model || 'gemini'}
                    onChange={(e) => updateSetting('agent', 'default_model', e.target.value)}
                />
            </SettingGroup>
            <SettingGroup title="Max Steps" description="Maximum reasoning steps per agent run">
                <Input
                    type="number"
                    value={settings?.agent.max_steps || 3}
                    onChange={(e) => updateSetting('agent', 'max_steps', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Lifelines per Step" description="Retry attempts for each step on failure">
                <Input
                    type="number"
                    value={settings?.agent.max_lifelines_per_step || 3}
                    onChange={(e) => updateSetting('agent', 'max_lifelines_per_step', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Planning Mode" description="Agent planning strategy">
                <select
                    value={settings?.agent.planning_mode || 'conservative'}
                    onChange={(e) => updateSetting('agent', 'planning_mode', e.target.value)}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm"
                >
                    <option value="conservative">Conservative</option>
                    <option value="exploratory">Exploratory</option>
                </select>
            </SettingGroup>
        </div>
    );

    const renderRemmeTab = () => (
        <div className="space-y-6">
            <SettingGroup title="Extraction Prompt" description="System prompt for memory extraction">
                <textarea
                    value={settings?.remme.extraction_prompt || ''}
                    onChange={(e) => updateSetting('remme', 'extraction_prompt', e.target.value)}
                    className="w-full h-64 bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono resize-y"
                    placeholder="Enter extraction prompt..."
                />
            </SettingGroup>
        </div>
    );

    const renderAdvancedTab = () => (
        <div className="space-y-6">
            <SettingGroup title="Ollama Base URL" description="Base URL for the local Ollama server">
                <Input
                    value={settings?.ollama.base_url || ''}
                    onChange={(e) => updateSetting('ollama', 'base_url', e.target.value)}
                    placeholder="http://127.0.0.1:11434"
                />
            </SettingGroup>
            <SettingGroup title="Ollama Timeout" description="Request timeout in seconds">
                <Input
                    type="number"
                    value={settings?.ollama.timeout || 300}
                    onChange={(e) => updateSetting('ollama', 'timeout', parseInt(e.target.value))}
                />
            </SettingGroup>
            <SettingGroup title="Gemini Rate Limit Interval" description="Minimum seconds between Gemini API calls">
                <Input
                    type="number"
                    step="0.1"
                    value={settings?.agent.rate_limit_interval || 4.5}
                    onChange={(e) => updateSetting('agent', 'rate_limit_interval', parseFloat(e.target.value))}
                />
            </SettingGroup>

            <div className="pt-6 border-t border-border">
                <h3 className="text-sm font-bold text-foreground mb-4">Server Actions</h3>
                <div className="flex gap-3">
                    <Button
                        variant="outline"
                        onClick={resetSettings}
                        className="gap-2"
                    >
                        <RotateCcw className="w-4 h-4" />
                        Reset to Defaults
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={restartServer}
                        className="gap-2"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Restart Server
                    </Button>
                </div>
            </div>
        </div>
    );

    const renderTabContent = () => {
        switch (activeTab) {
            case 'models': return renderModelsTab();
            case 'rag': return renderRagTab();
            case 'agent': return renderAgentTab();
            case 'remme': return renderRemmeTab();
            case 'advanced': return renderAdvancedTab();
        }
    };

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="h-full flex bg-background">
            {/* Left Panel: Tabs */}
            <div className="w-64 border-r border-border bg-card/50 flex flex-col">
                <div className="p-4 border-b border-border">
                    <div className="flex items-center gap-2">
                        <Settings className="w-5 h-5 text-primary" />
                        <h1 className="font-bold text-foreground">Settings</h1>
                    </div>
                </div>
                <nav className="flex-1 p-2 space-y-1">
                    {TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={cn(
                                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left",
                                activeTab === tab.id
                                    ? "bg-primary/10 text-primary border border-primary/20"
                                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                            )}
                        >
                            <tab.icon className="w-4 h-4" />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium">{tab.label}</div>
                                <div className="text-[10px] opacity-60 truncate">{tab.description}</div>
                            </div>
                            <ChevronRight className={cn(
                                "w-4 h-4 transition-transform",
                                activeTab === tab.id && "rotate-90"
                            )} />
                        </button>
                    ))}
                </nav>
            </div>

            {/* Right Panel: Content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <div className="p-4 border-b border-border flex items-center justify-between bg-card/30">
                    <div>
                        <h2 className="font-bold text-foreground">
                            {TABS.find(t => t.id === activeTab)?.label}
                        </h2>
                        <p className="text-xs text-muted-foreground">
                            {TABS.find(t => t.id === activeTab)?.description}
                        </p>
                    </div>
                    <Button
                        onClick={saveSettings}
                        disabled={saving || !hasChanges}
                        className="gap-2"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save Changes
                    </Button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {error && (
                        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-500 text-sm">
                            {error}
                        </div>
                    )}
                    {warnings.length > 0 && (
                        <div className="mb-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 space-y-1">
                            {warnings.map((w, i) => (
                                <div key={i} className="flex items-start gap-2 text-yellow-500 text-xs">
                                    <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                                    {w}
                                </div>
                            ))}
                        </div>
                    )}
                    {renderTabContent()}
                </div>
            </div>
        </div>
    );
};

// Helper component for consistent setting groups
const SettingGroup: React.FC<{
    title: string;
    description: string;
    children: React.ReactNode;
}> = ({ title, description, children }) => (
    <div className="space-y-2">
        <div>
            <label className="text-sm font-medium text-foreground">{title}</label>
            <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        {children}
    </div>
);
