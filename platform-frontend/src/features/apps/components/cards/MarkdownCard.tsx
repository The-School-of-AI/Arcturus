import React from 'react';
import { BaseCard } from './BaseCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface MarkdownCardProps {
    title?: string;
    content?: string;
}

export const MarkdownCard: React.FC<MarkdownCardProps> = ({ title, content = "# Hello Markdown\n\n* Item 1\n* Item 2\n\n> This is a quote." }) => {
    return (
        <BaseCard title={title}>
            <div className="prose prose-invert prose-xs max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {content}
                </ReactMarkdown>
            </div>
        </BaseCard>
    );
};
