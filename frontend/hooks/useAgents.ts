import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";

export interface AgentInfo {
  key: string;
  name: string;
  role: string;
  model: string;
}

export interface AgentReport {
  agent: string;
  stage: string;
  decision: any;
  rationale: string;
  confidence: number;
  created_at?: string;
}

export interface Clarification {
  topic: string;
  why: string;
  question: string;
  options: string[];
}

export function useAgentRegistry() {
  return useQuery<AgentInfo[]>({
    queryKey: ["agent-registry"],
    queryFn: async () => (await api.get("/api/agent/registry")).data,
  });
}

export function useAgentReports(projectId: string) {
  const q = useQuery<AgentReport[]>({
    queryKey: ["agent-reports", projectId],
    queryFn: async () =>
      (await api.get(`/api/agent/reports/${projectId}`)).data,
    enabled: !!projectId,
  });

  const [live, setLive] = useState<AgentReport[]>([]);

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    const handler = (payload: AgentReport) =>
      setLive((prev) => [...prev, payload]);
    socket.on("agent:report", handler);

    return () => {
      socket.off("agent:report", handler);
      socket.disconnect();
    };
  }, [projectId]);

  return [...(q.data ?? []), ...live];
}

export function useClarifications(projectId: string) {
  const [questions, setQuestions] = useState<Clarification[]>([]);

  useEffect(() => {
    let cancelled = false;

    // Seed with any clarifications already pending server-side, so a
    // reload mid-pause still shows the modal.
    api
      .get(`/api/agent/clarifications/${projectId}`)
      .then((res) => {
        if (!cancelled && res.data?.questions) {
          setQuestions(res.data.questions);
        }
      })
      .catch(() => {
        // No pending clarifications endpoint response / none pending — ignore.
      });

    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    const onAwaiting = (payload: { questions: Clarification[] }) =>
      setQuestions(payload.questions || []);
    const onResolved = () => setQuestions([]);

    socket.on("clarification.awaiting", onAwaiting);
    socket.on("clarification.resolved", onResolved);

    return () => {
      cancelled = true;
      socket.off("clarification.awaiting", onAwaiting);
      socket.off("clarification.resolved", onResolved);
      socket.disconnect();
    };
  }, [projectId]);

  const submit = async (answers: { topic: string; answer: string }[]) => {
    const res = await api.post(
      `/api/agent/clarifications/${projectId}/answer`,
      { answers }
    );
    setQuestions([]);
    return res.data;
  };

  return { questions, submit };
}
