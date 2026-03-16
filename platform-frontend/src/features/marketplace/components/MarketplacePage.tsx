// platform-frontend/src/features/marketplace/components/MarketplacePage.tsx

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Store, Search, Shield, Package, Download, Lock, Unlock,
  Flag, CheckCircle, XCircle, AlertTriangle, DollarSign,
  RotateCcw, Pin,
} from 'lucide-react';

// Types
interface SkillInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  category: string;
  permissions: string[];
  tool_count: number;
}

interface PricingInfo {
  skill_name: string;
  tier: string;
  price_cents: number;
  currency: string;
}

interface ModerationItem {
  skill_name: string;
  status: string;
  flags_count: number;
  resolution: string | null;
}

interface VersionInfo {
  skill_name: string;
  current_version: string | null;
  pinned: boolean;
  history_count: number;
}

type Tab = 'browse' | 'moderation' | 'my-skills';

export const MarketplacePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('browse');
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [categories, setCategories] = useState<Record<string, number>>({});
  const [moderationQueue, setModerationQueue] = useState<ModerationItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [pricing, setPricing] = useState<Record<string, PricingInfo>>({});
  const [isLoading, setIsLoading] = useState(true);

  // Fetch data
  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [skillsRes, catsRes, modRes] = await Promise.all([
        axios.get(`${API_BASE}/marketplace/skills`),
        axios.get(`${API_BASE}/marketplace/categories`).catch(() => ({ data: {} })),
        axios.get(`${API_BASE}/marketplace/moderation/queue`).catch(() => ({ data: [] })),
      ]);
      setSkills(skillsRes.data);
      setCategories(catsRes.data);
      setModerationQueue(modRes.data);

      // Fetch pricing for all skills
      const pricingMap: Record<string, PricingInfo> = {};
      for (const skill of skillsRes.data) {
        try {
          const res = await axios.get(`${API_BASE}/marketplace/skills/${skill.name}/pricing`);
          pricingMap[skill.name] = res.data;
        } catch {
          pricingMap[skill.name] = {
            skill_name: skill.name, tier: 'free', price_cents: 0, currency: 'usd'
          };
        }
      }
      setPricing(pricingMap);
    } catch (e) {
      console.error('Failed to fetch marketplace data', e);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter skills
  const filteredSkills = skills.filter(s => {
    const matchesSearch = !searchQuery ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || s.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Format price
  const formatPrice = (info: PricingInfo) => {
    if (info.tier === 'free') return 'Free';
    return `$${(info.price_cents / 100).toFixed(2)}`;
  };

  // --- Tab: Browse ---
  const BrowseTab = () => (
    <>
      {/* Category pills */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setSelectedCategory(null)}
          className={cn(
            "px-3 py-1 rounded-full text-xs font-medium transition-colors",
            !selectedCategory
              ? "bg-neon-purple/20 text-neon-purple border border-neon-purple/30"
              : "bg-muted/50 text-muted-foreground hover:bg-muted"
          )}
        >
          All ({skills.length})
        </button>
        {Object.entries(categories).map(([cat, count]) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={cn(
              "px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize",
              selectedCategory === cat
                ? "bg-neon-purple/20 text-neon-purple border border-neon-purple/30"
                : "bg-muted/50 text-muted-foreground hover:bg-muted"
            )}
          >
            {cat} ({count})
          </button>
        ))}
      </div>

      {/* Skill cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredSkills.map(skill => {
          const price = pricing[skill.name];
          return (
            <div key={skill.name}
              className="group bg-card/50 border border-border/50 rounded-xl p-5
                         hover:border-neon-purple/50 transition-all duration-300 flex flex-col gap-3"
            >
              <div className="flex justify-between items-start">
                <h3 className="font-bold text-lg truncate pr-2">{skill.name}</h3>
                {price && (
                  <Badge
                    variant="outline"
                    className={cn(
                      "shrink-0",
                      price.tier === 'free'
                        ? "bg-green-500/10 text-green-500 border-green-500/30"
                        : "bg-amber-500/10 text-amber-500 border-amber-500/30"
                    )}
                  >
                    {price.tier === 'free' ? (
                      <><CheckCircle className="w-3 h-3 mr-1" />Free</>
                    ) : (
                      <><DollarSign className="w-3 h-3 mr-1" />{formatPrice(price)}</>
                    )}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">
                {skill.description}
              </p>
              <div className="flex gap-1 flex-wrap">
                <Badge variant="secondary" className="text-[10px]">{skill.category}</Badge>
                <Badge variant="secondary" className="text-[10px]">{skill.tool_count} tools</Badge>
              </div>
              <div className="mt-auto pt-3 border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-muted-foreground font-mono">
                  v{skill.version} · by {skill.author}
                </span>
                <Button size="sm" variant="ghost" className="h-7 text-xs hover:text-neon-purple">
                  <Download className="w-3 h-3 mr-1" />
                  {price?.tier === 'free' ? 'Install' : 'Purchase'}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );

  // --- Tab: Moderation ---
  const ModerationTab = () => (
    <div className="space-y-3">
      {moderationQueue.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Moderation queue is empty</p>
          <p className="text-xs mt-1">No skills require review</p>
        </div>
      ) : (
        moderationQueue.map(item => (
          <div key={item.skill_name}
            className="bg-card/50 border border-border/50 rounded-lg p-4
                       flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              <div>
                <h4 className="font-semibold">{item.skill_name}</h4>
                <p className="text-xs text-muted-foreground">
                  {item.flags_count} flag(s) · Status: {item.status}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="h-7 text-xs">
                <CheckCircle className="w-3 h-3 mr-1" />Approve
              </Button>
              <Button size="sm" variant="destructive" className="h-7 text-xs">
                <XCircle className="w-3 h-3 mr-1" />Suspend
              </Button>
            </div>
          </div>
        ))
      )}
    </div>
  );

  // --- Tab: My Skills ---
  const MySkillsTab = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {skills.map(skill => (
        <div key={skill.name}
          className="bg-card/50 border border-border/50 rounded-lg p-4 space-y-3"
        >
          <div className="flex justify-between items-center">
            <h4 className="font-semibold">{skill.name}</h4>
            <span className="text-xs font-mono text-muted-foreground">v{skill.version}</span>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" className="h-7 text-xs">
              <Pin className="w-3 h-3 mr-1" />Pin
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-xs">
              <RotateCcw className="w-3 h-3 mr-1" />Rollback
            </Button>
          </div>
        </div>
      ))}
    </div>
  );

  // --- Tab config ---
  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'browse', label: 'Browse', icon: <Store className="w-3 h-3" /> },
    { id: 'moderation', label: 'Moderation', icon: <Shield className="w-3 h-3" /> },
    { id: 'my-skills', label: 'My Skills', icon: <Package className="w-3 h-3" /> },
  ];

  return (
    <div className="flex flex-col h-full bg-background/50 backdrop-blur-sm">
      {/* Header */}
      <div className="p-6 border-b border-border/50 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-neon-purple/10 rounded-xl border border-neon-purple/20">
            <Store className="w-6 h-6 text-neon-purple" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Bazaar Marketplace</h1>
            <p className="text-xs text-muted-foreground uppercase tracking-widest">
              {skills.length} Skills Available
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex bg-muted/50 p-1 rounded-lg">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-4 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-2",
                  activeTab === tab.id
                    ? "bg-background shadow text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.icon}
                {tab.label}
                {tab.id === 'moderation' && moderationQueue.length > 0 && (
                  <Badge className="bg-red-500/80 text-white text-[10px] px-1.5">{moderationQueue.length}</Badge>
                )}
              </button>
            ))}
          </div>

          {activeTab === 'browse' && (
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search marketplace skills..."
                className="pl-9 bg-black/20"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 p-6">
        {activeTab === 'browse' && <BrowseTab />}
        {activeTab === 'moderation' && <ModerationTab />}
        {activeTab === 'my-skills' && <MySkillsTab />}
      </ScrollArea>
    </div>
  );
};

export default MarketplacePage;
