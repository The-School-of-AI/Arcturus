import { useState } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { createPortal } from 'react-dom';

interface AppGenerationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onGenerate: (name: string, prompt: string) => Promise<void>;
}

export function AppGenerationModal({ isOpen, onClose, onGenerate }: AppGenerationModalProps) {
    const [name, setName] = useState('');
    const [prompt, setPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState('');

    if (!isOpen) return null;

    const handleGenerate = async () => {
        if (!name.trim()) {
            setError('Please enter an app name');
            return;
        }
        if (!prompt.trim()) {
            setError('Please describe your dashboard');
            return;
        }

        setError('');
        setIsGenerating(true);

        try {
            await onGenerate(name, prompt);
            // Reset form
            setName('');
            setPrompt('');
            onClose();
        } catch (err) {
            console.error(err);
            setError('Failed to generate dashboard. Please try again.');
        } finally {
            setIsGenerating(false);
        }
    };

    const modalContent = (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose}>
            <div className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-primary/20">
                        <Sparkles className="w-6 h-6 text-primary" />
                    </div>
                    <h2 className="text-xl font-bold">Generate Dashboard with AI</h2>
                </div>

                <div className="space-y-4">
                    {/* App Name Input */}
                    <div>
                        <label className="block text-sm font-medium mb-2">
                            Dashboard Name <span className="text-destructive">*</span>
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder='e.g., "CFO Dashboard" or "Sales Analytics"'
                            className="w-full px-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                            disabled={isGenerating}
                        />
                    </div>

                    {/* Prompt Textarea */}
                    <div>
                        <label className="block text-sm font-medium mb-2">
                            Describe your dashboard <span className="text-destructive">*</span>
                        </label>
                        <textarea
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            placeholder="Describe what you want your dashboard to show. Be specific about metrics, charts, and data you want to track. For example: &quot;A financial dashboard for tracking revenue, costs, profit margins, and cash flow with trend charts and key metrics&quot;"
                            rows={6}
                            className="w-full px-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                            disabled={isGenerating}
                        />
                        <div className="text-xs text-muted-foreground mt-1">
                            Tip: Include specific metrics, visualizations, and data sources you want
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
                            {error}
                        </div>
                    )}
                </div>

                {/* Actions */}
                <div className="flex gap-3 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 py-2 px-4 rounded-lg border border-border hover:bg-muted transition-colors"
                        disabled={isGenerating}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleGenerate}
                        disabled={isGenerating || !name.trim() || !prompt.trim()}
                        className="flex-1 py-2 px-4 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Generating...
                            </>
                        ) : (
                            <>
                                <Sparkles className="w-4 h-4" />
                                Generate Dashboard
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
