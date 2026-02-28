import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, FileText, File, Image, Share2, ExternalLink, Check } from 'lucide-react';

interface ExportControlsProps {
  pageId: string;
  pageTitle?: string;
  onExport?: (format: string, options: any) => void;
}

export const ExportControls: React.FC<ExportControlsProps> = ({ 
  pageId, 
  pageTitle = 'Untitled Page',
  onExport 
}) => {
  const [selectedFormat, setSelectedFormat] = useState('html');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeMedia, setIncludeMedia] = useState(true);
  const [includeCitations, setIncludeCitations] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [lastExport, setLastExport] = useState<any>(null);
  const [shareUrl, setShareUrl] = useState('');
  const [sharing, setSharing] = useState(false);

  const exportFormats = [
    { value: 'html', label: 'HTML', icon: FileText, description: 'Web page with styling' },
    { value: 'pdf', label: 'PDF', icon: File, description: 'Print-ready document' },
    { value: 'markdown', label: 'Markdown', icon: FileText, description: 'Plain text with formatting' },
    { value: 'docx', label: 'DOCX', icon: File, description: 'Microsoft Word document' }
  ];

  const handleExport = async () => {
    setExporting(true);
    
    try {
      const options = {
        include_charts: includeCharts,
        include_media: includeMedia,
        include_citations: includeCitations
      };

      const response = await fetch(`/api/pages/${pageId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: selectedFormat, ...options })
      });

      const result = await response.json();
      
      if (result.success) {
        setLastExport(result);
        
        // Trigger download or callback
        if (onExport) {
          onExport(selectedFormat, result);
        } else {
          // Direct download
          window.open(result.path, '_blank');
        }
      } else {
        console.error('Export failed:', result.error);
      }
    } catch (error) {
      console.error('Export error:', error);
    } finally {
      setExporting(false);
    }
  };

  const handleShare = async () => {
    setSharing(true);
    
    try {
      const response = await fetch(`/api/pages/${pageId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'share',
          share_type: 'link'
        })
      });

      const result = await response.json();
      
      if (result.share_url) {
        const fullUrl = window.location.origin + result.share_url;
        setShareUrl(fullUrl);
        
        // Copy to clipboard
        navigator.clipboard.writeText(fullUrl);
      }
    } catch (error) {
      console.error('Share error:', error);
    } finally {
      setSharing(false);
    }
  };

  const selectedFormatInfo = exportFormats.find(f => f.value === selectedFormat);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="h-5 w-5" />
          Export & Share Controls
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Export Format Selection */}
        <div className="space-y-3">
          <label className="text-sm font-medium">Export Format</label>
          <Select value={selectedFormat} onValueChange={setSelectedFormat}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {exportFormats.map(format => (
                <SelectItem key={format.value} value={format.value}>
                  <div className="flex items-center gap-2">
                    <format.icon className="h-4 w-4" />
                    <div>
                      <div>{format.label}</div>
                      <div className="text-xs text-gray-500">{format.description}</div>
                    </div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          {selectedFormatInfo && (
            <p className="text-sm text-gray-600">
              {selectedFormatInfo.description}
            </p>
          )}
        </div>

        {/* Export Options */}
        <div className="space-y-3">
          <label className="text-sm font-medium">Export Options</label>
          
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="charts" 
                checked={includeCharts} 
                onCheckedChange={setIncludeCharts}
              />
              <label htmlFor="charts" className="text-sm">
                Include charts and visualizations
              </label>
            </div>
            
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="media" 
                checked={includeMedia} 
                onCheckedChange={setIncludeMedia}
              />
              <label htmlFor="media" className="text-sm">
                Include media blocks (images, videos)
              </label>
            </div>
            
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="citations" 
                checked={includeCitations} 
                onCheckedChange={setIncludeCitations}
              />
              <label htmlFor="citations" className="text-sm">
                Include citations and references
              </label>
            </div>
          </div>
        </div>

        {/* Export Actions */}
        <div className="flex gap-3">
          <Button 
            onClick={handleExport} 
            disabled={exporting}
            className="flex-1"
          >
            {exporting ? (
              'Exporting...'
            ) : (
              <>
                <Download className="h-4 w-4 mr-2" />
                Export as {selectedFormat.toUpperCase()}
              </>
            )}
          </Button>
          
          <Button 
            variant="outline" 
            onClick={handleShare}
            disabled={sharing}
          >
            {sharing ? (
              'Creating link...'
            ) : (
              <>
                <Share2 className="h-4 w-4 mr-2" />
                Share
              </>
            )}
          </Button>
        </div>

        {/* Last Export Results */}
        {lastExport && (
          <Card className="bg-green-50 border-green-200">
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium">Export Complete</span>
                </div>
                <Badge variant="secondary">{lastExport.format?.toUpperCase()}</Badge>
              </div>
              
              <div className="mt-2 text-sm text-gray-600">
                <p>File: {lastExport.filename}</p>
                <p>Size: {lastExport.size ? `${Math.round(lastExport.size / 1024)}KB` : 'Unknown'}</p>
                <p>Created: {new Date(lastExport.exported_at).toLocaleString()}</p>
              </div>
              
              <Button 
                variant="link" 
                size="sm" 
                className="mt-2 p-0 h-auto text-blue-600"
                onClick={() => window.open(lastExport.path, '_blank')}
              >
                <ExternalLink className="h-3 w-3 mr-1" />
                Open exported file
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Share URL Results */}
        {shareUrl && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 mb-2">
                <Share2 className="h-4 w-4 text-blue-600" />
                <span className="text-sm font-medium">Shareable Link Created</span>
              </div>
              
              <div className="p-2 bg-white rounded border text-sm font-mono break-all">
                {shareUrl}
              </div>
              
              <p className="text-xs text-blue-700 mt-2">
                ✅ Link copied to clipboard! Anyone with this link can view the page.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Quick Export Shortcuts */}
        <div className="border-t pt-4">
          <label className="text-sm font-medium mb-3 block">Quick Export</label>
          <div className="grid grid-cols-2 gap-2">
            {exportFormats.map(format => (
              <Button
                key={format.value}
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelectedFormat(format.value);
                  setTimeout(handleExport, 100);
                }}
                disabled={exporting}
              >
                <format.icon className="h-3 w-3 mr-1" />
                {format.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Page Info */}
        <div className="border-t pt-4 text-xs text-gray-500">
          <p>Page: {pageTitle}</p>
          <p>ID: {pageId}</p>
        </div>
      </CardContent>
    </Card>
  );
};

export default ExportControls;