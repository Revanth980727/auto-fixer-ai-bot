
import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Copy, FileText } from 'lucide-react';
import { toast } from '@/hooks/use-toast';

interface Patch {
  id: number;
  patch_content: string;
  patched_code: string;
  test_code: string;
  commit_message: string;
  confidence_score: number;
  success: boolean;
  created_at: string;
  target_file?: string;
}

interface PatchDiffViewerProps {
  patches: Patch[];
}

export const PatchDiffViewer = ({ patches }: PatchDiffViewerProps) => {
  const [selectedPatch, setSelectedPatch] = useState<Patch | null>(patches[0] || null);

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'bg-green-500';
    if (score >= 0.6) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getConfidenceBadgeVariant = (score: number) => {
    if (score >= 0.8) return 'default';
    if (score >= 0.6) return 'secondary';
    return 'destructive';
  };

  const copyToClipboard = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied to clipboard",
      description: `${type} copied successfully.`,
    });
  };

  const formatPatchContent = (patchContent: string) => {
    if (!patchContent) return 'No patch content available';
    
    // Simple diff formatting - split lines and highlight additions/deletions
    return patchContent.split('\n').map((line, index) => {
      let className = '';
      if (line.startsWith('+')) className = 'text-green-600 bg-green-50';
      else if (line.startsWith('-')) className = 'text-red-600 bg-red-50';
      else if (line.startsWith('@@')) className = 'text-blue-600 bg-blue-50 font-semibold';
      
      return (
        <div key={index} className={`${className} px-2 py-1 font-mono text-sm`}>
          {line || ' '}
        </div>
      );
    });
  };

  if (!patches || patches.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground text-center">No patches generated for this ticket.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Patch Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Generated Patches ({patches.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {patches.map((patch) => (
              <div
                key={patch.id}
                className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                  selectedPatch?.id === patch.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                }`}
                onClick={() => setSelectedPatch(patch)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${getConfidenceColor(patch.confidence_score)}`} />
                    <span className="font-medium">{patch.target_file || `Patch #${patch.id}`}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={getConfidenceBadgeVariant(patch.confidence_score)}>
                      {(patch.confidence_score * 100).toFixed(0)}% confidence
                    </Badge>
                    {patch.success && <Badge variant="default">Success</Badge>}
                  </div>
                </div>
                {patch.commit_message && (
                  <p className="text-sm text-muted-foreground mt-1 truncate">
                    {patch.commit_message}
                  </p>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Patch Details */}
      {selectedPatch && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Patch Details</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant={getConfidenceBadgeVariant(selectedPatch.confidence_score)}>
                  {(selectedPatch.confidence_score * 100).toFixed(0)}% confidence
                </Badge>
                <Badge variant="outline">
                  {new Date(selectedPatch.created_at).toLocaleString()}
                </Badge>
              </div>
            </div>
            {selectedPatch.commit_message && (
              <p className="text-sm text-muted-foreground">{selectedPatch.commit_message}</p>
            )}
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="diff" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="diff">Diff</TabsTrigger>
                <TabsTrigger value="patched">Patched Code</TabsTrigger>
                <TabsTrigger value="tests">Tests</TabsTrigger>
              </TabsList>
              
              <TabsContent value="diff" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="font-semibold">Code Changes</h4>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(selectedPatch.patch_content, 'Patch')}
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Patch
                  </Button>
                </div>
                <div className="border rounded-lg bg-muted/20 max-h-96 overflow-auto">
                  {formatPatchContent(selectedPatch.patch_content)}
                </div>
              </TabsContent>
              
              <TabsContent value="patched" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="font-semibold">Complete File After Patch</h4>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(selectedPatch.patched_code, 'Patched code')}
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Code
                  </Button>
                </div>
                <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-96 whitespace-pre-wrap">
                  {selectedPatch.patched_code || 'No patched code available'}
                </pre>
              </TabsContent>
              
              <TabsContent value="tests" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="font-semibold">Generated Tests</h4>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(selectedPatch.test_code, 'Test code')}
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Tests
                  </Button>
                </div>
                <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-96 whitespace-pre-wrap">
                  {selectedPatch.test_code || 'No test code available'}
                </pre>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
