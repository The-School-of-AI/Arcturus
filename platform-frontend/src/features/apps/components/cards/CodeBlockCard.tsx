import React from 'react';
import { BaseCard } from './BaseCard';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

export interface CodeBlockCardProps {
    title?: string;
    code?: string;
    lang?: string;
    data?: any;
    config?: any;
    style?: any;
}

export const CodeBlockCard: React.FC<CodeBlockCardProps> = ({
    title = "Analysis Script",
    code,
    lang = 'python',
    data = {},
    config = {},
    style = {}
}) => {
    // Feature toggles from config
    const showTitle = config.showTitle !== false;
    const highlight = config.highlight !== false;
    const lineNumbers = config.lineNumbers !== false;
    const wordWrap = config.wordWrap === true;

    // Use data.code if available, otherwise fall back to direct prop or default
    const displayCode = data.code || code || `def calculate_fair_value(ticker):\n    data = fetch_financials(ticker)\n    ebitda = data['income_stmt']['ebitda']\n    multiple = 15.0\n    return ebitda * multiple`;
    const displayLang = data.language || lang;

    return (
        <BaseCard title={showTitle ? (data.title || title) : undefined}>
            <div className="h-full overflow-hidden rounded border border-white/5 text-[10px]">
                {highlight ? (
                    <SyntaxHighlighter
                        language={displayLang}
                        style={vscDarkPlus}
                        customStyle={{
                            background: 'transparent',
                            margin: 0,
                            padding: '8px',
                            whiteSpace: wordWrap ? 'pre-wrap' : 'pre'
                        }}
                        showLineNumbers={lineNumbers}
                        wrapLines={wordWrap}
                    >
                        {displayCode}
                    </SyntaxHighlighter>
                ) : (
                    <pre
                        className="p-2 text-muted-foreground"
                        style={{ whiteSpace: wordWrap ? 'pre-wrap' : 'pre' }}
                    >
                        {displayCode}
                    </pre>
                )}
            </div>
        </BaseCard>
    );
};
