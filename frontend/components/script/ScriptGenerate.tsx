"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGenerateScript } from "@/hooks/useScript";

interface ScriptGenerateProps {
  projectId: string;
  initialPremise?: string;
  initialGenre?: string;
  onSuccess: (data: {
    script_id: string;
    raw_text: string;
    structured_json: Record<string, unknown>;
  }) => void;
}

const GENRES = [
  "sci-fi",
  "thriller",
  "drama",
  "comedy",
  "horror",
  "romance",
  "action",
  "mystery",
  "fantasy",
];

export function ScriptGenerate({
  projectId,
  initialPremise = "",
  initialGenre = "",
  onSuccess,
}: ScriptGenerateProps) {
  const [genre, setGenre] = useState(initialGenre || "sci-fi");
  const [premise, setPremise] = useState(initialPremise);
  const [tone, setTone] = useState("dramatic");
  const [touched, setTouched] = useState(false);

  // Seed premise/genre from the project once they load (unless the user typed).
  useEffect(() => {
    if (initialPremise && !touched) setPremise(initialPremise);
  }, [initialPremise, touched]);
  useEffect(() => {
    if (initialGenre && !touched) setGenre(initialGenre);
  }, [initialGenre, touched]);

  const [episodeCount, setEpisodeCount] = useState(1);
  const [targetLength, setTargetLength] = useState(30); // seconds
  const [language, setLanguage] = useState("en");
  const [model, setModel] = useState("qwen-max");
  const generateScript = useGenerateScript();

  const handleGenerate = async () => {
    const result = await generateScript.mutateAsync({
      project_id: projectId,
      genre,
      premise,
      tone,
      episode_count: episodeCount,
      target_length: targetLength,
      language,
      model,
    });
    onSuccess(result);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Write from Scratch</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Genre</Label>
            <Select
              value={genre}
              onValueChange={(v) => {
                if (v) {
                  setTouched(true);
                  setGenre(v);
                }
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GENRES.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Tone</Label>
            <Input
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder="dramatic, dark, lighthearted..."
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Language</Label>
            <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="zh">中文</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Model</Label>
            <Select value={model} onValueChange={(v) => v && setModel(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="qwen-max">Qwen-Max (best)</SelectItem>
                <SelectItem value="qwen-plus">Qwen-Plus (balanced)</SelectItem>
                <SelectItem value="qwen-flash">Qwen-Flash (fast/cheap)</SelectItem>
                <SelectItem value="qwen3-max">Qwen3-Max (newest)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Premise (max 300 characters)</Label>
          <Textarea
            value={premise}
            onChange={(e) => {
              setTouched(true);
              setPremise(e.target.value.slice(0, 300));
            }}
            placeholder="A detective in 2047 Tokyo discovers her partner is an AI."
            rows={3}
          />
          <p className="text-xs text-muted-foreground mt-1">
            {premise.length}/300
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Episodes</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={episodeCount}
              onChange={(e) => setEpisodeCount(Number(e.target.value))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Target Length (sec/ep)</Label>
            <Input
              type="number"
              min={10}
              max={600}
              step={5}
              value={targetLength}
              onChange={(e) => setTargetLength(Number(e.target.value))}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Write as many episodes as you like — scripting is cheap. The token
          budget governs how much video you render later, not how much you
          write.
        </p>
        <Button
          onClick={handleGenerate}
          disabled={!premise || generateScript.isPending}
          className="w-full"
        >
          {generateScript.isPending
            ? "Generating with Qwen-Max..."
            : "Generate Script"}
        </Button>
        {generateScript.isError && (
          <p className="text-sm text-destructive">
            Error: {(generateScript.error as Error).message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
