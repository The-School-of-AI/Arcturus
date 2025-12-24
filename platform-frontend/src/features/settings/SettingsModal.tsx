import React from 'react';
import { X, Save } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';

interface SettingsModalProps {
    open: boolean;
    onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose }) => {
    const { apiKey, setApiKey, localModel, setLocalModel } = useAppStore();

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-charcoal-800 border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <h2 className="text-lg font-semibold text-foreground">Settings</h2>
                    <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 hover:text-destructive">
                        <X className="w-4 h-4" />
                    </Button>
                </div>

                <div className="p-6 space-y-6 overflow-y-auto">
                    <div className="space-y-2">
                        <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            Gemini API Key
                        </label>
                        <input
                            type="password"
                            className="w-full bg-charcoal-900 border border-border rounded-md px-3 py-2 text-sm focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all font-mono"
                            placeholder="AIzaSy..."
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                        />
                        <p className="text-[10px] text-muted-foreground">Stored locally in your browser.</p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            Local Model (Ollama)
                        </label>
                        <select
                            className="w-full bg-charcoal-900 border border-border rounded-md px-3 py-2 text-sm focus:border-primary/50 transition-all"
                            value={localModel}
                            onChange={(e) => setLocalModel(e.target.value)}
                        >
                            <option value="mistral:latest">mistral:latest</option>
                            <option value="llama2">llama2</option>
                            <option value="gemma:7b">gemma:7b</option>
                        </select>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            System Prompts
                        </label>
                        <div className="text-xs bg-charcoal-900 border border-border rounded p-3 text-muted-foreground">
                            Global prompts editing coming soon...
                        </div>
                    </div>


                </div>

                <div className="p-4 bg-charcoal-900/50 border-t border-white/5 flex justify-end">
                    <Button onClick={onClose} className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
                        <Save className="w-4 h-4" />
                        Save Changes
                    </Button>
                </div>
            </div>
        </div>
    );
};
