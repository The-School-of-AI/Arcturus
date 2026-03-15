import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { History, RotateCcw, Eye, User, Clock, GitCommit, FileText } from 'lucide-react';

interface PageVersion {
  version_id: string;
  timestamp: string;
  author_id: string;
  summary: string;
  changes?: any;
}

interface VersionHistoryProps {
  pageId: string;
  onVersionRestore?: (versionId: string) => void;
}

export const VersionHistory: React.FC<VersionHistoryProps> = ({ 
  pageId, 
  onVersionRestore 
}) => {
  const [versions, setVersions] = useState<PageVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<PageVersion | null>(null);
  const [revertDialogOpen, setRevertDialogOpen] = useState(false);
  const [revertReason, setRevertReason] = useState('');

  useEffect(() => {
    fetchVersions();
  }, [pageId]);

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/pages/${pageId}/history`);
      const data = await response.json();
      setVersions(data.versions || []);
    } catch (error) {
      console.error('Failed to fetch version history:', error);
    } finally {
      setLoading(false);
    }
  };

  const revertToVersion = async (versionId: string, reason: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/pages/${pageId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'revert',
          version_id: versionId,
          reason: reason
        })
      });

      const data = await response.json();
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`/api/pages/actions/${data.job_id}`);
        const statusData = await statusResponse.json();
        
        if (statusData.status === 'completed') {
          clearInterval(pollInterval);
          onVersionRestore?.(versionId);
          fetchVersions(); // Refresh version list
          setRevertDialogOpen(false);
          setRevertReason('');
          setLoading(false);
        }
      }, 1000);

    } catch (error) {
      console.error('Failed to revert version:', error);
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const getVersionIcon = (summary: string) => {
    if (summary.includes('reverted')) return <RotateCcw className="h-4 w-4 text-orange-500" />;
    if (summary.includes('metadata')) return <FileText className="h-4 w-4 text-blue-500" />;
    if (summary.includes('generated') || summary.includes('created')) return <GitCommit className="h-4 w-4 text-green-500" />;
    return <History className="h-4 w-4 text-gray-500" />;
  };

  const getVersionBadgeColor = (summary: string) => {
    if (summary.includes('reverted')) return 'bg-orange-100 text-orange-800';
    if (summary.includes('metadata')) return 'bg-blue-100 text-blue-800';
    if (summary.includes('generated') || summary.includes('created')) return 'bg-green-100 text-green-800';
    return 'bg-gray-100 text-gray-800';
  };

  const getChangesSummary = (changes: any) => {
    if (!changes) return null;
    
    const changeKeys = Object.keys(changes);
    if (changeKeys.length === 0) return null;
    
    return (
      <div className="mt-2 text-xs text-gray-600">
        <div className="font-medium">Changed:</div>
        <div className="flex flex-wrap gap-1 mt-1">
          {changeKeys.map((key) => (
            <Badge key={key} variant="outline" className="text-xs">
              {key}
            </Badge>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Version History ({versions.length})
          </CardTitle>
        </CardHeader>
        
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-gray-500">Loading version history...</div>
            </div>
          ) : versions.length > 0 ? (
            <div className="space-y-3">
              {versions.map((version, index) => (
                <div key={version.version_id} className="border rounded-lg p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      {getVersionIcon(version.summary)}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge className={getVersionBadgeColor(version.summary)}>
                            v{versions.length - index}
                          </Badge>
                          <span className="text-sm font-medium">{version.summary}</span>
                        </div>
                        
                        <div className="flex items-center gap-4 text-xs text-gray-500 mb-2">
                          <div className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {version.author_id}
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTimestamp(version.timestamp)}
                          </div>
                        </div>

                        {getChangesSummary(version.changes)}
                      </div>
                    </div>
                    
                    <div className="flex gap-2 ml-4">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelectedVersion(version)}
                      >
                        <Eye className="h-3 w-3 mr-1" />
                        View
                      </Button>
                      
                      {index > 0 && ( // Don't allow reverting to current version
                        <Dialog open={revertDialogOpen && selectedVersion?.version_id === version.version_id} onOpenChange={(open) => {
                          setRevertDialogOpen(open);
                          if (open) setSelectedVersion(version);
                        }}>
                          <DialogTrigger asChild>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setSelectedVersion(version)}
                            >
                              <RotateCcw className="h-3 w-3 mr-1" />
                              Revert
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Revert to Version {versions.length - index}</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4">
                              <div className="p-3 bg-yellow-50 rounded-lg">
                                <div className="text-sm font-medium text-yellow-800 mb-1">
                                  Are you sure you want to revert?
                                </div>
                                <div className="text-xs text-yellow-700">
                                  This will restore the page to version "{version.summary}" from {formatTimestamp(version.timestamp)}.
                                  A new version will be created to track this change.
                                </div>
                              </div>
                              
                              <Textarea
                                placeholder="Reason for reverting (optional)"
                                value={revertReason}
                                onChange={(e) => setRevertReason(e.target.value)}
                              />
                              
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => revertToVersion(version.version_id, revertReason)}
                                  disabled={loading}
                                  className="flex-1"
                                >
                                  {loading ? 'Reverting...' : 'Confirm Revert'}
                                </Button>
                                <Button 
                                  variant="outline" 
                                  onClick={() => setRevertDialogOpen(false)}
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <History className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <div>No version history available</div>
              <div className="text-sm">Versions will appear here as the page is modified</div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Version Details Dialog */}
      {selectedVersion && !revertDialogOpen && (
        <Dialog open={!!selectedVersion} onOpenChange={() => setSelectedVersion(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>
                Version Details: {selectedVersion.summary}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="font-medium text-gray-700">Author</div>
                  <div className="flex items-center gap-1">
                    <User className="h-3 w-3" />
                    {selectedVersion.author_id}
                  </div>
                </div>
                <div>
                  <div className="font-medium text-gray-700">Timestamp</div>
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatTimestamp(selectedVersion.timestamp)}
                  </div>
                </div>
              </div>
              
              {selectedVersion.changes && (
                <div>
                  <div className="font-medium text-gray-700 mb-2">Changes Made</div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <pre className="text-sm text-gray-600">
                      {JSON.stringify(selectedVersion.changes, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
              
              <div className="flex justify-end">
                <Button variant="outline" onClick={() => setSelectedVersion(null)}>
                  Close
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};