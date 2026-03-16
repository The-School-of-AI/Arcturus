import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

interface FeatureFlagsContextValue {
    flags: Record<string, boolean>;
    loading: boolean;
    refetch: () => Promise<void>;
}

const FeatureFlagsContext = createContext<FeatureFlagsContextValue>({
    flags: {},
    loading: true,
    refetch: async () => {},
});

export const FeatureFlagsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [flags, setFlags] = useState<Record<string, boolean>>({});
    const [loading, setLoading] = useState(true);

    const refetch = useCallback(async () => {
        try {
            const res = await axios.get(`${API_BASE}/admin/flags`);
            const flagList: { name: string; enabled: boolean }[] = res.data.flags || [];
            const flagMap: Record<string, boolean> = {};
            for (const f of flagList) {
                flagMap[f.name] = f.enabled;
            }
            setFlags(flagMap);
        } catch {
            console.error('Failed to fetch feature flags');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refetch();
    }, [refetch]);

    return (
        <FeatureFlagsContext.Provider value={{ flags, loading, refetch }}>
            {children}
        </FeatureFlagsContext.Provider>
    );
};

export const useFeatureFlags = (): FeatureFlagsContextValue => {
    return useContext(FeatureFlagsContext);
};
