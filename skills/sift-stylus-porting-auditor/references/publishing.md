# Publishing and Installation Paths

## 1) GitHub repository path (primary)
Place the skill folder at:
- `skills/sift-stylus-porting-auditor/`

Recommended install command from Codex skill installer flows should reference the repo path directly.

## 2) npm `npx` helper (secondary)
This repository includes a helper package scaffold:
- `tools/sift-stylus-porting-auditor-installer/`

Publish flow:
1. Set final npm package name/version in `package.json`.
2. `cd tools/sift-stylus-porting-auditor-installer`
3. `npm publish --access public`
4. Consumers run:
- `npx <package-name> --repo <owner/repo> --skill-path skills/sift-stylus-porting-auditor`

## Validation before publish
- Verify `SKILL.md` frontmatter and references.
- Verify `agents/openai.yaml` fields.
- Dry-run installer using a test repo/tag before announcing the package.
