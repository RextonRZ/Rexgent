"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useFlagClip, useRegenClip, useApproveClip } from "@/hooks/useEditFlag";
import { SpendConfirm, type SpendRequest } from "@/components/shared/SpendConfirm";
import { RegenComparison } from "./RegenComparison";

const FLAG_TYPES = ["APPEARANCE", "ACTION", "LIGHTING", "AUDIO", "TIMING", "OTHER"];
const SEVERITIES = ["MINOR", "MAJOR", "REGENERATE_FULLY"];

export function FlagPanel({
  clipId,
  originalUrl,
  onApproved,
}: {
  clipId: string;
  originalUrl: string | null;
  onApproved: () => void;
}) {
  const [flagType, setFlagType] = useState("APPEARANCE");
  const [severity, setSeverity] = useState("MAJOR");
  const [description, setDescription] = useState("");
  const [spend, setSpend] = useState<SpendRequest | null>(null);
  const [regen, setRegen] = useState<{
    new_clip_id: string;
    new_url: string;
    original_url: string;
    changes_made: string[];
  } | null>(null);

  const flagClip = useFlagClip();
  const regenClip = useRegenClip();
  const approveClip = useApproveClip();

  const handleRegen = async () => {
    const flag = await flagClip.mutateAsync({
      clip_id: clipId,
      flag_type: flagType,
      severity,
      description,
    });
    const result = await regenClip.mutateAsync({
      clip_id: clipId,
      flag_id: flag.flag_id,
    });
    setRegen(result);
  };

  const handleApprove = async (id: string) => {
    await approveClip.mutateAsync(id);
    setRegen(null);
    onApproved();
  };

  const busy = flagClip.isPending || regenClip.isPending;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Flag & Regenerate</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>What&apos;s wrong?</Label>
              <Select value={flagType} onValueChange={(v) => v && setFlagType(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FLAG_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Severity</Label>
              <Select value={severity} onValueChange={(v) => v && setSeverity(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Describe the change</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. lighting too bright, character's face looks wrong"
              rows={2}
            />
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() =>
                setSpend({
                  title: "Regenerate this take",
                  costLine:
                    "This re-renders the clip on real credit, about $0.55 for a 5s take and up to $1.50 for a long premium one.",
                  note: "Your note rewrites the prompt first, so the new take targets exactly what you flagged.",
                  confirmLabel: "Regenerate",
                  run: handleRegen,
                })
              }
              disabled={!description || busy}
            >
              {busy ? "Regenerating with Qwen-Max + HappyHorse..." : "Regenerate Clip"}
            </Button>
            <Button variant="outline" onClick={() => handleApprove(clipId)}>
              Approve As-Is
            </Button>
          </div>
        </CardContent>
      </Card>

      {regen && (
        <RegenComparison
          originalUrl={originalUrl}
          regenUrl={regen.new_url}
          regenClipId={regen.new_clip_id}
          changesMade={regen.changes_made}
          onApprove={handleApprove}
          onKeepOriginal={() => setRegen(null)}
        />
      )}
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
    </div>
  );
}
