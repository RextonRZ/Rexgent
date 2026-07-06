import { io, Socket } from "socket.io-client";

let socket: Socket | null = null;

/**
 * One shared socket for the whole app. Consumers add/remove their own event
 * handlers but must NEVER call socket.disconnect() — the instance is shared,
 * so one component unmounting would silently kill live updates everywhere
 * (and an explicit disconnect also turns off auto-reconnect).
 */
export function getSocket(): Socket {
  if (!socket) {
    socket = io(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000", {
      transports: ["websocket"],
      autoConnect: false,
    });
  }
  return socket;
}
