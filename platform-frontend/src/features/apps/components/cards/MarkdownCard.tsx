import React from 'react';
import { BaseCard } from './BaseCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTheme } from '@/components/theme';
import { cn } from '@/lib/utils';

export interface MarkdownCardProps {
    title?: string;
    content?: string;
}

export const MarkdownCard: React.FC<MarkdownCardProps> = ({ title, content = "# Hello Markdown\n\n* Item 1\n* Item 2\n\n> This is a quote." }) => {
    const { theme } = useTheme();
    return (
        <BaseCard title={title}>
            <div className={cn("prose prose-xs max-w-none", theme === 'dark' ? "prose-invert" : "")}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {content}
                </ReactMarkdown>
            </div>
        </BaseCard>
    );
};
