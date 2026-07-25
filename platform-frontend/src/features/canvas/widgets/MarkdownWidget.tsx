import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTheme } from '@/components/theme';

interface MarkdownWidgetProps {
    content: string;
    title?: string;
}

const MarkdownWidget: React.FC<MarkdownWidgetProps> = ({ content = '', title }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && (
                <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                </div>
            )}
            <div className={`px-4 py-3 prose prose-sm max-w-none ${isDark ? 'prose-invert' : ''}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
        </div>
    );
};

export default MarkdownWidget;
