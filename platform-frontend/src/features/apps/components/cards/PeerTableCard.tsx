import React from 'react';
import { BaseCard } from './BaseCard';

interface PeerTableCardProps {
    title?: string;
    data?: any;
    config?: any;
    style?: any;
    cardId?: string;
    autoFit?: boolean;
    context?: string;
}

const defaultPeers = [
    { name: "Apple", ticker: "AAPL", marketCap: "2.8T", pe: "28.4" },
    { name: "Microsoft", ticker: "MSFT", marketCap: "2.4T", pe: "32.1" },
    { name: "Alphabet", ticker: "GOOGL", marketCap: "1.7T", pe: "24.5", active: true },
    { name: "Meta", ticker: "META", marketCap: "800B", pe: "18.2" },
];

export const PeerTableCard: React.FC<PeerTableCardProps> = ({
    title: propTitle,
    data = {},
    config = {},
    style = {},
    cardId,
    autoFit,
    context
}) => {
    // Use dynamic data if provided, otherwise use defaults
    const peers = data.peers || defaultPeers;
    const tableTitle = data.title || propTitle || "Peer Comparison";

    return (
        <BaseCard title={tableTitle} cardId={cardId} autoFit={autoFit}>
            <div className="w-full text-[10px] text-left">
                <div className="flex border-b border-border/50 pb-2 mb-2 font-bold text-muted-foreground">
                    <div className="flex-1">Company</div>
                    <div className="w-16 text-right">Market Cap</div>
                    <div className="w-12 text-right">P/E</div>
                </div>
                <div className="space-y-1.5">
                    {peers.map((p: any) => (
                        <div key={p.ticker} className={`flex items-center py-1 px-1 rounded ${p.active ? 'bg-primary/10 text-primary' : 'text-foreground/80 hover:bg-muted/50'}`}>
                            <div className="flex-1 flex items-center gap-1.5 min-w-0">
                                <span className="font-bold truncate">{p.name || p.ticker}</span>
                                <span className="opacity-40  text-[9px]">{p.ticker}</span>
                            </div>
                            <div className="w-16 text-right ">{p.marketCap || p.cap}</div>
                            <div className="w-12 text-right ">{p.pe}</div>
                        </div>
                    ))}
                </div>
            </div>
        </BaseCard>
    );
};
