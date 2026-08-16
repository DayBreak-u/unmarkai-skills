# Rect coordinates and video dimensions

`sel_area` mode processes only the rectangle you give it. Getting the numbers
right the first time saves a billed run.

## Read the dimensions and duration

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height \
  -show_entries format=duration \
  -of json video.mp4 | jq '{width: .streams[0].width, height: .streams[0].height, duration: .format.duration}'
```

Example output:

```json
{ "width": 1920, "height": 1080, "duration": "12.34" }
```

- Coordinates are **absolute pixels of the original video** — not percentages,
  not normalized 0–1 values, and never relative to a preview or a re-encoded
  copy.
- `duration` is a string of seconds; billing rounds it **up** to whole seconds
  with a 1-second minimum (12.34s → 13 billable seconds).

## Define the rect

`rect` = `{ "x1": left, "y1": top, "x2": right, "y2": bottom }` in pixels:

```text
(0,0) ───────────────── x →
  │
  │      (x1,y1)─────────┐
  │        │   text box  │
  │        └─────────(x2,y2)
  y↓
```

Rules enforced by the API:

- `0 ≤ x1 < x2 ≤ width` and `0 ≤ y1 < y2 ≤ height`
- The region must be inside the frame and non-empty.

## Margin and typical cases

Cover the text **plus an 8–16px margin** on every side. Two anchors cover most
real videos:

- **Bottom subtitles (16:9, 1920×1080)** — the text band usually sits in the
  lower ~15% of the frame. Start with
  `{"x1": 0, "y1": 880, "x2": 1920, "y2": 1040}` and adjust after looking at a
  frame.
- **Corner caption / logo-area text** — crop tightly around the text block
  with the same margin, e.g. `{"x1": 1480, "y1": 40, "x2": 1880, "y2": 140}`
  for a top-right caption on 1080p.

If unsure of the exact text bounds:

1. Extract a frame where the text is fully visible:
   `ffmpeg -i video.mp4 -vf select=eq(n\,30) -vframes 1 frame.png`
2. Read the pixel bounds in any image viewer (hover shows coordinates), or
   crop candidates with ffmpeg until the text is fully covered.
3. Add the margin, clamp to the frame, and prefer a slightly larger box —
   a larger region costs the same per second in `sel_area`.

## Sanity checklist before creating the job

- [ ] Width/height come from ffprobe of THIS file (not a different export)
- [ ] `x2 > x1`, `y2 > y1`, both inside the frame
- [ ] Margin added on all four sides
- [ ] `rect` is passed only with `mode: "sel_area"` — omit it for `all_area`
