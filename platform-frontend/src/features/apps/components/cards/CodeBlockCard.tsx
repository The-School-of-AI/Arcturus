import React from 'react';
import { BaseCard } from './BaseCard';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

export const CodeBlockCard: React.FC<{ title?: string, code?: string, lang?: string }> = ({
    title = "Analysis Script",
    code = `def calculate_fair_value(ticker):\n    data = fetch_financials(ticker)\n    ebitda = data['income_stmt']['ebitda']\n    multiple = 15.0\n    return ebitda * multiple`,
    lang = 'python'
}) => {
    return (
        <BaseCard title={title}>
            <div className="h-full overflow-hidden rounded border border-white/5 text-[10px]">
                <SyntaxHighlighter
                    language={lang}
                    style={vscDarkPlus}
                    customStyle={{ background: 'transparent', margin: 0, padding: '8px' }}
                >
                    {code}
                </SyntaxHighlighter>
            </div>
        </BaseCard>
    );
};
