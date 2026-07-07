export interface CharacterRelationship {
  id: string;
  project_id: string;
  from_char_id: string;
  to_char_id: string;
  from_character_name: string;
  to_character_name: string;
  rel_type: RelationshipType;
  strength: number;
  description: string | null;
  first_established_scene: number | null;
  evidence_quote: string | null;
  evolution: "STATIC" | "GROWS" | "DETERIORATES" | "TRANSFORMS";
  evolution_description: string | null;
  stages: RelationshipStage[] | null;
}

export interface RelationshipStage {
  scene: number | null;
  type: RelationshipType;
  label: string;
}

export type RelationshipType =
  | "ROMANTIC"
  | "RIVAL"
  | "FAMILY"
  | "MENTOR"
  | "ALLY"
  | "ENEMY"
  | "STRANGER"
  | "COLLEAGUE";

export interface RelationshipGraph {
  characters: { id: string; name: string; role: string }[];
  relationships: CharacterRelationship[];
}
