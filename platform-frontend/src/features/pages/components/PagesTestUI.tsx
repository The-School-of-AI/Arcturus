import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ExternalLink, Download, RefreshCw, MessageSquare, Eye, Share2 } from 'lucide-react';

interface SparkPage {
  id: string;
  title: string;
  query: string;
  template: string;
  sections: PageSection[];
  citations: Record<string, any>;
  created_at: string;
  created_by: string;
  metadata: any;
}

interface PageSection {
  id: string;
  type: string;
  title: string;
  blocks: PageBlock[];
  charts?: any[];
  metadata?: any;
}

interface PageBlock {
  kind: string;
  text?: string;
  metric?: string;
  value?: string;
  source?: string;
  style?: string;
  title?: string;
  url?: string;
  description?: string;
  chart_type?: string;
  data?: any;
  config?: any;
}

export const PagesTestUI: React.FC = () => {
  const [query, setQuery] = useState('');
  const [template, setTemplate] = useState('topic_overview');
  const [loading, setLoading] = useState(false);
  const [pages, setPages] = useState<SparkPage[]>([]);
  const [selectedPage, setSelectedPage] = useState<SparkPage | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  // Load pages on component mount
  useEffect(() => {
    fetchPages();
  }, []);

  const fetchPages = async () => {
    try {
      const response = await fetch('/api/pages');
      const data = await response.json();
      setPages(data);
    } catch (error) {
      console.error('Failed to fetch pages:', error);
    }
  };

  const generatePage = async () => {
    if (!query.trim()) return;

    setLoading(true);
    try {
      const response = await fetch('/api/pages/pages/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), template })
      });
      
      const data = await response.json();
      setJobId(data.job_id);
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        const jobResponse = await fetch(`/api/pages/jobs/${data.job_id}`);
        const jobData = await jobResponse.json();
        
        if (jobData.status === 'completed') {
          clearInterval(pollInterval);
          setLoading(false);
          setJobId(null);
          fetchPages();
        }
      }, 1000);
    } catch (error) {
      console.error('Failed to generate page:', error);
      setLoading(false);
    }
  };

  const refreshSection = async (pageId: string, sectionId: string) => {
    try {
      await fetch(`/api/pages/${pageId}/sections/${sectionId}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ focus: 'latest data' })
      });
      
      // Refresh the page data
      const response = await fetch(`/api/pages/${pageId}`);
      const updatedPage = await response.json();
      setSelectedPage(updatedPage);
    } catch (error) {
      console.error('Failed to refresh section:', error);
    }
  };

  const exportPage = async (pageId: string, format: string) => {
    try {
      const response = await fetch(`/api/pages/${pageId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format, include_charts: true })
      });
      
      const data = await response.json();
      if (data.success) {
        // Open exported file
        window.open(data.path, '_blank');
      }
    } catch (error) {
      console.error('Failed to export page:', error);
    }
  };

  const sharePage = async (pageId: string, shareType: 'link' | 'users', password?: string) => {
    try {
      const body: any = { 
        action: 'share', 
        share_type: shareType 
      };
      if (password) body.password = password;

      const response = await fetch(`/api/pages/${pageId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      const data = await response.json();
      if (data.share_url) {
        navigator.clipboard.writeText(window.location.origin + data.share_url);
        alert('Share URL copied to clipboard!');
      }
    } catch (error) {
      console.error('Failed to share page:', error);
    }
  };

  const renderBlock = (block: PageBlock, pageId: string, sectionId: string) => {
    switch (block.kind) {
      case 'markdown':
        return (
          <div className="prose prose-sm max-w-none whitespace-pre-wrap">
            {block.text}
          </div>
        );
      
      case 'highlight':
        return (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4">
              <div className="flex justify-between items-center">
                <div>
                  <h4 className="font-semibold">{block.metric}</h4>
                  <p className="text-2xl font-bold text-blue-600">{block.value}</p>
                  <p className="text-sm text-gray-600">{block.source}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      
      case 'media':
        return (
          <Card className="border-dashed">
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <ExternalLink className="h-4 w-4" />
                <h4 className="font-medium">{block.title}</h4>
              </div>
              <a href={block.url} target="_blank" rel="noopener noreferrer" 
                 className="text-blue-600 hover:underline">
                View {block.url?.includes('video') ? 'video' : 'image'}
              </a>
              <p className="text-sm text-gray-600 mt-1">{block.description}</p>
            </CardContent>
          </Card>
        );
      
      case 'table':
        const data = block.data || [];
        if (data.length === 0) return null;
        
        return (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse border border-gray-300">
              <thead>
                <tr className="bg-gray-100">
                  {Object.keys(data[0] || {}).map(key => (
                    <th key={key} className="border border-gray-300 p-2 text-left font-medium">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row: any, idx: number) => (
                  <tr key={idx}>
                    {Object.values(row).map((value: any, cellIdx: number) => (
                      <td key={cellIdx} className="border border-gray-300 p-2">
                        {String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      
      case 'chart':
        return (
          <Card className="bg-gray-50">
            <CardContent className="pt-4 text-center">
              <h4 className="font-medium mb-2">{block.title}</h4>
              <div className="bg-white rounded p-8 border-2 border-dashed border-gray-300">
                <p className="text-gray-500">📊 {block.chart_type?.toUpperCase()} Chart</p>
                <p className="text-sm text-gray-400 mt-1">[Interactive chart would render here]</p>
              </div>
            </CardContent>
          </Card>
        );
      
      default:
        return (
          <div className="text-sm text-gray-500 italic">
            Unknown block type: {block.kind}
          </div>
        );
    }
  };

  const renderSection = (section: PageSection, pageId: string) => (
    <Card key={section.id} className="mb-4">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">{section.title}</CardTitle>
        <div className="flex gap-2">
          <Badge variant="outline">{section.type}</Badge>
          <Button 
            size="sm" 
            variant="outline"
            onClick={() => refreshSection(pageId, section.id)}
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {section.blocks?.map((block, idx) => (
          <div key={idx}>
            {renderBlock(block, pageId, section.id)}
          </div>
        ))}
        {section.charts && section.charts.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {section.charts.map((chart, idx) => (
              <Card key={idx} className="bg-gray-50">
                <CardContent className="pt-4 text-center">
                  <p className="font-medium mb-2">{chart.title}</p>
                  <div className="bg-white rounded p-6 border-2 border-dashed border-gray-300">
                    <p className="text-gray-500">📊 {chart.type?.toUpperCase()}</p>
                    <p className="text-xs text-gray-400">[Chart.js visualization]</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            ✨ Spark Pages Test UI
            <Badge variant="secondary">Week 2-3 Features</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="generate" className="space-y-4">
            <TabsList>
              <TabsTrigger value="generate">Generate</TabsTrigger>
              <TabsTrigger value="library">Library ({pages.length})</TabsTrigger>
              {selectedPage && <TabsTrigger value="view">View Page</TabsTrigger>}
            </TabsList>

            <TabsContent value="generate" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2">
                  <Textarea
                    placeholder="Enter your query (e.g. 'blockchain technology market analysis')"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Select value={template} onValueChange={setTemplate}>
                    <SelectTrigger>
                      <SelectValue placeholder="Template" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="topic_overview">Topic Overview</SelectItem>
                      <SelectItem value="product_comparison">Product Comparison</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button 
                    onClick={generatePage} 
                    disabled={loading || !query.trim()}
                    className="w-full"
                  >
                    {loading ? 'Generating...' : 'Generate Page'}
                  </Button>
                </div>
              </div>
              {jobId && (
                <div className="p-3 bg-blue-50 rounded border border-blue-200">
                  <p className="text-sm text-blue-800">
                    Generation job {jobId} in progress... Polling for completion.
                  </p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="library" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {pages.map(page => (
                  <Card key={page.id} className="cursor-pointer hover:shadow-md transition-shadow">
                    <CardHeader>
                      <CardTitle className="text-base truncate">{page.title}</CardTitle>
                      <p className="text-sm text-gray-600 truncate">{page.query}</p>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-between">
                        <div className="flex gap-1">
                          <Badge variant="outline" className="text-xs">{page.template}</Badge>
                          <Badge variant="secondary" className="text-xs">
                            {page.sections?.length || 0} sections
                          </Badge>
                        </div>
                        <div className="flex gap-1">
                          <Button 
                            size="sm" 
                            variant="ghost"
                            onClick={() => setSelectedPage(page)}
                          >
                            <Eye className="h-3 w-3" />
                          </Button>
                          <Button 
                            size="sm" 
                            variant="ghost"
                            onClick={() => exportPage(page.id, 'html')}
                          >
                            <Download className="h-3 w-3" />
                          </Button>
                          <Button 
                            size="sm" 
                            variant="ghost"
                            onClick={() => sharePage(page.id, 'link')}
                          >
                            <Share2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        Created: {new Date(page.created_at).toLocaleDateString()}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="view" className="space-y-4">
              {selectedPage && (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h1 className="text-2xl font-bold">{selectedPage.title}</h1>
                      <p className="text-gray-600">Query: {selectedPage.query}</p>
                    </div>
                    <div className="flex gap-2">
                      {['html', 'pdf', 'markdown', 'docx'].map(format => (
                        <Button 
                          key={format}
                          size="sm" 
                          variant="outline"
                          onClick={() => exportPage(selectedPage.id, format)}
                        >
                          <Download className="h-3 w-3 mr-1" />
                          {format.toUpperCase()}
                        </Button>
                      ))}
                      <Button 
                        size="sm"
                        onClick={() => sharePage(selectedPage.id, 'link')}
                      >
                        <Share2 className="h-3 w-3 mr-1" />
                        Share
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {selectedPage.sections?.map(section => renderSection(section, selectedPage.id))}
                  </div>

                  {/* Citations Section */}
                  {Object.keys(selectedPage.citations || {}).length > 0 && (
                    <Card>
                      <CardHeader>
                        <CardTitle>References</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {Object.entries(selectedPage.citations).map(([id, citation]: [string, any]) => (
                            <div key={id} className="border-l-4 border-blue-200 pl-4">
                              <p className="font-medium">[{id}] {citation.title}</p>
                              <p className="text-sm text-gray-600">{citation.snippet}</p>
                              <p className="text-xs text-gray-500">
                                Credibility: {citation.credibility || 'N/A'} | 
                                Source: {citation.citation_id}
                              </p>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

export default PagesTestUI;