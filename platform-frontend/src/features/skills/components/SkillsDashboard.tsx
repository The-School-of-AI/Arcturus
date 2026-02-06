

import React, { useEffect, useState } from 'react';
import { api, API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Zap, Download, CheckCircle, Search, ExternalLink, Globe, Plus, Check } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import axios from 'axios';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuCheckboxItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface Skill {
    name: string;
    version?: string;
    description: string;
    intent_triggers?: string[];
    installed?: boolean;
}

export const SkillsDashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'installed' | 'store'>('installed');
    const [installedSkills, setInstalledSkills] = useState<Skill[]>([]);
    const [storeSkills, setStoreSkills] = useState<Skill[]>([]);

    // Map of Agent -> List of assigned skills
    const [assignments, setAssignments] = useState<Record<string, string[]>>({});
    const [agents, setAgents] = useState<string[]>([]);

    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [installing, setInstalling] = useState<string | null>(null);

    const fetchAll = async () => {
        try {
            setIsLoading(true);
            const [localRes, storeRes, agentsRes, assignRes] = await Promise.all([
                axios.get(`${API_BASE}/skills/list`),
                axios.get(`${API_BASE}/skills/store`).catch(() => ({ data: [] })),
                axios.get(`${API_BASE}/skills/agents`).catch(() => ({ data: [] })),
                axios.get(`${API_BASE}/skills/assignments`).catch(() => ({ data: {} }))
            ]);

            setInstalledSkills(localRes.data);
            setStoreSkills(storeRes.data);
            setAgents(agentsRes.data);
            setAssignments(assignRes.data);
        } catch (e) {
            console.error("Failed to fetch skills", e);
        } finally {
            setIsLoading(false);
        }
    };

    const installSkill = async (skillName: string) => {
        setInstalling(skillName);
        try {
            await axios.post(`${API_BASE}/skills/${skillName}/install`);
            alert(`Installed ${skillName}`);
            fetchAll(); // Refresh to move it to "Installed" list
        } catch (e) {
            alert("Failed to install skill");
        } finally {
            setInstalling(null);
        }
    };

    const toggleAssignment = async (agentName: string, skillName: string, checked: boolean) => {
        try {
            // Optimistic update
            const newAssignments = { ...assignments };
            if (!newAssignments[agentName]) newAssignments[agentName] = [];

            if (checked) {
                if (!newAssignments[agentName].includes(skillName)) newAssignments[agentName].push(skillName);
            } else {
                newAssignments[agentName] = newAssignments[agentName].filter(s => s !== skillName);
            }
            setAssignments(newAssignments);

            await axios.post(`${API_BASE}/skills/toggle`, { agent_name: agentName, skill_name: skillName, active: checked });
        } catch (e) {
            alert("Failed to update assignment");
            fetchAll(); // Revert on error
        }
    };

    useEffect(() => {
        fetchAll();
    }, []);

    const displayedSkills = (activeTab === 'installed' ? installedSkills : storeSkills).filter(s =>
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
                            {activeTab === 'installed' ? `${installedSkills.length} Installed Skills` : "Community Skills Repository"}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex bg-muted/50 p-1 rounded-lg">
                        <button
                            onClick={() => setActiveTab('installed')}
                            className={cn(
                                "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                                activeTab === 'installed' ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            Installed
                        </button>
                        <button
                            onClick={() => setActiveTab('store')}
                            className={cn(
                                "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                                activeTab === 'store' ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <Globe className="w-3 h-3 inline-block mr-2" />
                            Community Store
                        </button>
                    </div>
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            placeholder={activeTab === 'installed' ? "Search installed skills..." : "Browse 500+ community skills..."}
                            className="pl-9 bg-black/20"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>
            </div>

            {/* Content */}
            <ScrollArea className="flex-1 p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {displayedSkills.map((skill: any) => {
                        const isInstalled = installedSkills.some(is => is.name === skill.name);

                        return (
                            <div key={skill.name} className="group relative bg-card/50 border border-border/50 rounded-xl p-5 hover:border-neon-purple/50 hover:bg-neon-purple/1 transition-all duration-300 flex flex-col gap-3">
                                <div className="flex justify-between items-start">
                                    <h3 className="font-bold text-lg capitalize truncate pr-2" title={skill.name}>{skill.name.replace(/-/g, ' ')}</h3>
                                    {isInstalled && activeTab === 'store' && (
                                        <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30 gap-1 shrink-0">
                                            <CheckCircle className="w-3 h-3" />
                                            Owned
                                        </Badge>
                                    )}
                                </div>

                                <p className="text-sm text-muted-foreground line-clamp-2 min-h-[40px]">
                                    {skill.description}
                                </p>

                                <div className="flex flex-wrap gap-1 mt-2 min-h-[24px]">
                                    {(skill.intent_triggers || []).slice(0, 3).map((trigger: string) => (
                                        <Badge key={trigger} variant="secondary" className="text-[10px] bg-white/5 text-muted-foreground">
                                            "{trigger}"
                                        </Badge>
                                    ))}
                                </div>

                                <div className="mt-auto pt-4 border-t border-white/5 flex items-center justify-between text-xs text-muted-foreground">
                                    <span className="font-mono opacity-50">{skill.version ? `v${skill.version}` : 'latest'}</span>

                                    {activeTab === 'installed' ? (
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                                                    <Plus className="w-3 h-3" /> Assign
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="w-56">
                                                {agents.map(agent => {
                                                    const assigned = assignments[agent]?.includes(skill.name);
                                                    return (
                                                        <DropdownMenuCheckboxItem
                                                            key={agent}
                                                            checked={assigned}
                                                            onCheckedChange={(checked) => toggleAssignment(agent, skill.name, checked)}
                                                        >
                                                            {agent}
                                                        </DropdownMenuCheckboxItem>
                                                    );
                                                })}
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    ) : (
                                        !isInstalled && (
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="h-7 text-xs hover:text-neon-purple"
                                                onClick={() => installSkill(skill.name)}
                                                disabled={installing === skill.name}
                                            >
                                                {installing === skill.name ? (
                                                    <span className="animate-spin mr-1">⏳</span>
                                                ) : <Download className="w-3 h-3 mr-1" />}
                                                Install
                                            </Button>
                                        )
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </ScrollArea>
        </div>
    );
};
