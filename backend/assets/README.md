# Rexgent Asset Library

## 1. What this is

A file based, version controlled library of reusable creative assets: music,
sound effects, ambience, visual effects, transitions, overlays, subtitles,
fonts, LUTs, stickers, and templates. There is no database and no separate
index. The folder structure **is** the index.

Every asset lives at:

```
backend/assets/<type>/<category>/<name>.<ext>
backend/assets/<type>/<category>/<name>.json   <- sidecar metadata beside it
```

On app start (or whenever `AssetManager.scan()` runs) the library walks
`<type>/**/*.json`, validates each sidecar, and indexes the valid ones in
memory. Add an asset by dropping two files on disk. Nothing else to register.

## 2. The 11 types and their categories

Types and categories are declared in one place, `backend/app/assets/registry.py`.
To add a type or a category, edit that file. The categories below are the
folder names you should use under each type.

| Type | Categories |
| --- | --- |
| `music` | romance, sadness, happy, comedy, action, thriller, horror, luxury, daily, inspirational, fantasy, historical |
| `sfx` | door, phone, footsteps, vehicle, weather, fight, human, ui, magic, explosion |
| `ambience` | rain, forest, night, city, office, hospital, classroom, restaurant, cafe, airport, subway, courtroom, beach, wedding, mall |
| `vfx` | fire, smoke, explosion, magic, lightning, blood, spark, dust, snow, rain, fog |
| `transitions` | fade, crossfade, zoom, blur, whip, flash, glitch, camera_shake, film_cut |
| `overlays` | film_grain, dust, light_leak, vhs, cctv, security_camera, old_tv, rain_overlay, snow_overlay |
| `subtitles` | netflix, tiktok, youtube, anime, minimal, modern, comic |
| `fonts` | display, body, handwritten, mono |
| `luts` | warm, cold, romantic, horror, thriller, dream, cinematic, vintage, anime |
| `stickers` | emoji, arrow, callout, meme |
| `templates` | office_romance, ceo_drama, campus, hospital, fantasy, ancient_china, sci_fi, police, mafia |

## 3. Metadata schema

Each sidecar JSON is validated against a schema in `backend/app/assets/schema.py`.
The base schema `AssetMeta` applies to every type. Music sidecars use `MusicMeta`,
which adds the music fields.

Because the schema sets `extra="allow"`, adding a brand new key to a sidecar
never breaks older assets. Unknown keys are kept, not rejected.

### Base fields (`AssetMeta`, all types)

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | str | yes | none |
| `title` | str | yes | none |
| `filename` | str | yes | none |
| `type` | str | yes | filled from the folder name if you omit it |
| `tags` | list of str | no | `[]` |
| `duration` | number (seconds) | no | `null` |
| `license` | str | no | `null` |
| `attribution` | str | no | `null` |
| `source` | str | no | `null` |

### Extra music fields (`MusicMeta`)

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `mood` | str | yes | none |
| `scene_tags` | list of str | no | `[]` |
| `tempo` | str | no | `null` |
| `intensity` | int | no | `1` |
| `instruments` | list of str | no | `[]` |
| `loopable` | bool | no | `false` |

## 4. How to add a track

1. Pick a mood folder under `music/`, for example `music/sadness/`.
2. Drop the audio file in, for example `music/sadness/sad_piano.mp3`.
3. Write a matching sidecar beside it, `music/sadness/sad_piano.json`. The
   `filename` in the JSON must match the audio file name exactly.

Example sidecar (`music/sadness/sad_piano.json`):

```json
{
  "id": "sad_piano", "title": "Sad Piano", "filename": "sad_piano.mp3",
  "type": "music", "mood": "sadness", "scene_tags": ["breakup", "goodbye"],
  "tempo": "slow", "intensity": 2, "instruments": ["piano"], "loopable": true,
  "duration": 45, "license": "CC0", "attribution": "",
  "source": "TODO: add a royalty free track named sad_piano.mp3 beside this file"
}
```

On the next app start, or the next call to `AssetManager.scan()`, the track is
indexed automatically. If a sidecar is malformed or fails validation, the
library logs a warning and skips just that one asset. A bad sidecar is never
fatal and never blocks the rest of the library.

The three sample sidecars shipped in this repo (`sad_piano`, `bright_ukulele`,
`soft_strings`) carry metadata only. Their `source` field is a note telling the
operator to drop a royalty free audio file of the given `filename` beside the
JSON before shipping.

## 5. How assets are served

The library file stays on disk until an asset actually ships. When it does,
`AssetManager.resolve_url(asset)` uploads the file to a shared OSS key of the
form `library/<type>/<filename>` and returns a public URL. The export pipeline
and the frontend consume that URL.

The key is shared, not scoped to a project, so the same asset always maps to the
same key. Uploading again simply overwrites, and the API caches the resolved URL by
asset id so a read pays the upload at most once.

## 6. The API

Two read only GET endpoints live in `backend/app/routers/assets.py`. Both
require authentication.

| Endpoint | Query params | Returns |
| --- | --- | --- |
| `GET /api/assets/{asset_type}` | `mood`, `scene`, `max_duration`, `intensity` | `{ "results": [ { ...meta, "url": ... } ] }` |
| `GET /api/assets/music/suggest` | `project_id` | `{ "mood": ..., "results": [ { ...meta, "url": ... } ] }` |

For `music/suggest`, the mood is derived from the project's genre plus the
emotional beats of its scenes, then used to pick matching music. Each result is
serialized with its resolved library `url`.

## 7. How agents and emotion packs consume the library

The `AssetManager` is the reusable core. The API is just a thin layer over it.
A future Music, Sound, Editing, or Director agent calls the same manager methods
directly:

- `find_music(mood=, scene=, max_duration=, intensity=)` for scored music picks.
- `find(asset_type, **criteria)` for any type, filtering by equality plus
  `max_duration` and list membership on `scene` and `tag`.
- `random_match(asset_type, **criteria)` for a single random pick among matches.

Because agents and the API share this one core, a track that an agent can find
is also visible through the API, and the reverse holds too.

An "emotion pack" is nothing more than a set of sidecars that share a `mood` and
overlapping `scene_tags`. To build one, drop a group of tracks under the same
mood folder and tag their scenes consistently. Any agent querying that mood then
receives the whole pack as candidate matches, with no code change required.
