"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateShot } from "@/hooks/useStoryboard";
import type { Shot } from "@/lib/types";

export function ShotEditor({
  shot,
  onClose,
}: {
  shot: Shot;
  onClose: () => void;
}) {
  const [action, setAction] = useState(shot.action || "");
  const [dialogue, setDialogue] = useState(shot.dialogue || "");
  const [duration, setDuration] = useState(shot.estimated_duration_seconds);
  const [directorNote, setDirectorNote] = useState(shot.director_note || "");
  const updateShot = useUpdateShot();

  const handleSave = async () => {
    await updateShot.mutateAsync({
      shotId: shot.id,
      updates: {
        action,
        dialogue: dialogue || null,
        estimated_duration_seconds: duration,
        director_note: directorNote || null,
      },
    });
    onClose();
  };

  return (
    <Card>
      <CardContent className="pt-4 space-y-3">
        <div>
          <Label>Action</Label>
          <Textarea
            value={action}
            onChange={(e) => setAction(e.target.value)}
            rows={2}
          />
        </div>
        <div>
          <Label>Dialogue</Label>
          <Input
            value={dialogue}
            onChange={(e) => setDialogue(e.target.value)}
            placeholder="(none)"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Duration (s)</Label>
            <Input
              type="number"
              min={1}
              max={15}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </div>
        </div>
        <div>
          <Label>Director&apos;s Note</Label>
          <Input
            value={directorNote}
            onChange={(e) => setDirectorNote(e.target.value)}
            placeholder="Creative instruction for generation"
          />
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={updateShot.isPending}>
            {updateShot.isPending ? "Saving..." : "Save"}
          </Button>
          <Button size="sm" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
