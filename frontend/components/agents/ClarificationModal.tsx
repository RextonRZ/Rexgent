"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useClarifications } from "@/hooks/useAgents";

export function ClarificationModal({ projectId }: { projectId: string }) {
  const { questions, submit } = useClarifications(projectId);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [freeText, setFreeText] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const open = questions.length > 0;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const answers = questions.map((q) => ({
        topic: q.topic,
        answer: (freeText[q.topic] || "").trim() || selected[q.topic] || "",
      }));
      await submit(answers);
      setSelected({});
      setFreeText({});
    } finally {
      setSubmitting(false);
    }
  };

  const allAnswered = questions.every(
    (q) => !!selected[q.topic] || !!(freeText[q.topic] || "").trim()
  );

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="glass sm:max-w-lg" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle className="text-xl">The studio needs input</DialogTitle>
          <DialogDescription>
            Answer the questions below to continue generation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 pt-2 max-h-[60vh] overflow-y-auto">
          {questions.map((q) => (
            <div key={q.topic} className="space-y-2">
              <div>
                <Label className="text-sm">{q.question}</Label>
                {q.why && (
                  <p className="text-[11px] text-muted-foreground mt-0.5">{q.why}</p>
                )}
              </div>

              {q.options && q.options.length > 0 && (
                <div className="space-y-1.5">
                  {q.options.map((opt) => (
                    <label
                      key={opt}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="radio"
                        name={`clarification-${q.topic}`}
                        value={opt}
                        checked={selected[q.topic] === opt}
                        onChange={() => {
                          setSelected((prev) => ({ ...prev, [q.topic]: opt }));
                          setFreeText((prev) => ({ ...prev, [q.topic]: "" }));
                        }}
                        className="accent-primary"
                      />
                      {opt}
                    </label>
                  ))}
                </div>
              )}

              <Input
                value={freeText[q.topic] || ""}
                onChange={(e) => {
                  const value = e.target.value;
                  setFreeText((prev) => ({ ...prev, [q.topic]: value }));
                  if (value.trim()) {
                    setSelected((prev) => ({ ...prev, [q.topic]: "" }));
                  }
                }}
                placeholder="Or type your own answer…"
                className="bg-background/50 text-sm"
              />
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button
            onClick={handleSubmit}
            disabled={submitting || !allAnswered}
            className="w-full glow"
          >
            {submitting ? "Submitting…" : "Submit answers"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
