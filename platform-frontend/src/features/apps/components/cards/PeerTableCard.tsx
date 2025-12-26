import React from 'react';
import { BaseCard } from './BaseCard';

export const PeerTableCard: React.FC<{ title?: string }> = ({ title = "Peer Comparison" }) => {
    const peers = [
        { name: "Apple", ticker: "AAPL", cap: "2.8T", pe: "28.4" },
        { name: "Microsoft", ticker: "MSFT", cap: "2.4T", pe: "32.1" },
        { name: "Alphabet", ticker: "GOOGL", cap: "1.7T", pe: "24.5", active: true },
        { name: "Meta", ticker: "META", cap: "800B", pe: "18.2" },
    ];

    return (
        <BaseCard title={title}>
            <div className="w-full text-[10px] text-left">
                <div className="flex border-b border-white/5 pb-2 mb-2 font-bold text-muted-foreground">
                    <div className="flex-1">Company</div>
                    <div className="w-16 text-right">Market Cap</div>
                    <div className="w-12 text-right">P/E</div>
                </div>
                <div className="space-y-1.5">
                    {peers.map(p => (
                        <div key={p.ticker} className={`flex items-center py-1 px-1 rounded ${p.active ? 'bg-primary/10 text-primary' : 'text-foreground/80 hover:bg-white/5'}`}>
                            <div className="flex-1 flex items-center gap-1.5 min-w-0">
                                <span className="font-bold truncate">{p.name}</span>
                                <span className="opacity-40 font-mono text-[9px]">{p.ticker}</span>
                            </div>
                            <div className="w-16 text-right font-mono">{p.cap}</div>
                            <div className="w-12 text-right font-mono">{p.pe}</div>
                        </div>
                    ))}
                </div>
            </div>
        </BaseCard>
    );
};
