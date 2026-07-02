import { useEffect } from "react";
import { getSocket } from "@/lib/websocket";
import { useGenerationStore } from "@/stores/generationStore";

export function useWebSocket(projectId: string) {
  const { upsertClip, setCost, setComplete } = useGenerationStore();

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    socket.on("clip:started", (d) =>
      upsertClip(d.shot_id, { status: "GENERATING", model: d.model })
    );
    socket.on("clip:retry", (d) =>
      upsertClip(d.shot_id, {
        status: "CHECKING",
        retry_number: d.retry_number,
        reason: d.reason,
      })
    );
    socket.on("clip:completed", (d) =>
      upsertClip(d.shot_id, {
        status: d.status,
        clip_url: d.clip_url,
        consistency_score: d.consistency_score,
      })
    );
    socket.on("cost:updated", (d) =>
      setCost(d.current_cost ?? 0, d.budget_remaining ?? 40)
    );
    socket.on("job:completed", () => setComplete(true));

    return () => {
      socket.off("clip:started");
      socket.off("clip:retry");
      socket.off("clip:completed");
      socket.off("cost:updated");
      socket.off("job:completed");
      socket.disconnect();
    };
  }, [projectId, upsertClip, setCost, setComplete]);
}
