# Releasing the WatchDock Agent

## How to Release

### Option 1: Tag (recommended — triggers GitHub Actions automatically)

```bash
# 1. Bump agent_version in agent.py (line ~326)
# 2. Commit your changes
git add -p
git commit -m "Release vX.Y.Z: <summary>"

# 3. Tag and push
git tag -a agent-vX.Y.Z -m "Release agent vX.Y.Z"
git push origin main && git push origin agent-vX.Y.Z
```

GitHub Actions will build the tarball, create the GitHub release, and upload the artefacts automatically.

### Option 2: Manual trigger

Go to **Actions → Release Agent → Run workflow** and enter the version number.

### Option 3: Build locally

```bash
./build_release.sh 1.2.0
# Creates: platform-obs-agent-1.2.0.tar.gz
```

---

## Version Numbering

`MAJOR.MINOR.PATCH` — follow [semver](https://semver.org/):

| Bump | When |
|------|------|
| PATCH | Bug fixes |
| MINOR | New features (backward compatible) |
| MAJOR | Breaking changes |

---

## Pre-release Checklist

- [ ] `agent_version` in `agent.py` matches the tag
- [ ] All changes committed and pushed to `main`
- [ ] No sensitive data or credentials in the diff
