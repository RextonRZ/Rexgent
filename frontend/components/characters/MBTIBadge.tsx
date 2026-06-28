import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface MBTIBadgeProps {
  type: string | null;
  confidence: number | null;
}

export function MBTIBadge({ type, confidence }: MBTIBadgeProps) {
  if (!type) return null;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <Badge variant="secondary">
            {type}
            {confidence ? ` — ${confidence}%` : ""}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs max-w-48">
            MBTI type inferred from dialogue patterns and character actions
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
