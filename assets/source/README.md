# Art sources

`art.html` holds the hero banner, the pipeline diagram, the Swagger frame and the social card (`docs/og.png`). Open it with `?c=hero`, `?c=diagram`, `?c=swagger` or `?c=og` and screenshot the matching element at 2x device scale.

The page expects these images next to it:

- `1.png`, `2.png`, `3.png`: copies of `examples/acme-dashboard/screenshots/`
- `frame_8.5_c.png`: the frame at 8.5 s of `data/output/processed_video.mp4` (`ffmpeg -ss 8.5 -i data/output/processed_video.mp4 -frames:v 1 frame_8.5_c.png`)
- `swagger_crop.png`: the top 1620 px of a 2x screenshot of `/docs` with the POST block open

Fonts: Bricolage Grotesque, Instrument Sans, JetBrains Mono (Google Fonts, OFL).
