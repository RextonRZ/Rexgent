
import {
  Clapperboard,
  CloudRain,
  Coffee,
  Eye,
  Ghost,
  Heart,
  Landmark,
  Laugh,
  Rocket,
  Search,
  Swords,
  Wand2,
  type LucideIcon,
} from "lucide-react";

export interface GenreDef {
  value: string;
  label: string;
  icon: LucideIcon;
  /** dark duotone start for placeholder posters — barely-there saturation */
  tint: string;
  /** small accent for genre dots in card meta rows */
  dot: string;
}

// Full taxonomy offered when creating a drama. Filters only show genres the
// user actually has. Tints stay near-black so the grid reads as one family.
export const GENRES: GenreDef[] = [
  { value: "romance", label: "Romance", icon: Heart, tint: "hsl(345 30% 12%)", dot: "hsl(345 60% 62%)" },
  { value: "drama", label: "Drama", icon: Clapperboard, tint: "hsl(250 12% 13%)", dot: "hsl(250 25% 66%)" },
  { value: "comedy", label: "Comedy", icon: Laugh, tint: "hsl(28 30% 12%)", dot: "hsl(35 65% 58%)" },
  { value: "horror", label: "Horror", icon: Ghost, tint: "hsl(0 40% 10%)", dot: "hsl(0 60% 56%)" },
  { value: "thriller", label: "Thriller", icon: Eye, tint: "hsl(15 28% 11%)", dot: "hsl(15 60% 56%)" },
  { value: "mystery", label: "Mystery", icon: Search, tint: "hsl(215 25% 12%)", dot: "hsl(215 55% 62%)" },
  { value: "sci-fi", label: "Sci-Fi", icon: Rocket, tint: "hsl(190 35% 10%)", dot: "hsl(190 60% 55%)" },
  { value: "fantasy", label: "Fantasy", icon: Wand2, tint: "hsl(280 20% 12%)", dot: "hsl(280 45% 64%)" },
  { value: "action", label: "Action", icon: Swords, tint: "hsl(12 32% 12%)", dot: "hsl(14 65% 56%)" },
  { value: "slice of life", label: "Slice of Life", icon: Coffee, tint: "hsl(150 18% 11%)", dot: "hsl(150 40% 56%)" },
  { value: "historical", label: "Historical", icon: Landmark, tint: "hsl(45 18% 12%)", dot: "hsl(45 40% 58%)" },
  { value: "melodrama", label: "Melodrama", icon: CloudRain, tint: "hsl(220 18% 12%)", dot: "hsl(220 40% 64%)" },
];

const FALLBACK: GenreDef = {
  value: "drama",
  label: "Drama",
  icon: Clapperboard,
  tint: "hsl(250 12% 13%)",
  dot: "hsl(250 25% 66%)",
};

export function genreDef(genre?: string | null): GenreDef {
  const g = genre?.toLowerCase().trim();
  return GENRES.find((x) => x.value === g) ?? FALLBACK;
}

export function posterGradient(genre?: string | null): string {
  return `linear-gradient(135deg, ${genreDef(genre).tint} 0%, #050308 82%)`;
}
