# sift-stylus-skills-installer

Installs the two Sift Codex skills:
- `sift-stylus-porting-auditor`
- `sift-stylus-research`

## Quick install (both)

```bash
npx sift-stylus-skills-installer \
  --repo getFairAI/angel-stylus-coding-assistant
```

## Install one skill only

```bash
npx sift-stylus-skills-installer \
  --repo getFairAI/angel-stylus-coding-assistant \
  --skills sift-stylus-research
```

## Options

- `--repo <owner/repo>`: required GitHub repository containing skills.
- `--ref <git-ref>`: branch/tag/commit. Default: `main`.
- `--skills <csv>`: comma-separated skill names.
- `--skills-root <path>`: root path in repo containing skill folders. Default: `skills`.
- `--target <path>`: install root. Default: `~/.codex/skills`.
- `--force`: overwrite existing installs.
