Files that should be relocated to `assets/` or `scripts/`:

- dragon.lottie -> assets/dragon.lottie (replace placeholder with real binary)
- temp_audio.mp3 -> assets/ (or upload to S3 and reference via URL)
- start.sh, groq_test.mjs -> scripts/

Note: Some files currently remain at repo root; move them or delete them locally to keep the repository tidy. The `.gitignore` now prevents accidental commits of these local artifacts.
