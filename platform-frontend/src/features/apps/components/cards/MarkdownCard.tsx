import React from 'react';
import { BaseCard } from './BaseCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import DOMPurify from 'dompurify';
import { useTheme } from '@/components/theme';
import { cn } from '@/lib/utils';

export interface MarkdownCardProps {
    title?: string;
    content?: string;
    cardId?: string;
    autoFit?: boolean;
}

export const MarkdownCard: React.FC<MarkdownCardProps> = ({
    title,
    content = "# Hello Markdown\n\n* Item 1\n* Item 2\n\n> This is a quote.",
    cardId,
    autoFit = true
}) => {
    const { theme } = useTheme();

    // Sanitize content to prevent XSS while allowing safe HTML
    const sanitizedContent = DOMPurify.sanitize(content, {
        ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'span', 'img', 'hr'],
        ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'id', 'style']
    });

    return (
        <BaseCard title={title} cardId={cardId} autoFit={autoFit}>
            <div className={cn("prose prose-xs max-w-none", theme === 'dark' ? "prose-invert" : "")}>
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                >
                    {sanitizedContent}
                </ReactMarkdown>
            </div>
        </BaseCard>
    );
};

