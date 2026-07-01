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

function SortableClip({
  item,
  order,
  selected,
  onSelect,
  onRemove,
}: {
  item: TimelineItem;
  order: number;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.clipId });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onSelect}
      className={`group relative shrink-0 w-40 cursor-grab active:cursor-grabbing rounded-lg border overflow-hidden bg-black ${
        selected ? "border-primary ring-1 ring-primary" : "hairline"
      }`}
    >
      <video
        src={item.url}
        muted
        playsInline
        preload="none"
        className="aspect-video w-full object-cover pointer-events-none"
      />
      <div className="absolute top-1 left-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white/90">
        {order}. {item.label}
      </div>
      <button
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="absolute top-1 right-1 h-5 w-5 rounded-full bg-black/60 text-white/90 text-xs opacity-0 group-hover:opacity-100 hover:bg-bad transition-opacity"
        title="Remove from cut"
      >
        ×
      </button>
    </div>
  );
}

export function EditorTimeline({
  items,
  selectedIndex,
  onSelect,
  onReorder,
  onRemove,
}: {
  items: TimelineItem[];
  selectedIndex: number;
  onSelect: (i: number) => void;
  onReorder: (items: TimelineItem[]) => void;
  onRemove: (clipId: string) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (over && active.id !== over.id) {
      const from = items.findIndex((i) => i.clipId === active.id);
      const to = items.findIndex((i) => i.clipId === over.id);
      if (from !== -1 && to !== -1) onReorder(arrayMove(items, from, to));
    }
  };

  const totalSeconds = items.length * 5; // clips are ~5s each

  return (
    <div className="rounded-xl border hairline bg-card p-3">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-sm font-medium">Timeline</h2>
          <p className="text-[11px] text-muted-foreground">
            Drag clips to reorder · hover to remove · click to preview
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          {items.length} clips · ~{totalSeconds}s
        </span>
      </div>

      {items.length === 0 ? (
        <div className="h-24 rounded-lg border border-dashed border-border flex items-center justify-center text-sm text-muted-foreground">
          Empty cut — add shots from the right.
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={items.map((i) => i.clipId)}
            strategy={horizontalListSortingStrategy}
          >
            <div className="flex gap-2 overflow-x-auto pb-2">
              {items.map((item, i) => (
                <SortableClip
                  key={item.clipId}
                  item={item}
                  order={i + 1}
                  selected={i === selectedIndex}
                  onSelect={() => onSelect(i)}
                  onRemove={() => onRemove(item.clipId)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}
