import React from 'react';
import { BaseCard } from './BaseCard';

export interface ProfileCardProps {
    title?: string;
    companyName?: string;
    ticker?: string;
    description?: string;
    logoUrl?: string; // Optional
}

export const ProfileCard: React.FC<ProfileCardProps> = ({ title = "Company Profile", companyName = "Alphabet Inc.", ticker = "GOOGL", description = "Alphabet Inc. provides online advertising services, cloud computing platform, software, and hardware.", logoUrl }) => {
    return (
        <BaseCard title={title}>
            <div className="space-y-4">
                <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded bg-white flex items-center justify-center text-charcoal-900 font-bold text-xl shrink-0">
                        {logoUrl ? <img src={logoUrl} className="w-full h-full object-contain p-1" /> : ticker[0]}
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-foreground">{companyName}</h2>
                        <div className="text-xs font-mono text-neon-yellow px-2 py-0.5 bg-neon-yellow/10 rounded inline-block border border-neon-yellow/20 mt-1">
                            {ticker}
                        </div>
                    </div>
                </div>
                <div className="text-sm text-gray-400 leading-relaxed line-clamp-4">
                    {description}
                </div>
                <div className="flex gap-4 pt-2 border-t border-white/5">
                    <div className="text-xs">
                        <span className="text-muted-foreground block">Sector</span>
                        <span className="text-foreground font-medium">Technology</span>
                    </div>
                    <div className="text-xs">
                        <span className="text-muted-foreground block">Industry</span>
                        <span className="text-foreground font-medium">Internet Content & Info</span>
                    </div>
                    <div className="text-xs">
                        <span className="text-muted-foreground block">Employees</span>
                        <span className="text-foreground font-medium">~180,000</span>
                    </div>
                </div>
            </div>
        </BaseCard>
    );
};
