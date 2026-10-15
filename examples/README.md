# Examples

Every example uses a fictional **Acme** product and sample data. Build any of them from the repository root with
`filmwright build examples/<folder>`; finished files land in `examples/<folder>/out/final/`.

| Folder | Film type | What it shows | Voice · presenter · music | Outputs |
|---|---|---|---|---|
| [`demo-app/`](demo-app/) | demo | A real browser recording of the bundled "Acme Tasks" web app: three scenarios with checks, zooms on each action, chapter labels | preset `ryan` · `maya` · upbeat | HD, 9:16, 1:1, GIF |
| [`explainer/`](explainer/) | explainer (story) | Three character stories for Acme Tasks: checklist, dashboard and form windows | preset `ryan` · none · upbeat | 4K, HD, 1:1 |
| [`explainer-invoicing/`](explainer-invoicing/) | explainer (story) | Three stories for "Acme Invoice", one per window kind (chat, dashboard, form) and story shape | preset `aiden` · `ana` · corporate | 4K, HD, 1:1 |
| [`montage/`](montage/) | explainer (montage) | Six Acme Tasks features in about a minute | preset `aiden` · none · inspiring | HD, 9:16, 1:1 |
| [`montage-fitness/`](montage-fitness/) | explainer (montage) | Six features of "Acme Fit", a gym app, laid out natively for Reels and feeds | preset `ryan` · none · epic | 9:16, 1:1, HD, GIF |
| [`both/`](both/) | both | Animated scenes around a short sample recording (`python examples/both/make_sample_clip.py` first) | preset `ryan` · `leo` · upbeat | HD, 9:16 |
| [`both-from-demo/`](both-from-demo/) | both | Animated scenes around the real recordings from `demo-app/` (build `demo-app` first) | preset `ryan` · `kit` · playful | 4K, HD, 9:16, web |
| [`voices/`](voices/) | explainer | The same stories with a voice described in words, or your own cloned voice (with consent) | described / cloned | HD |

No Apple Silicon? Change `voice: {type: ...}` to `voice: {type: system}` in any `reel.yaml` for a quick, fully offline
run. Everything else works the same.

## Start your own

```bash
filmwright new my-film          # asks what you're making, writes reel.yaml and starter files
filmwright build my-film
```
