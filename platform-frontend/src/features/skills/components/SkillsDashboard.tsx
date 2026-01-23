import React, { useEffect, useState } from 'react';
import { api, API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Zap, Download, CheckCircle, Search, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import axios from 'axios';

interface Skill {
    name: string;
    version: string;
    description: string;
    intent_triggers: string[];
    installed: boolean;
}

export const SkillsDashboard: React.FC = () => {
    const [skills, setSkills] = useState<Skill[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [installUrl, setInstallUrl] = useState('');

    const fetchSkills = async () => {
        try {
            setIsLoading(true);
            const res = await axios.get(`${API_BASE}/skills`);
            setSkills(res.data);
        } catch (e) {
            console.error("Failed to fetch skills", e);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchSkills();
    }, []);

    const filteredSkills = skills.filter(s =>
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full bg-background/50 backdrop-blur-sm">
            {/* Header */}
            <div className="p-6 border-b border-border/50 flex flex-col gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-neon-purple/10 rounded-xl border border-neon-purple/20">
                        <Zap className="w-6 h-6 text-neon-purple" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold tracking-tight">Skill Store</h1>
                        <p className="text-xs text-muted-foreground uppercase tracking-widest">
                            Extend Agent Capabilities
                        </p>
                    </div>
                </div>

                <div className="flex gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            placeholder="Search installed skills..."
                            className="pl-9 bg-black/20"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <div className="flex gap-2">
                        <Input
                            placeholder="GitHub URL (Coming Soon)"
                            className="w-[300px] bg-black/20 opacity-50 cursor-not-allowed"
                            disabled
                            value={installUrl}
                            onChange={(e) => setInstallUrl(e.target.value)}
                        />
                        <Button disabled variant="outline" className="gap-2 opacity-50">
                            <Download className="w-4 h-4" />
                            Install
                        </Button>
                    </div>
                </div>
            </div>

            {/* Content */}
            <ScrollArea className="flex-1 p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {isLoading && (
                        <div className="col-span-full py-20 text-center text-muted-foreground animate-pulse">
                            Loading Skills...
                        </div>
                    )}

                    {!isLoading && filteredSkills.map((skill) => (
                        <div key={skill.name} className="group relative bg-card/50 border border-border/50 rounded-xl p-5 hover:border-neon-purple/50 hover:bg-neon-purple/5 transition-all duration-300 flex flex-col gap-3">
                            <div className="flex justify-between items-start">
                                <h3 className="font-bold text-lg capitalize">{skill.name.replace(/_/g, ' ')}</h3>
                                {skill.installed && (
                                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30 gap-1">
                                        <CheckCircle className="w-3 h-3" />
                                        Installed
                                    </Badge>
                                )}
                            </div>

                            <p className="text-sm text-muted-foreground line-clamp-2 min-h-[40px]">
                                {skill.description}
                            </p>

                            <div className="flex flex-wrap gap-1 mt-2">
                                {skill.intent_triggers.map(trigger => (
                                    <Badge key={trigger} variant="secondary" className="text-[10px] bg-white/5 text-muted-foreground">
                                        "{trigger}"
                                    </Badge>
                                ))}
                            </div>

                            <div className="mt-auto pt-4 border-t border-white/5 flex items-center justify-between text-xs text-muted-foreground">
                                <span className="font-mono">v{skill.version}</span>
                                <Button variant="ghost" size="sm" className="h-6 text-[10px] gap-1 hover:text-neon-purple">
                                    View Source <ExternalLink className="w-3 h-3" />
                                </Button>
                            </div>
                        </div>
                    ))}

                    {!isLoading && filteredSkills.length === 0 && (
                        <div className="col-span-full py-20 flex flex-col items-center justify-center text-center opacity-40 gap-4">
                            <div className="p-6 bg-muted/50 rounded-full">
                                <Zap className="w-12 h-12" />
                            </div>
                            <div>
                                <h3 className="text-lg font-medium">No Skills Found</h3>
                                <p className="text-sm">Try installing standard skills or check your query.</p>
                            </div>
                        </div>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};
