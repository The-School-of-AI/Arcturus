import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Share2, Users, Link, Copy, Eye, Edit, Calendar, Shield } from 'lucide-react';

interface ShareRequest {
  share_type: 'link' | 'users';
  expires_at?: string;
  password?: string;
  permissions?: string;
  user_ids?: string[];
}

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: string;
}

interface PageShareProps {
  pageId: string;
  pageTitle: string;
  currentShares?: any[];
  onShareUpdate?: () => void;
}

export const PageShare: React.FC<PageShareProps> = ({ 
  pageId, 
  pageTitle, 
  currentShares = [],
  onShareUpdate 
}) => {
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [shareType, setShareType] = useState<'link' | 'users'>('link');
  const [shareConfig, setShareConfig] = useState({
    password: '',
    permissions: 'read',
    expiry_days: '',
    selected_users: [] as string[]
  });
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [generatedLink, setGeneratedLink] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchTeamMembers();
  }, []);

  const fetchTeamMembers = async () => {
    // Mock team members for now - in production this would fetch from API
    setTeamMembers([
      { id: '1', name: 'Alice Johnson', email: 'alice@company.com', role: 'Editor' },
      { id: '2', name: 'Bob Smith', email: 'bob@company.com', role: 'Viewer' },
      { id: '3', name: 'Carol Davis', email: 'carol@company.com', role: 'Admin' },
      { id: '4', name: 'David Wilson', email: 'david@company.com', role: 'Editor' }
    ]);
  };

  const createShare = async () => {
    setLoading(true);
    try {
      const expires_at = shareConfig.expiry_days 
        ? new Date(Date.now() + parseInt(shareConfig.expiry_days) * 24 * 60 * 60 * 1000).toISOString()
        : undefined;

      const request: ShareRequest = {
        share_type: shareType,
        permissions: shareConfig.permissions,
        expires_at
      };

      if (shareType === 'link') {
        if (shareConfig.password) {
          request.password = shareConfig.password;
        }
      } else {
        request.user_ids = shareConfig.selected_users;
      }

      const response = await fetch(`/api/pages/${pageId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'share', ...request })
      });

      const data = await response.json();
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`/api/pages/actions/${data.job_id}`);
        const statusData = await statusResponse.json();
        
        if (statusData.status === 'completed') {
          clearInterval(pollInterval);
          if (statusData.share_url) {
            setGeneratedLink(window.location.origin + statusData.share_url);
          }
          onShareUpdate?.();
          setLoading(false);
        }
      }, 1000);

    } catch (error) {
      console.error('Failed to create share:', error);
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // Could add a toast notification here
  };

  const getPermissionIcon = (permission: string) => {
    switch (permission) {
      case 'read': return <Eye className="h-3 w-3" />;
      case 'edit': return <Edit className="h-3 w-3" />;
      case 'admin': return <Shield className="h-3 w-3" />;
      default: return <Eye className="h-3 w-3" />;
    }
  };

  const getPermissionColor = (permission: string) => {
    switch (permission) {
      case 'read': return 'bg-gray-100 text-gray-800';
      case 'edit': return 'bg-blue-100 text-blue-800';
      case 'admin': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Share2 className="h-5 w-5" />
            Page Sharing
          </CardTitle>
          <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Share2 className="h-4 w-4 mr-2" />
                Share Page
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Share "{pageTitle}"</DialogTitle>
              </DialogHeader>
              
              <div className="space-y-4">
                {/* Share Type Selection */}
                <div className="flex gap-2">
                  <Button 
                    variant={shareType === 'link' ? 'default' : 'outline'}
                    onClick={() => setShareType('link')}
                    className="flex-1"
                  >
                    <Link className="h-4 w-4 mr-2" />
                    Public Link
                  </Button>
                  <Button 
                    variant={shareType === 'users' ? 'default' : 'outline'}
                    onClick={() => setShareType('users')}
                    className="flex-1"
                  >
                    <Users className="h-4 w-4 mr-2" />
                    Team Members
                  </Button>
                </div>

                {/* Permissions */}
                <Select 
                  value={shareConfig.permissions} 
                  onValueChange={(value) => setShareConfig({...shareConfig, permissions: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select permissions" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="read">View Only</SelectItem>
                    <SelectItem value="edit">Can Edit</SelectItem>
                    <SelectItem value="admin">Admin Access</SelectItem>
                  </SelectContent>
                </Select>

                {/* Expiry */}
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-gray-500" />
                  <Input
                    placeholder="Expire after days (optional)"
                    type="number"
                    value={shareConfig.expiry_days}
                    onChange={(e) => setShareConfig({...shareConfig, expiry_days: e.target.value})}
                  />
                </div>

                {shareType === 'link' && (
                  <Input
                    placeholder="Password (optional)"
                    type="password"
                    value={shareConfig.password}
                    onChange={(e) => setShareConfig({...shareConfig, password: e.target.value})}
                  />
                )}

                {shareType === 'users' && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Select team members:</div>
                    <div className="max-h-32 overflow-y-auto space-y-2">
                      {teamMembers.map((member) => (
                        <div key={member.id} className="flex items-center space-x-2">
                          <Checkbox
                            checked={shareConfig.selected_users.includes(member.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setShareConfig({
                                  ...shareConfig,
                                  selected_users: [...shareConfig.selected_users, member.id]
                                });
                              } else {
                                setShareConfig({
                                  ...shareConfig,
                                  selected_users: shareConfig.selected_users.filter(id => id !== member.id)
                                });
                              }
                            }}
                          />
                          <div className="flex-1">
                            <div className="text-sm font-medium">{member.name}</div>
                            <div className="text-xs text-gray-500">{member.email}</div>
                          </div>
                          <Badge variant="outline">{member.role}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {generatedLink && (
                  <div className="p-3 bg-green-50 rounded-lg">
                    <div className="text-sm font-medium text-green-800 mb-2">Share Link Created!</div>
                    <div className="flex gap-2">
                      <Input value={generatedLink} readOnly className="text-xs" />
                      <Button size="sm" onClick={() => copyToClipboard(generatedLink)}>
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button onClick={createShare} disabled={loading} className="flex-1">
                    {loading ? 'Creating...' : 'Create Share'}
                  </Button>
                  <Button variant="outline" onClick={() => setShareDialogOpen(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </CardHeader>
        
        <CardContent>
          {currentShares.length > 0 ? (
            <div className="space-y-3">
              {currentShares.map((share, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    {share.type === 'link' ? (
                      <Link className="h-4 w-4 text-blue-500" />
                    ) : (
                      <Users className="h-4 w-4 text-green-500" />
                    )}
                    <div>
                      <div className="font-medium">
                        {share.type === 'link' ? 'Public Link' : `${share.entries?.length || 0} Users`}
                      </div>
                      <div className="text-sm text-gray-500">
                        {share.expires_at ? `Expires ${new Date(share.expires_at).toLocaleDateString()}` : 'No expiry'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={getPermissionColor(share.permissions)}>
                      {getPermissionIcon(share.permissions)}
                      {share.permissions || 'read'}
                    </Badge>
                    <Button size="sm" variant="outline">
                      Manage
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Share2 className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <div>This page is not shared with anyone</div>
              <div className="text-sm">Click "Share Page" to invite collaborators</div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};