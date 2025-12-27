import React from 'react';
import { BaseCard } from './BaseCard';
import { DEFAULT_COLORS } from '../../utils/defaults';

export interface ProfileCardProps {
    title?: string;
    companyName?: string;
    ticker?: string;
    description?: string;
    logoUrl?: string;
    // Feature toggles
    showLogo?: boolean;
    showTicker?: boolean;
    showDescription?: boolean;
    showSector?: boolean;
    // Data from store
    data?: {
        name?: string;
        ticker?: string;
        description?: string;
        sector?: string;
        industry?: string;
        employees?: string;
        logoUrl?: string;
    };
    config?: any;
    style?: any;
}

export const ProfileCard: React.FC<ProfileCardProps> = ({
    title = "Company Profile",
    companyName,
    ticker,
    description,
    logoUrl,
    showLogo = true,
    showTicker = true,
    showDescription = true,
    showSector = true,
    data = {},
    style = {}
}) => {
    // Use data from props or defaults
    const name = data.name || companyName || "Alphabet Inc.";
    const tickerSymbol = data.ticker || ticker || "GOOGL";
    const desc = data.description || description || "Alphabet Inc. provides online advertising services, cloud computing platform, software, and hardware.";
    const logo = data.logoUrl || logoUrl;
    const sector = data.sector || "Technology";
    const industry = data.industry || "Internet Content & Info";
    const employees = data.employees || "~180,000";

    return (
        <BaseCard title={title}>
            <div className="space-y-4">
                <div className="flex items-start gap-4">
                    {showLogo && (
                        <div className="w-12 h-12 rounded bg-white flex items-center justify-center text-charcoal-900 font-bold text-xl shrink-0">
                            {logo ? <img src={logo} className="w-full h-full object-contain p-1" /> : tickerSymbol[0]}
                        </div>
                    )}
                    <div>
                        <h2 className="text-lg font-bold text-foreground" style={{ color: style.textColor }}>{name}</h2>
                        {showTicker && (
                            <div
                                className="text-xs  px-2 py-0.5 rounded inline-block border mt-1"
                                style={{
                                    color: style.accentColor || DEFAULT_COLORS.accent,
                                    backgroundColor: `${style.accentColor || DEFAULT_COLORS.accent}15`,
                                    borderColor: `${style.accentColor || DEFAULT_COLORS.accent}30`
                                }}
                            >
                                {tickerSymbol}
                            </div>
                        )}
                    </div>
                </div>

                {showDescription && (
                    <div className="text-sm leading-relaxed line-clamp-4" style={{ color: style.textColor ? `${style.textColor}99` : '#9ca3af' }}>
                        {desc}
                    </div>
                )}

                {showSector && (
                    <div className="flex gap-4 pt-2 border-t border-border/50">
                        <div className="text-xs">
                            <span className="text-muted-foreground block">Sector</span>
                            <span className="font-medium" style={{ color: style.textColor }}>{sector}</span>
                        </div>
                        <div className="text-xs">
                            <span className="text-muted-foreground block">Industry</span>
                            <span className="font-medium" style={{ color: style.textColor }}>{industry}</span>
                        </div>
                        <div className="text-xs">
                            <span className="text-muted-foreground block">Employees</span>
                            <span className="font-medium" style={{ color: style.textColor }}>{employees}</span>
                        </div>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};
