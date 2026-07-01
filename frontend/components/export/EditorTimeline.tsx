"use client";

import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { TimelineItem } from "./SequencePlayer";

export const PX_PER_SEC = 80; // timeline scale
const MIN_CLIP = 0.5; // shortest a clip can be trimmed to
const FRAME_W = 64; // approx filmstrip frame width

function fmt(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Repeated poster frames across the clip → a filmstrip. */
function Filmstrip({ item, width }: { item: TimelineItem; width: number }) {
  const span = Math.max(0.1, item.trimEnd - item.trimStart);
  const count = Math.min(8, Math.max(1, Math.round(width / FRAME_W)));
  return (
    <div className="absolute inset-0 flex pointer-events-none">
      {Array.from({ length: count }, (_, i) => {
        const t = item.trimStart + (span * (i + 0.5)) / count;
        return (
          <video
            key={i}
            src={`${item.url}#t=${t.toFixed(2)}`}
            muted
            playsInline
            preload="metadata"
            className="h-full flex-1 min-w-0 object-cover border-r border-black/30 last:border-r-0"
          />
        );
      })}
    </div>
  );
}

function TimelineClip({
  item,
  order,
  selected,
  onSelect,
  onRemove,
  onTrim,
}: {
  item: TimelineItem;
  order: number;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onTrim: (clipId: string, start: number, end: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.clipId });
  const width = (item.trimEnd - item.trimStart) * PX_PER_SEC;

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    width: `${width}px`,
  };

  const dragHandle = (edge: "left" | "right") => (e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const startX = e.clientX;
    const startStart = item.trimStart;
    const startEnd = item.trimEnd;
    const onMove = (ev: PointerEvent) => {
      const delta = (ev.clientX - startX) / PX_PER_SEC;
      if (edge === "left") {
        const ns = Math.min(Math.max(0, startStart + delta), startEnd - MIN_CLIP);
        onTrim(item.clipId, ns, startEnd);
      } else {
        const ne = Math.max(
          Math.min(item.duration, startEnd + delta),
          startStart + MIN_CLIP
        );
        onTrim(item.clipId, startStart, ne);
      }
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onSelect}
      className={`group relative shrink-0 h-20 cursor-grab active:cursor-grabbing rounded-md overflow-hidden bg-black select-none ${
        selected ? "ring-2 ring-primary" : "ring-1 ring-border"
      }`}
    >
      <Filmstrip item={item} width={width} />

      {/* label bar */}
      <div className="absolute top-0 inset-x-0 h-4 bg-black/55 flex items-center px-1.5">
        <span className="truncate text-[9px] text-white/90">
          {order}. {item.label}
        </span>
      </div>

      {/* trim handles */}
      <div
        onPointerDown={dragHandle("left")}
        className="absolute left-0 top-0 bottom-0 w-2.5 bg-white/80 cursor-ew-resize flex items-center justify-center opacity-70 hover:opacity-100"
        title="Trim start"
      >
        <span className="h-6 w-0.5 bg-black/60" />
      </div>
      <div
        onPointerDown={dragHandle("right")}
        className="absolute right-0 top-0 bottom-0 w-2.5 bg-white/80 cursor-ew-resize flex items-center justify-center opacity-70 hover:opacity-100"
        title="Trim end"
      >
        <span className="h-6 w-0.5 bg-black/60" />
      </div>

      {/* duration + remove */}
      <div className="absolute bottom-0 inset-x-0 h-4 bg-black/55 flex items-center justify-between px-1.5">
        <span className="text-[9px] text-white/80">
          {(item.trimEnd - item.trimStart).toFixed(1)}s
        </span>
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="text-[10px] text-white/70 hover:text-bad"
          title="Remove"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

function Ruler({ totalSeconds }: { totalSeconds: number }) {
  const ticks = Math.ceil(totalSeconds) + 1;
  return (
    <div
      className="relative h-5 border-b hairline"
      style={{ width: `${totalSeconds * PX_PER_SEC}px`, minWidth: "100%" }}
    >
      {Array.from({ length: ticks }, (_, i) => (
        <div
          key={i}
          className="absolute top-0 bottom-0 flex items-start"
          style={{ left: `${i * PX_PER_SEC}px` }}
        >
          <span className="h-2 w-px bg-border" />
          <span className="ml-1 text-[9px] text-muted-foreground">{fmt(i)}</span>
        </div>
      ))}
    </div>
  );
}

export function EditorTimeline({
  items,
  selectedIndex,
  onSelect,
  onReorder,
  onRemove,
  onTrim,
  playheadSeconds,
}: {
  items: TimelineItem[];
  selectedIndex: number;
  onSelect: (i: number) => void;
  onReorder: (items: TimelineItem[]) => void;
  onRemove: (clipId: string) => void;
  onTrim: (clipId: string, start: number, end: number) => void;
  playheadSeconds: number;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (over && active.id !== over.id) {
      const from = items.findIndex((i) => i.clipId === active.id);
      const to = items.findIndex((i) => i.clipId === over.id);
      if (from !== -1 && to !== -1) onReorder(arrayMove(items, from, to));
    }
  };

  const totalSeconds = items.reduce(
    (sum, i) => sum + (i.trimEnd - i.trimStart),
    0
  );

  return (
    <div className="rounded-xl border hairline bg-card p-3">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-sm font-medium">Timeline</h2>
          <p className="text-[11px] text-muted-foreground">
            Drag clips to reorder · drag the white edges to trim · ✕ to remove
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          {items.length} clips · {totalSeconds.toFixed(1)}s
        </span>
      </div>

      {items.length === 0 ? (
        <div className="h-24 rounded-lg border border-dashed border-border flex items-center justify-center text-sm text-muted-foreground">
          Empty cut — add shots from the right.
        </div>
      ) : (
        <div className="overflow-x-auto pb-2">
          <div className="relative inline-block min-w-full">
            <Ruler totalSeconds={totalSeconds} />
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={items.map((i) => i.clipId)}
                strategy={horizontalListSortingStrategy}
              >
                <div className="flex gap-0.5 pt-2">
                  {items.map((item, i) => (
                    <TimelineClip
                      key={item.clipId}
                      item={item}
                      order={i + 1}
                      selected={i === selectedIndex}
                      onSelect={() => onSelect(i)}
                      onRemove={() => onRemove(item.clipId)}
                      onTrim={onTrim}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

            {/* playhead */}
            <div
              className="pointer-events-none absolute top-0 bottom-0 w-px bg-primary"
              style={{ left: `${playheadSeconds * PX_PER_SEC}px` }}
            >
              <span className="absolute -top-1 -left-1 h-2 w-2 rounded-full bg-primary" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
