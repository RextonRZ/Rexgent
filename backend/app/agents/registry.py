AGENTS = [
  {"key": "clarification", "name": "Clarification Agent", "role": "Resolves ambiguous extraction", "model": "qwen-max"},
  {"key": "narrative_judge", "name": "Narrative Judge", "role": "Scores script quality + dialogue density", "model": "qwen-max"},
  {"key": "continuity", "name": "Continuity Agent", "role": "Scores face/outfit/background per clip", "model": "qwen3-vl-plus"},
  {"key": "style_casting", "name": "Style/Casting Agent", "role": "Generates style + character + location plates", "model": "qwen-image-max"},
  {"key": "budget_allocator", "name": "Budget Allocator", "role": "Allocates Wan vs HappyHorse under the cap", "model": "rule-based"},
]
