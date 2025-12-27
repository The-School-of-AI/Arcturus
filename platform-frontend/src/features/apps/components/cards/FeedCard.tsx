import React from 'react';
import { BaseCard } from './BaseCard';
import { ExternalLink } from 'lucide-react';

export interface FeedCardProps {
    title: string;
    items?: { id: string, text: string, time: string, source?: string, url?: string }[];
}

export const FeedCard: React.FC<FeedCardProps> = ({ title, items = [
    { id: '1', text: "Quarterly earnings report released exceeding expectations.", time: "2h ago", source: "Bloomberg" },
    { id: '2', text: "New strategic partnership announced with major cloud provider.", time: "5h ago", source: "Reuters" },
    { id: '3', text: "Stock price reaches all-time high amidst market rally.", time: "1d ago", source: "CNBC" },
] }) => {
    return (
        <BaseCard title={title}>
            <div className="space-y-3">
                {items.map(item => (
                    <div key={item.id} className="group relative pl-4 border-l-2 border-border/50 hover:border-primary/50 transition-colors pb-1">
                        <div className="flex items-center justify-between mb-0.5">
                            <div className="text-[10px] uppercase font-bold text-primary opacity-80">{item.source}</div>
                            <div className="text-[10px] text-muted-foreground">{item.time}</div>
                        </div>
                        <div className="text-xs text-foreground/90 leading-relaxed group-hover:text-foreground transition-colors">
                            {item.text}
                        </div>
                        {item.url && (
                            <a href={item.url} target="_blank" className="absolute inset-0 flex items-end justify-end p-1 opacity-0 group-hover:opacity-100 pointer-events-none">
                                <ExternalLink className="w-3 h-3 text-muted-foreground" />
                            </a>
                        )}
                    </div>
                ))}
            </div>
        </BaseCard>
    );
};
