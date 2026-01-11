
import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import ReactMarkdown from 'react-markdown';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2, AlertCircle } from 'lucide-react';
import { API_BASE } from '@/lib/api';

export const McpBrowser: React.FC = () => {
    const { selectedMcpServer } = useAppStore();
    const [content, setContent] = useState<string>("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false);

    useEffect(() => {
        if (!selectedMcpServer) return;

        // Legacy / Special Handling
        if (selectedMcpServer === 'alphavantage') {
            return; // Render iframe below
        }

        const fetchDocs = async () => {
            setLoading(true);
            setError(false);
            try {
                // Try to fetch dynamic README from backend
                const res = await fetch(`${API_BASE}/mcp/readme/${selectedMcpServer}`);
                if (!res.ok) throw new Error("Doc not found");
                const data = await res.json();

                // If backend returns specific content, use it
                if (data.content) {
                    setContent(data.content);
                } else {
                    // Fallback to static if backend return empty (for legacy reasons or if desired)
                    // But backend now returns a default message so we likely won't hit this.
                    setContent(`# ${selectedMcpServer.toUpperCase()}\n\nNo documentation found.`);
                }

            } catch (e) {
                console.warn(`Failed to fetch docs for ${selectedMcpServer}`, e);
                setContent(`# ${selectedMcpServer.toUpperCase()}\n\nError loading documentation.`);
            } finally {
                setLoading(false);
            }
        };

        fetchDocs();
    }, [selectedMcpServer]);

    if (!selectedMcpServer) {
        return (
            <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground p-8">
                <div className="p-4 rounded-full bg-muted/50 mb-4">
                    <AlertCircle className="w-8 h-8 opacity-50" />
                </div>
                <p>Select an MCP Server to view documentation</p>
            </div>
        );
    }

    if (selectedMcpServer === 'alphavantage') {
        return (
            <div className="w-full h-full flex flex-col bg-background">
                <iframe
                    src="https://mcp.alphavantage.co/"
                    className="w-full h-full border-0"
                    title="Alpha Vantage MCP Docs"
                />
            </div>
        );
    }

    return (
        <div className="w-full h-full bg-transparent flex flex-col overflow-hidden">
            <ScrollArea className="flex-1 p-8">
                <div className="max-w-3xl mx-auto prose prose-slate dark:prose-invert prose-sm">
                    {loading ? (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="w-8 h-8 animate-spin text-primary" />
                        </div>
                    ) : (
                        <ReactMarkdown
                            components={{
                                h1: ({ node, ...props }) => <h1 className="text-2xl font-bold text-foreground mb-4 pb-2 border-b border-border" {...props} />,
                                h2: ({ node, ...props }) => <h2 className="text-xl font-semibold text-foreground mt-8 mb-3" {...props} />,
                                h3: ({ node, ...props }) => <h3 className="text-lg font-medium text-primary mt-6 mb-2" {...props} />,
                                ul: ({ node, ...props }) => <ul className="list-disc pl-5 space-y-1 my-4 text-muted-foreground" {...props} />,
                                li: ({ node, ...props }) => <li className="text-muted-foreground" {...props} />,
                                code: ({ node, inline, className, children, ...props }: any) => {
                                    return inline ? (
                                        <code className="bg-muted px-1.5 py-0.5 rounded text-primary font-mono text-xs" {...props}>{children}</code>
                                    ) : (
                                        <div className="bg-muted/50 p-4 rounded-lg my-4 overflow-x-auto border border-border">
                                            <code className="bg-transparent text-sm font-mono text-foreground" {...props}>{children}</code>
                                        </div>
                                    )
                                }
                            }}
                        >
                            {content}
                        </ReactMarkdown>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};
