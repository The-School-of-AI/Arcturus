import React, { useEffect, useState } from 'react';
import { X, Save, RefreshCw } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

interface SettingsModalProps {
    open: boolean;
    onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose }) => {
    const { apiKey, setApiKey } = useAppStore();
    const [settings, setSettings] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [ollamaModels, setOllamaModels] = useState<string[]>([]);

    // Fetch settings and models when opened
    useEffect(() => {
        if (!open) return;

        const fetchData = async () => {
            setLoading(true);
            try {
                // 1. Get Settings
                const res = await axios.get(`${API_BASE}/settings`);
                if (res.data?.settings) {
                    setSettings(res.data.settings);
                }

                // 2. Get Ollama Models
                try {
                    const modelRes = await axios.get(`${API_BASE}/settings/ollama/models`);
                    if (modelRes.data?.models) {
                        setOllamaModels(modelRes.data.models.map((m: any) => m.name));
                    }
                } catch (e) {
                    // Ollama might be down, just ignore
                }
            } catch (e) {
                console.error("Failed to load settings", e);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [open]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await axios.put(`${API_BASE}/settings`, { settings });
            onClose();
        } catch (e) {
            console.error("Failed to save settings", e);
            alert("Failed to save settings");
        } finally {
            setSaving(false);
        }
    };

    const updateAgentOverride = (agent: string, field: string, value: string) => {
        setSettings((prev: any) => {
            const newSettings = { ...prev };
            if (!newSettings.agent) newSettings.agent = {};
            if (!newSettings.agent.overrides) newSettings.agent.overrides = {};
            if (!newSettings.agent.overrides[agent]) newSettings.agent.overrides[agent] = {};

            newSettings.agent.overrides[agent][field] = value;
            return newSettings;
        });
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-card border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                <div className="flex items-center justify-between p-4 border-b border-border/50">
                    <h2 className="text-lg font-semibold text-foreground">Settings</h2>
                    <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 hover:text-destructive">
                        <X className="w-4 h-4" />
                    </Button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-8">
                    {loading ? (
                        <div className="flex items-center justify-center h-32 text-muted-foreground">
                            <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                            Loading settings...
                        </div>
                    ) : settings ? (
                        <>
                            {/* Gemini Section */}
                            <div className="space-y-3">
                                <h3 className="text-sm font-medium text-foreground border-b border-border/50 pb-1">AI Providers</h3>
                                <div className="grid gap-4">
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-mono text-muted-foreground">Gemini API Key</label>
                                        <input
                                            type="password"
                                            className="w-full bg-input border border-border rounded-md px-3 py-1.5 text-sm font-mono"
                                            placeholder="AIzaSy..."
                                            value={apiKey}
                                            onChange={(e) => setApiKey(e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-mono text-muted-foreground">Ollama Base URL</label>
                                        <input
                                            type="text"
                                            className="w-full bg-input border border-border rounded-md px-3 py-1.5 text-sm font-mono"
                                            value={settings.ollama?.base_url || "http://127.0.0.1:11434"}
                                            onChange={(e) => setSettings({ ...settings, ollama: { ...settings.ollama, base_url: e.target.value } })}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Agents Config */}
                            <div className="space-y-4">
                                <h3 className="text-sm font-medium text-foreground border-b border-border/50 pb-1">Agent Models (Overrides)</h3>

                                <div className="grid grid-cols-2 gap-4">
                                    {/* Test Agent */}
                                    <div className="p-3 bg-muted/30 rounded-lg border border-border/50 space-y-2">
                                        <div className="font-medium text-sm text-foreground">Test Agent</div>
                                        <div className="grid gap-2">
                                            <select
                                                className="w-full bg-input border border-border rounded px-2 py-1 text-xs"
                                                value={settings.agent?.overrides?.TestAgent?.model_provider || "ollama"}
                                                onChange={(e) => updateAgentOverride('TestAgent', 'model_provider', e.target.value)}
                                            >
                                                <option value="ollama">Ollama</option>
                                                <option value="gemini">Gemini</option>
                                            </select>

                                            {settings.agent?.overrides?.TestAgent?.model_provider === 'gemini' ? (
                                                <input
                                                    className="w-full bg-input border border-border rounded px-2 py-1 text-xs"
                                                    value={settings.agent?.overrides?.TestAgent?.model || "gemini-2.5-flash"}
                                                    onChange={(e) => updateAgentOverride('TestAgent', 'model', e.target.value)}
                                                    placeholder="Model name"
                                                />
                                            ) : (
                                                <select
                                                    className="w-full bg-input border border-border rounded px-2 py-1 text-xs"
                                                    value={settings.agent?.overrides?.TestAgent?.model || ""}
                                                    onChange={(e) => updateAgentOverride('TestAgent', 'model', e.target.value)}
                                                >
                                                    <option value="" disabled>Select Model</option>
                                                    {ollamaModels.map(m => <option key={m} value={m}>{m}</option>)}
                                                </select>
                                            )}
                                        </div>
                                    </div>

                                    {/* General Agent Default */}
                                    <div className="p-3 bg-muted/30 rounded-lg border border-border/50 space-y-2">
                                        <div className="font-medium text-sm text-foreground">General / IDE Agent</div>
                                        <div className="grid gap-2">
                                            <select
                                                className="w-full bg-input border border-border rounded px-2 py-1 text-xs"
                                                value={settings.agent?.model_provider || "gemini"}
                                                onChange={(e) => setSettings({ ...settings, agent: { ...settings.agent, model_provider: e.target.value } })}
                                            >
                                                <option value="ollama">Ollama</option>
                                                <option value="gemini">Gemini</option>
                                            </select>

                                            {settings.agent?.model_provider === 'gemini' ? (
                                                <input
                                                    className="w-full bg-input border border-border rounded px-2 py-1 text-xs"
                                                    value={settings.agent?.default_model || "gemini-2.5-flash"}
                                                    onChange={(e) => setSettings({ ...settings, agent: { ...settings.agent, default_model: e.target.value } })}
                                                    placeholder="Model name"
                                                />
                                            ) : (
                                                <select
                                                    className="w-full bg-input border border-border rounded px-2 py-1 text-xs"
                                                    value={settings.agent?.default_model || ""}
                                                    onChange={(e) => setSettings({ ...settings, agent: { ...settings.agent, default_model: e.target.value } })}
                                                >
                                                    <option value="" disabled>Select Model</option>
                                                    {ollamaModels.map(m => <option key={m} value={m}>{m}</option>)}
                                                </select>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <p className="text-[10px] text-muted-foreground">Changes to agent models take effect on next run.</p>
                            </div>
                        </>
                    ) : (
                        <div className="text-red-500">Failed to load settings.</div>
                    )}
                </div>

                <div className="p-4 bg-muted/50 border-t border-border/50 flex justify-end gap-2">
                    <Button variant="ghost" onClick={onClose} disabled={saving}>Cancel</Button>
                    <Button onClick={handleSave} disabled={saving || loading} className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
                        {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save Changes
                    </Button>
                </div>
            </div>
        </div>
    );
};
