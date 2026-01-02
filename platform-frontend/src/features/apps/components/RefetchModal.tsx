import { useState } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';
import { createPortal } from 'react-dom';

interface RefetchModalProps {
    isOpen: boolean;
    onClose: () => void;
    onRefetch: (prompt: string) => Promise<void>;
}

export function RefetchModal({ isOpen, onClose, onRefetch }: RefetchModalProps) {
    const [prompt, setPrompt] = useState('');
    const [isRefetching, setIsRefetching] = useState(false);
    const [error, setError] = useState('');

    if (!isOpen) return null;

    const handleRefetch = async () => {
        setError('');
        setIsRefetching(true);

        try {
            await onRefetch(prompt);
            // Reset form
            setPrompt('');
            onClose();
        } catch (err) {
            console.error(err);
            setError('Failed to refresh data. Please try again.');
        } finally {
            setIsRefetching(false);
        }
    };

    const modalContent = (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose}>
            <div className="bg-background border border-border rounded-lg p-6 max-w-lg w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-primary/20">
                        <RefreshCw className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold">Refresh Data</h2>
                        <p className="text-xs text-muted-foreground">Fetch latest data using AI</p>
                    </div>
                </div>

                <div className="space-y-4">
                    {/* Prompt Textarea */}
                    <div>
                        <label className="block text-sm font-medium mb-2">
                            Your Preferences <span className="text-muted-foreground">(optional)</span>
                        </label>
                        <textarea
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            placeholder="Add any specific instructions for the data refresh. For example: 'Focus on Q4 2025 data', 'Include competitor comparisons', 'Use Indian Rupees for currency'..."
                            rows={4}
                            className="w-full px-4 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                            disabled={isRefetching}
                        />
                        <div className="text-xs text-muted-foreground mt-1">
                            Leave empty to refresh with default settings
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
                        className="flex-1 py-2 px-4 rounded-lg border border-border hover:border-muted-foreground hover:bg-muted/50 transition-colors"
                        disabled={isRefetching}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleRefetch}
                        disabled={isRefetching}
                        className="flex-1 py-2 px-4 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isRefetching ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Refreshing...
                            </>
                        ) : (
                            <>
                                <RefreshCw className="w-4 h-4" />
                                Refresh Data
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
