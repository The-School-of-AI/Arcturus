import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Brain, Sparkles, RefreshCw } from 'lucide-react';
import { API_BASE } from '@/lib/api';
import axios from 'axios';

export const RemMeProfileView: React.FC = () => {
    const [content, setContent] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchProfile = async (force: boolean = false) => {
        setIsLoading(true);
        setError(null);
        try {
            // Note: Currently backend handles caching, but we could add a force flag query param if needed
            const response = await axios.get(`${API_BASE}/remme/profile`);
            // Clean up the content to prevent indentation from creating code blocks
            const rawContent = response.data.content || '';
            const cleanedContent = rawContent.split('\n').map((line: string) => line.trimStart()).join('\n');
            setContent(cleanedContent);
        } catch (err: any) {
            console.error("Failed to fetch profile:", err);
            setError(err.response?.data?.detail || "Failed to generate profile. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchProfile();
    }, []);

    if (isLoading) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 bg-card animate-in fade-in duration-500">
                <div className="relative">
                    <div className="absolute inset-0 bg-yellow-500/20 blur-xl rounded-full animate-pulse" />
                    <Brain className="w-16 h-16 text-yellow-500 relative z-10 animate-bounce" />
                </div>
                <h2 className="mt-8 text-2xl font-bold text-foreground tracking-tight">Analyzing Memories...</h2>
                <p className="mt-2 text-muted-foreground text-center max-w-md animate-pulse">
                    Gemini is reading through your history to construct a detailed psychological and professional profile. <br />
                    <span className="text-xs opacity-70 mt-2 block">(This may take 10-20 seconds on first run)</span>
                </p>
                <div className="mt-8 flex gap-2">
                    <div className="w-2 h-2 bg-yellow-500 rounded-full animate-[bounce_1s_infinite_0ms]" />
                    <div className="w-2 h-2 bg-yellow-500 rounded-full animate-[bounce_1s_infinite_200ms]" />
                    <div className="w-2 h-2 bg-yellow-500 rounded-full animate-[bounce_1s_infinite_400ms]" />
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center">
                <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mb-4">
                    <Brain className="w-8 h-8 text-red-500" />
                </div>
                <h3 className="text-lg font-bold text-red-500 mb-2">Profile Generation Failed</h3>
                <p className="text-muted-foreground mb-6 max-w-md">{error}</p>
                <button
                    onClick={() => fetchProfile()}
                    className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 rounded-md transition-colors font-medium text-sm"
                >
                    <RefreshCw className="w-4 h-4" /> Try Again
                </button>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-transparent overflow-hidden relative">
            {/* Header */}
            <div className="flex-none p-6 pb-2 border-b border-border/50 bg-transparent backdrop-blur-sm z-10 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-yellow-400 to-amber-600 bg-clip-text text-transparent flex items-center gap-2">
                        <Sparkles className="w-6 h-6 text-yellow-500" />
                        RemMe Insight Profile
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        AI-generated psychological and professional analysis based on your long-term memory.
                    </p>
                </div>
                <button
                    onClick={() => fetchProfile()}
                    title="Regenerate Profile"
                    className="p-2 hover:bg-muted rounded-full text-muted-foreground hover:text-foreground transition-colors"
                >
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-8 py-8 md:px-12 w-full">
                <article className="prose prose-slate dark:prose-invert max-w-none 
                    prose-headings:font-bold prose-headings:tracking-tight 
                    prose-h1:text-3xl prose-h2:text-2xl prose-h2:border-b prose-h2:border-border prose-h2:pb-2 prose-h2:mt-8 
                    prose-p:leading-relaxed prose-p:text-foreground/90 
                    prose-li:text-foreground/90 prose-li:marker:text-yellow-500/70
                    prose-strong:text-yellow-600 dark:prose-strong:text-yellow-400 
                    prose-code:text-yellow-600 dark:prose-code:text-yellow-400 prose-code:bg-yellow-500/10 prose-code:px-1 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none
                    selection:bg-yellow-500/30">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {content || ''}
                    </ReactMarkdown>
                </article>

                <div className="mt-16 pt-8 border-t border-border text-center text-xs text-muted-foreground font-mono">
                    Generated by Gemini 2.0 Flash (1M Context) • Cached for 7 Days
                </div>
            </div>
        </div>
    );
};
