"use client";

import React, { useState } from "react";
import { ArtifactResponse, ArtifactContentResponse } from "@/lib/types/api";
import { getArtifactContent } from "@/lib/api/artifacts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { formatDate, formatBytes, formatShortId } from "@/lib/utils/formatting";
import { FileText, ShieldCheck, Eye, Download } from "lucide-react";

export interface ArtifactListProps {
  executionId: string;
  artifacts: ArtifactResponse[];
}

export function ArtifactList({ executionId, artifacts }: ArtifactListProps) {
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [artifactContent, setArtifactContent] = useState<ArtifactContentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInspect = async (artId: string) => {
    setSelectedArtifactId(artId);
    setIsLoading(true);
    setError(null);
    try {
      const data = await getArtifactContent(executionId, artId);
      setArtifactContent(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load artifact.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Artifact Name</TableHead>
              <TableHead>Task Node</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>SHA-256 Checksum</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Inspect</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {artifacts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-6 text-zinc-500 font-mono-data">
                  No artifacts produced by this execution yet.
                </TableCell>
              </TableRow>
            ) : (
              artifacts.map((art) => (
                <TableRow key={art.id}>
                  <TableCell>
                    <div className="flex items-center gap-2 font-medium text-zinc-200">
                      <FileText className="w-3.5 h-3.5 text-zinc-400" />
                      <span>{art.artifact_name}</span>
                    </div>
                  </TableCell>

                  <TableCell className="font-mono-data text-zinc-400">
                    {art.task_key || "root"}
                  </TableCell>

                  <TableCell>
                    <Badge variant="neutral">{art.artifact_type.toUpperCase()}</Badge>
                  </TableCell>

                  <TableCell className="font-mono-data text-zinc-400">
                    <span title={art.content_hash} className="select-all">
                      {formatShortId(art.content_hash, 16)}...
                    </span>
                  </TableCell>

                  <TableCell className="font-mono-data text-zinc-400">
                    {formatBytes(art.size_bytes)}
                  </TableCell>

                  <TableCell className="font-mono-data text-zinc-400">
                    {formatDate(art.created_at, { relative: true })}
                  </TableCell>

                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleInspect(art.id)}
                      className="h-7 text-[11px]"
                    >
                      <Eye className="w-3 h-3" />
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Artifact Viewer Modal */}
      {selectedArtifactId ? (
        <Modal
          isOpen={true}
          onClose={() => {
            setSelectedArtifactId(null);
            setArtifactContent(null);
          }}
          title={artifactContent?.artifact_name || "Artifact Inspector"}
          description={
            artifactContent
              ? `SHA-256: ${artifactContent.content_hash}`
              : "Verifying cryptographic SHA-256 checksum..."
          }
          maxWidth="xl"
        >
          {isLoading ? (
            <div className="py-8 text-center text-xs font-mono-data text-zinc-400">
              Retrieving artifact & validating integrity...
            </div>
          ) : error ? (
            <div className="p-3 rounded bg-rose-950/70 border border-rose-800 text-xs text-rose-200">
              {error}
            </div>
          ) : artifactContent ? (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between p-2 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono-data">
                <div className="flex items-center gap-1.5 text-emerald-400">
                  <ShieldCheck className="w-4 h-4" />
                  <span>SHA-256 Checksum Verified</span>
                </div>
                <Badge variant="neutral">
                  {artifactContent.artifact_type.toUpperCase()}
                </Badge>
              </div>

              <CodeBlock
                code={
                  typeof artifactContent.data === "object" && artifactContent.data !== null
                    ? artifactContent.data
                    : String(artifactContent.data)
                }
                language={
                  artifactContent.artifact_type.toLowerCase() === "json"
                    ? "json"
                    : "markdown"
                }
                maxHeight="max-h-96"
              />
            </div>
          ) : null}
        </Modal>
      ) : null}
    </div>
  );
}
