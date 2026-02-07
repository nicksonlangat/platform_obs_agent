# Release Guide for Platform Observability Agent

This guide explains how to create and publish releases of the agent for customer deployment.

## Table of Contents
- [Quick Release](#quick-release)
- [Manual Release](#manual-release)
- [Automated Release (GitHub Actions)](#automated-release-github-actions)
- [Testing a Release](#testing-a-release)
- [Version Numbering](#version-numbering)

---

## Quick Release

### Option 1: Automated (Recommended)

```bash
# Create and push a tag
git tag -a agent-v1.0.0 -m "Release agent v1.0.0"
git push origin agent-v1.0.0

# GitHub Actions will automatically:
# - Build the release package
# - Create a GitHub release
# - Upload the tarball
```

### Option 2: Manual Build

```bash
cd backend/agent
./build_release.sh 1.0.0
# Upload platform-obs-agent-1.0.0.tar.gz to GitHub releases manually
```

---

## Manual Release Process

### Step 1: Prepare the Release

```bash
# Navigate to agent directory
cd backend/agent

# Ensure all changes are committed
git status

# Update version in code if needed
# (Currently version is in agent.py, line 307)
```

### Step 2: Build the Package

```bash
# Run the build script with version number
./build_release.sh 1.0.0

# This creates:
# - platform-obs-agent-1.0.0.tar.gz
# - build/release-info.txt (contains checksums and instructions)
```

### Step 3: Test the Package

```bash
# Extract and verify
tar -xzf platform-obs-agent-1.0.0.tar.gz
cd platform-obs-agent-1.0.0

# Check file integrity
sha256sum -c SHA256SUMS

# Verify all files present
ls -la
# Expected: agent.py, config.py, log_parser.py, docker_monitor.py,
#           http_monitor.py, requirements.txt, install.sh,
#           agent_config.json.example, etc.
```

### Step 4: Test Installation (Optional but Recommended)

```bash
# On a test VM/container
cp agent_config.json.example agent_config.json
# Edit with test API token
nano agent_config.json

# Test installation
sudo ./install.sh

# Verify it works
sudo systemctl status platform-obs-agent
sudo journalctl -u platform-obs-agent -n 20
```

### Step 5: Create GitHub Release

#### Using GitHub CLI (gh)

```bash
# Create release
gh release create agent-v1.0.0 \
  platform-obs-agent-1.0.0.tar.gz \
  --title "Agent v1.0.0" \
  --notes "Release notes here"
```

#### Using GitHub Web UI

1. Go to: https://github.com/yourorg/yourrepo/releases/new
2. Tag: `agent-v1.0.0`
3. Title: `Agent v1.0.0`
4. Description: (see template below)
5. Upload: `platform-obs-agent-1.0.0.tar.gz`
6. Click "Publish release"

**Release Notes Template:**

```markdown
## Platform Observability Agent v1.0.0

### Installation

```bash
# Download and extract
wget https://github.com/yourorg/yourrepo/releases/download/agent-v1.0.0/platform-obs-agent-1.0.0.tar.gz
tar -xzf platform-obs-agent-1.0.0.tar.gz
cd platform-obs-agent-1.0.0

# Configure (only API token needed!)
cp agent_config.json.example agent_config.json
nano agent_config.json  # Add your API token

# Install
sudo ./install.sh
```

### What's New in v1.0.0
- ✅ Auto-discovery: Agent automatically registers with platform
- ✅ Simplified configuration: Only API token required
- ✅ Machine ID auto-detection
- 🐛 Bug fixes and performance improvements

### Features
- 📊 Server metrics monitoring (CPU, memory, disk, network)
- 🐳 Docker container monitoring
- 🌐 HTTP service health checks
- 📝 Log file ingestion and parsing
- 🔄 Auto-restart on failure
- 📦 Log rotation

### Requirements
- Linux (Ubuntu 20.04+, Debian 10+, CentOS 7+, RHEL 8+, Amazon Linux 2)
- Python 3.7+
- systemd

### SHA256 Checksum
```
<paste checksum from build/release-info.txt>
```
```

---

## Automated Release (GitHub Actions)

### Trigger a Release

#### Method 1: Git Tag (Automatic)

```bash
# Create and push tag
git tag -a agent-v1.0.0 -m "Release agent v1.0.0"
git push origin agent-v1.0.0

# GitHub Actions automatically creates the release
```

#### Method 2: Manual Trigger

1. Go to: https://github.com/yourorg/yourrepo/actions
2. Click "Release Agent" workflow
3. Click "Run workflow"
4. Enter version (e.g., `1.0.0`)
5. Click "Run workflow"

### What GitHub Actions Does

1. ✅ Checks out code
2. ✅ Runs `build_release.sh`
3. ✅ Creates tarball
4. ✅ Calculates checksums
5. ✅ Creates GitHub release
6. ✅ Uploads tarball
7. ✅ Generates release notes

---

## Testing a Release

### Quick Test on Docker

```bash
# Start a test container
docker run -it --rm ubuntu:22.04 bash

# Inside container:
apt-get update && apt-get install -y wget python3 python3-pip

# Download release
wget https://github.com/yourorg/yourrepo/releases/download/agent-v1.0.0/platform-obs-agent-1.0.0.tar.gz
tar -xzf platform-obs-agent-1.0.0.tar.gz
cd platform-obs-agent-1.0.0

# Create test config
cat > agent_config.json << EOF
{
  "api_endpoint": "https://your-api.com/api",
  "api_token": "pos_test_token",
  "log_files": []
}
EOF

# Test config validation
python3 agent.py --test-config

# Test installation (if running systemd)
./install.sh
```

### Verify Package Integrity

```bash
# Download and verify
wget https://github.com/yourorg/yourrepo/releases/download/agent-v1.0.0/platform-obs-agent-1.0.0.tar.gz
sha256sum platform-obs-agent-1.0.0.tar.gz
# Compare with checksum in release notes

# Verify contents
tar -tzf platform-obs-agent-1.0.0.tar.gz
# Should show all expected files
```

---

## Version Numbering

We follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`

### Examples:

- **Major (1.0.0 → 2.0.0)**: Breaking changes
  - Changed API endpoints
  - Removed configuration options
  - Changed data format

- **Minor (1.0.0 → 1.1.0)**: New features (backward compatible)
  - Added HTTP monitoring
  - Added Docker support
  - New configuration options

- **Patch (1.0.0 → 1.0.1)**: Bug fixes
  - Fixed memory leak
  - Fixed crash on startup
  - Improved error messages

### Pre-releases:

- **Beta**: `1.0.0-beta.1`
- **RC**: `1.0.0-rc.1`

---

## Release Checklist

Before releasing, ensure:

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version number incremented
- [ ] No sensitive data in code
- [ ] Dependencies up to date (check for security vulnerabilities)
- [ ] Tested on target platforms (Ubuntu, CentOS, etc.)
- [ ] Migration guide written (if breaking changes)

---

## Troubleshooting

### Build Script Fails

```bash
# Check script permissions
ls -l build_release.sh
# Should show: -rwxr-xr-x

# Make executable if needed
chmod +x build_release.sh

# Check for required files
ls -la agent.py config.py log_parser.py docker_monitor.py http_monitor.py
```

### GitHub Actions Fails

1. Check workflow logs: https://github.com/yourorg/yourrepo/actions
2. Verify secrets are set (GITHUB_TOKEN is automatic)
3. Check branch protection rules

### Tarball Missing Files

```bash
# Verify all files exist before build
ls -la *.py *.sh requirements.txt

# Check build script includes all files (line 44-51)
cat build_release.sh | grep "^cp"
```

---

## Customer Download Instructions

Share this with customers:

```bash
# Download latest release
wget https://github.com/yourorg/yourrepo/releases/latest/download/platform-obs-agent-latest.tar.gz

# Or specific version
wget https://github.com/yourorg/yourrepo/releases/download/agent-v1.0.0/platform-obs-agent-1.0.0.tar.gz

# Extract
tar -xzf platform-obs-agent-*.tar.gz
cd platform-obs-agent-*

# Configure
cp agent_config.json.example agent_config.json
nano agent_config.json

# Install
sudo ./install.sh
```

---

## Advanced: Custom Builds

### Build for Specific Customer

```bash
# Create custom config
cat > agent_config.json << EOF
{
  "api_endpoint": "https://customer-specific.com/api",
  "api_token": "customer_token_here",
  "collect_metrics": true,
  "metrics_interval": 120
}
EOF

# Build with pre-configured settings
./build_release.sh 1.0.0-customer-xyz

# This creates: platform-obs-agent-1.0.0-customer-xyz.tar.gz
# Customer just needs to run: sudo ./install.sh
```

### Build for Airgapped Environments

Include all dependencies in the package:

```bash
# Download all Python packages
pip download -r requirements.txt -d packages/

# Add to tarball (modify build_release.sh):
cp -r packages/ "$RELEASE_DIR/"

# Update install.sh to use local packages:
pip install --no-index --find-links=packages/ -r requirements.txt
```

---

## Support

For questions about the release process:
- Documentation: https://github.com/yourorg/yourrepo/tree/main/backend/agent
- Issues: https://github.com/yourorg/yourrepo/issues
