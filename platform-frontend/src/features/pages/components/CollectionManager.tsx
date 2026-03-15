import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Folder, FolderPlus, Edit, Trash2, Move, FileText, Search, Tag } from 'lucide-react';

interface Folder {
  id: string;
  name: string;
  description?: string;
  parent_id?: string;
  page_count: number;
  created_at: string;
}

interface Tag {
  name: string;
  description?: string;
  color: string;
  category: string;
  usage_count: number;
}

interface CollectionManagerProps {
  onFolderSelect?: (folderId: string | null) => void;
  onTagSelect?: (tags: string[]) => void;
  selectedFolder?: string | null;
  selectedTags?: string[];
}

export const CollectionManager: React.FC<CollectionManagerProps> = ({
  onFolderSelect,
  onTagSelect,
  selectedFolder,
  selectedTags = []
}) => {
  const [folders, setFolders] = useState<Folder[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(false);
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [showNewTagDialog, setShowNewTagDialog] = useState(false);
  const [editingFolder, setEditingFolder] = useState<Folder | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // New folder form state
  const [newFolder, setNewFolder] = useState({
    name: '',
    description: '',
    parent_id: ''
  });

  // New tag form state  
  const [newTag, setNewTag] = useState({
    name: '',
    description: '',
    color: 'blue',
    category: 'general'
  });

  useEffect(() => {
    fetchFolders();
    fetchTags();
  }, []);

  const fetchFolders = async () => {
    try {
      const response = await fetch('/api/pages/all-folders');
      const data = await response.json();
      setFolders(data.folders || []);
    } catch (error) {
      console.error('Failed to fetch folders:', error);
    }
  };

  const fetchTags = async () => {
    try {
      const response = await fetch('/api/pages/tags');
      const data = await response.json();
      setTags(data.tags || []);
    } catch (error) {
      console.error('Failed to fetch tags:', error);
    }
  };

  const createFolder = async () => {
    if (!newFolder.name.trim()) return;

    setLoading(true);
    try {
      await fetch('/api/pages/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newFolder)
      });
      
      await fetchFolders();
      setNewFolder({ name: '', description: '', parent_id: '' });
      setShowNewFolderDialog(false);
    } catch (error) {
      console.error('Failed to create folder:', error);
    } finally {
      setLoading(false);
    }
  };

  const createTag = async () => {
    if (!newTag.name.trim()) return;

    setLoading(true);
    try {
      await fetch('/api/pages/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTag)
      });
      
      await fetchTags();
      setNewTag({ name: '', description: '', color: 'blue', category: 'general' });
      setShowNewTagDialog(false);
    } catch (error) {
      console.error('Failed to create tag:', error);
    } finally {
      setLoading(false);
    }
  };

  const deleteFolder = async (folderId: string) => {
    if (!confirm('Are you sure you want to delete this folder?')) return;

    try {
      await fetch(`/api/pages/folders/${folderId}?force=true`, {
        method: 'DELETE'
      });
      await fetchFolders();
    } catch (error) {
      console.error('Failed to delete folder:', error);
    }
  };

  const deleteTag = async (tagName: string) => {
    if (!confirm(`Are you sure you want to delete the "${tagName}" tag?`)) return;

    try {
      await fetch(`/api/pages/tags/${encodeURIComponent(tagName)}`, {
        method: 'DELETE'
      });
      await fetchTags();
    } catch (error) {
      console.error('Failed to delete tag:', error);
    }
  };

  const getTagColor = (color: string) => {
    const colors = {
      blue: 'bg-blue-100 text-blue-800',
      green: 'bg-green-100 text-green-800',
      red: 'bg-red-100 text-red-800',
      yellow: 'bg-yellow-100 text-yellow-800',
      purple: 'bg-purple-100 text-purple-800',
      pink: 'bg-pink-100 text-pink-800'
    };
    return colors[color as keyof typeof colors] || colors.blue;
  };

  const filteredFolders = folders.filter(folder =>
    folder.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredTags = tags.filter(tag =>
    tag.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search folders and tags..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Folders Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Folder className="h-5 w-5" />
            Folders ({filteredFolders.length})
          </CardTitle>
          <Dialog open={showNewFolderDialog} onOpenChange={setShowNewFolderDialog}>
            <DialogTrigger asChild>
              <Button size="sm">
                <FolderPlus className="h-4 w-4 mr-2" />
                New Folder
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Folder</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <Input
                  placeholder="Folder name"
                  value={newFolder.name}
                  onChange={(e) => setNewFolder({...newFolder, name: e.target.value})}
                />
                <Textarea
                  placeholder="Description (optional)"
                  value={newFolder.description}
                  onChange={(e) => setNewFolder({...newFolder, description: e.target.value})}
                />
                <Select value={newFolder.parent_id} onValueChange={(value) => setNewFolder({...newFolder, parent_id: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Parent folder (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">No parent (root level)</SelectItem>
                    {folders.map((folder) => (
                      <SelectItem key={folder.id} value={folder.id}>
                        {folder.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="flex gap-2">
                  <Button onClick={createFolder} disabled={loading}>
                    Create Folder
                  </Button>
                  <Button variant="outline" onClick={() => setShowNewFolderDialog(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div
              className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer hover:bg-gray-50 ${
                selectedFolder === null ? 'bg-blue-50 border-blue-200' : ''
              }`}
              onClick={() => onFolderSelect?.(null)}
            >
              <div className="flex items-center gap-2">
                <Folder className="h-4 w-4 text-gray-500" />
                <span className="font-medium">All Pages</span>
              </div>
              <Badge variant="secondary">
                {folders.reduce((acc, f) => acc + f.page_count, 0)}
              </Badge>
            </div>

            {filteredFolders.map((folder) => (
              <div
                key={folder.id}
                className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer hover:bg-gray-50 ${
                  selectedFolder === folder.id ? 'bg-blue-50 border-blue-200' : ''
                }`}
                onClick={() => onFolderSelect?.(folder.id)}
              >
                <div className="flex items-center gap-2">
                  <Folder className="h-4 w-4 text-blue-500" />
                  <div>
                    <div className="font-medium">{folder.name}</div>
                    {folder.description && (
                      <div className="text-sm text-gray-500">{folder.description}</div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{folder.page_count}</Badge>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingFolder(folder);
                      }}
                    >
                      <Edit className="h-3 w-3" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteFolder(folder.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Tags Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-5 w-5" />
            Tags ({filteredTags.length})
          </CardTitle>
          <Dialog open={showNewTagDialog} onOpenChange={setShowNewTagDialog}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Tag className="h-4 w-4 mr-2" />
                New Tag
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Tag</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <Input
                  placeholder="Tag name"
                  value={newTag.name}
                  onChange={(e) => setNewTag({...newTag, name: e.target.value})}
                />
                <Textarea
                  placeholder="Description (optional)"
                  value={newTag.description}
                  onChange={(e) => setNewTag({...newTag, description: e.target.value})}
                />
                <Select value={newTag.color} onValueChange={(value) => setNewTag({...newTag, color: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Color" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="blue">Blue</SelectItem>
                    <SelectItem value="green">Green</SelectItem>
                    <SelectItem value="red">Red</SelectItem>
                    <SelectItem value="yellow">Yellow</SelectItem>
                    <SelectItem value="purple">Purple</SelectItem>
                    <SelectItem value="pink">Pink</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder="Category (optional)"
                  value={newTag.category}
                  onChange={(e) => setNewTag({...newTag, category: e.target.value})}
                />
                <div className="flex gap-2">
                  <Button onClick={createTag} disabled={loading}>
                    Create Tag
                  </Button>
                  <Button variant="outline" onClick={() => setShowNewTagDialog(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {filteredTags.map((tag) => (
              <div key={tag.name} className="group relative">
                <Badge 
                  className={`cursor-pointer ${getTagColor(tag.color)} ${
                    selectedTags.includes(tag.name) ? 'ring-2 ring-blue-300' : ''
                  }`}
                  onClick={() => {
                    const newSelectedTags = selectedTags.includes(tag.name)
                      ? selectedTags.filter(t => t !== tag.name)
                      : [...selectedTags, tag.name];
                    onTagSelect?.(newSelectedTags);
                  }}
                >
                  {tag.name} ({tag.usage_count})
                  <Button
                    size="sm"
                    variant="ghost"
                    className="ml-2 p-0 h-4 w-4 opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteTag(tag.name);
                    }}
                  >
                    <Trash2 className="h-2 w-2" />
                  </Button>
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};