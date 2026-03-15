import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { RefreshCw, MessageSquare, Edit3, Save, X } from 'lucide-react';

interface SectionBlockProps {
  section: {
    id: string;
    type: string;
    title: string;
    blocks: any[];
    charts?: any[];
    metadata?: any;
  };
  pageId: string;
  onRefresh?: (sectionId: string, focus?: string) => void;
  onEdit?: (sectionId: string, newContent: any) => void;
}

export const SectionBlock: React.FC<SectionBlockProps> = ({ 
  section, 
  pageId, 
  onRefresh, 
  onEdit 
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [showCopilot, setShowCopilot] = useState(false);
  const [copilotQuery, setCopilotQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async (focus?: string) => {
    if (!onRefresh) return;
    
    setRefreshing(true);
    try {
      await onRefresh(section.id, focus);
    } finally {
      setRefreshing(false);
    }
  };

  const handleCopilotQuery = async () => {
    if (!copilotQuery.trim()) return;

    try {
      const response = await fetch(`/api/pages/${pageId}/copilot/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: copilotQuery,
          section_id: section.id,
          context: 'section_refinement'
        })
      });

      const data = await response.json();
      if (data.action === 'refresh_section') {
        await handleRefresh(data.focus);
      }
      
      setCopilotQuery('');
    } catch (error) {
      console.error('Copilot query failed:', error);
    }
  };

  const renderBlockContent = (block: any) => {
    switch (block.kind) {
      case 'markdown':
        return (
          <div className="prose prose-sm max-w-none whitespace-pre-wrap">
            {block.text}
          </div>
        );
      
      case 'highlight':
        return (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-semibold text-blue-900">{block.metric}</h4>
            <p className="text-2xl font-bold text-blue-600">{block.value}</p>
            <p className="text-sm text-blue-700">{block.source}</p>
          </div>
        );
      
      case 'media':
        return (
          <div className="border border-dashed border-gray-300 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <h4 className="font-medium">{block.title}</h4>
              <Badge variant="outline">Media</Badge>
            </div>
            <a href={block.url} target="_blank" rel="noopener noreferrer" 
               className="text-blue-600 hover:underline">
              View {block.url?.includes('video') ? 'video' : 'image'}
            </a>
            <p className="text-sm text-gray-600 mt-1">{block.description}</p>
          </div>
        );
      
      case 'chart':
        return (
          <div className="bg-gray-50 border rounded-lg p-6 text-center">
            <h4 className="font-medium mb-2">{block.title}</h4>
            <div className="bg-white rounded border-2 border-dashed border-gray-300 p-8">
              <p className="text-gray-500">📊 {block.chart_type?.toUpperCase()} Chart</p>
              <p className="text-sm text-gray-400 mt-1">[Interactive Chart.js visualization]</p>
            </div>
          </div>
        );
      
      default:
        return (
          <div className="text-sm text-gray-500 italic p-2 bg-gray-50 rounded">
            Unknown block type: {block.kind}
          </div>
        );
    }
  };

  return (
    <Card className="mb-6 border-l-4 border-blue-500">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-lg">{section.title}</CardTitle>
            <Badge variant="secondary">{section.type}</Badge>
            {section.metadata?.enhanced && (
              <Badge variant="default" className="bg-green-600">Enhanced</Badge>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {/* Section-level controls */}
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowCopilot(!showCopilot)}
            >
              <MessageSquare className="h-3 w-3 mr-1" />
              Ask Copilot
            </Button>
            
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleRefresh()}
              disabled={refreshing}
            >
              <RefreshCw className={`h-3 w-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIsEditing(!isEditing)}
            >
              {isEditing ? <X className="h-3 w-3" /> : <Edit3 className="h-3 w-3" />}
            </Button>
          </div>
        </div>
        
        {/* Metadata */}
        {section.metadata && (
          <div className="flex gap-2 text-xs text-gray-600">
            {section.metadata.refreshed_at && (
              <span>Refreshed: {new Date(section.metadata.refreshed_at).toLocaleString()}</span>
            )}
            {section.metadata.chart_count && (
              <span>• {section.metadata.chart_count} charts</span>
            )}
            {section.metadata.media_count && (
              <span>• {section.metadata.media_count} media</span>
            )}
          </div>
        )}
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Inline Copilot Interface */}
        {showCopilot && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4">
              <div className="flex gap-2">
                <Textarea
                  placeholder="Ask the copilot to expand this section, add examples, cite more sources, or simplify..."
                  value={copilotQuery}
                  onChange={(e) => setCopilotQuery(e.target.value)}
                  rows={2}
                  className="flex-1"
                />
                <Button onClick={handleCopilotQuery} disabled={!copilotQuery.trim()}>
                  <MessageSquare className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-2 text-xs text-blue-700">
                💡 Try: "Add more examples", "Cite additional sources", "Simplify this content"
              </div>
            </CardContent>
          </Card>
        )}
        
        {/* Quick Refresh Actions */}
        <div className="flex gap-2 text-sm">
          <Button 
            size="xs" 
            variant="link" 
            onClick={() => handleRefresh('latest data')}
            className="text-blue-600 p-0 h-auto"
          >
            + Latest data
          </Button>
          <Button 
            size="xs" 
            variant="link" 
            onClick={() => handleRefresh('more examples')}
            className="text-blue-600 p-0 h-auto"
          >
            + More examples
          </Button>
          <Button 
            size="xs" 
            variant="link" 
            onClick={() => handleRefresh('additional sources')}
            className="text-blue-600 p-0 h-auto"  
          >
            + More sources
          </Button>
        </div>

        {/* Section Content */}
        <div className="space-y-4">
          {section.blocks?.map((block, idx) => (
            <div key={idx} className="border-l-2 border-gray-200 pl-4">
              {renderBlockContent(block)}
            </div>
          ))}
        </div>

        {/* Charts Section */}
        {section.charts && section.charts.length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium text-gray-700">Visualizations ({section.charts.length})</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {section.charts.map((chart, idx) => (
                <div key={idx} className="bg-gray-50 border rounded-lg p-4 text-center">
                  <p className="font-medium text-sm mb-2">{chart.title || `Chart ${idx + 1}`}</p>
                  <div className="bg-white rounded border-2 border-dashed border-gray-300 p-6">
                    <p className="text-gray-500 text-sm">📊 {chart.type?.toUpperCase()}</p>
                    <p className="text-xs text-gray-400">[Chart.js compatible]</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Edit Mode */}
        {isEditing && (
          <Card className="bg-yellow-50 border-yellow-200">
            <CardContent className="pt-4">
              <div className="space-y-3">
                <Textarea
                  placeholder="Edit section content..."
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  rows={6}
                  className="w-full"
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => {
                    if (onEdit) onEdit(section.id, { content: editContent });
                    setIsEditing(false);
                  }}>
                    <Save className="h-3 w-3 mr-1" />
                    Save Changes
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setIsEditing(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );
};

export default SectionBlock;