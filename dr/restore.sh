#!/usr/bin/env bash
# =============================================================================
# homelab-restore.sh — Homelab DR Restore Script
#
# Restores the full homelab container stack from a Duplicati backup.
#
# Two restore paths:
#
#   --source NAS02  (default) — restore from NAS02 NAS backups share
#                              RTO: ~30 min. Requires NAS02 reachable on LAN.
#
#   --source b2              — restore from Backblaze B2 (offsite)
#                              RTO: ~60-90 min (downloads ~46 GB over internet).
#                              Use when NAS02 is unavailable (catastrophic failure,
#                              off-site restore). Requires B2_KEY_ID and
#                              B2_APPLICATION_KEY in .homelab.secrets.
#                              Media library is NOT restored this way — Radarr/
#                              Sonarr will re-download content after restore.
#
# Usage:
#   ./restore.sh
#   ./restore.sh --source b2
#   ./restore.sh --secrets /path/to/.homelab.secrets
#   ./restore.sh --source b2 --secrets /path/to/.homelab.secrets
#
# Prerequisites:
#   - Linux x86_64 host with sudo access
#   - .homelab.secrets file filled in from .secrets.template
#   - Internet access (to pull Docker images if not cached)
#   - GitHub SSH key available (see Step 4 — clone repo)
#   - For --source NAS02: Network access to NAS02 (TrueNAS) NAS
#   - For --source b2:   B2_KEY_ID + B2_APPLICATION_KEY in secrets file
# =============================================================================

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# --- Defaults ---
REAL_HOME="$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)"
SECRETS_FILE="${REAL_HOME}/.homelab.secrets"
MOUNT_BASE="/mnt/homelab"
APPDATA_PATH="/opt/homelab/appdata"
COMPOSE_DIR="$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)/homelab"
REPO_URL="git@github.com:yourusername/homelab.git"
SOURCE_MODE="NAS02"    # NAS02 (local NAS) or b2 (Backblaze offsite)

# --- Timing ---
SCRIPT_START=$(date +%s)

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case $1 in
    --secrets) SECRETS_FILE="$2"; shift 2 ;;
    --source)
      case "$2" in
        NAS02|b2) SOURCE_MODE="$2"; shift 2 ;;
        *) echo "Unknown source: $2 (valid: NAS02, b2)"; exit 1 ;;
      esac ;;
    --help|-h)
      echo "Usage: $0 [--source NAS02|b2] [--secrets /path/to/.homelab.secrets]"
      echo ""
      echo "  --source NAS02  Restore from NAS02 NAS backups share (default, ~30 min RTO)"
      echo "  --source b2    Restore from Backblaze B2 offsite bucket (~60-90 min RTO)"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# --- Helpers ---
info()    { echo -e "${BLUE}[INFO]${NC}    $*"; }
success() { echo -e "${GREEN}[✓]${NC}      $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}    $*"; }
error()   { echo -e "${RED}[ERROR]${NC}   $*" >&2; }
step()    { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}"; }
die()     { error "$*"; exit 1; }

elapsed() {
  local secs=$(( $(date +%s) - SCRIPT_START ))
  printf "%dm%02ds" $(( secs / 60 )) $(( secs % 60 ))
}

# =============================================================================
echo -e "\n${BOLD}╔══════════════════════════════════════════════╗"
echo "║     HOMELAB DR RESTORE — $(date '+%Y-%m-%d %H:%M')     ║"
echo -e "╚══════════════════════════════════════════════╝${NC}"
if [[ "$SOURCE_MODE" == "b2" ]]; then
  echo -e "\n${YELLOW}${BOLD}▶ Restore source: Backblaze B2 (offsite) — RTO ~60-90 min${NC}"
  echo -e "  Media library will NOT be restored. Radarr/Sonarr will re-download content.\n"
else
  echo -e "\n${GREEN}${BOLD}▶ Restore source: NAS02 NAS (local) — RTO ~30 min${NC}\n"
fi
# =============================================================================

# =============================================================================
step "1/10 Load secrets"
# =============================================================================

[[ -f "$SECRETS_FILE" ]] || die "Secrets file not found: ${SECRETS_FILE}\n  Copy dr/.secrets.template, fill in values, save to ${SECRETS_FILE}"

PERMS=$(stat -c %a "$SECRETS_FILE" 2>/dev/null || stat -f %Lp "$SECRETS_FILE" 2>/dev/null)
[[ "$PERMS" == "600" ]] || warn "Secrets file is not chmod 600 — run: chmod 600 ${SECRETS_FILE}"

# Strip UTF-8 BOM and Windows CRLF line endings if present
# (common when the file is created or edited on Windows / in some GUI editors)
sed -i 's/^\xef\xbb\xbf//; s/\r//' "$SECRETS_FILE" 2>/dev/null || true

# shellcheck disable=SC1090
source "$SECRETS_FILE"

if [[ "$SOURCE_MODE" == "b2" ]]; then
  REQUIRED_VARS=(PIA_USER PIA_PASS DUPLICATI_PASSPHRASE B2_KEY_ID B2_APPLICATION_KEY SSH_KEY_PATH)
else
  REQUIRED_VARS=(T440_IP T440_MEDIA_SHARE T440_DOWNLOADS_SHARE T440_BACKUPS_SHARE PIA_USER PIA_PASS DUPLICATI_PASSPHRASE SSH_KEY_PATH)
fi
for var in "${REQUIRED_VARS[@]}"; do
  [[ -n "${!var:-}" ]] || die "Required secret not set in ${SECRETS_FILE}: ${var}"
done

# TRUENAS_SSH_USER is optional — defaults to homelab-svc
TRUENAS_SSH_USER="${TRUENAS_SSH_USER:-homelab-svc}"

success "Secrets loaded from ${SECRETS_FILE}"

# =============================================================================
step "2/10 Check & install dependencies"
# =============================================================================

# Detect package manager (supported: apt/dnf/yum — Debian/Ubuntu and RHEL/Fedora)
install_pkg() {
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y "$@"
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y "$@"
  elif command -v yum &>/dev/null; then
    sudo yum install -y "$@"
  else
    die "No supported package manager found (apt/dnf/yum).\nThis script targets Debian/Ubuntu and RHEL/Fedora. Install dependencies manually: $*"
  fi
}

# --- Base packages: install anything missing before we try to use it ---
MISSING_PKGS=()
command -v curl      &>/dev/null || MISSING_PKGS+=(curl)
command -v git       &>/dev/null || MISSING_PKGS+=(git)
command -v ssh       &>/dev/null || MISSING_PKGS+=(openssh-client)
command -v mount.nfs &>/dev/null || {
  # nfs-common on Debian/Ubuntu, nfs-utils on RHEL/Fedora
  if command -v apt-get &>/dev/null; then MISSING_PKGS+=(nfs-common)
  else MISSING_PKGS+=(nfs-utils); fi
}

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
  info "Installing missing base packages: ${MISSING_PKGS[*]}"
  if command -v apt-get &>/dev/null; then sudo apt-get update -qq; fi
  install_pkg "${MISSING_PKGS[@]}"
  success "Base packages installed"
fi

# --- Docker ---
install_docker() {
  warn "Docker not found — installing via get.docker.com..."
  curl -fsSL https://get.docker.com | sh
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  warn "Docker installed and ${USER} added to the docker group."
}

command -v docker &>/dev/null || install_docker

# After a fresh install the current shell session won't have the new docker
# group membership active, so plain 'docker' hits a permission denied error
# on /var/run/docker.sock. Detect this and use 'sudo docker' for this run.
DOCKER_CMD="docker"
if ! docker info &>/dev/null 2>&1; then
  if sudo docker info &>/dev/null 2>&1; then
    warn "Docker socket not accessible without sudo (group membership not active in this session)."
    warn "Using 'sudo docker' for this run. To fix permanently: log out and back in."
    DOCKER_CMD="sudo docker"
  else
    # Docker daemon might not be running
    sudo systemctl start docker 2>/dev/null || true
    sleep 2
    if sudo docker info &>/dev/null 2>&1; then
      DOCKER_CMD="sudo docker"
    else
      die "Cannot connect to Docker daemon.\n  Try: sudo systemctl start docker"
    fi
  fi
fi

# --- Docker Compose plugin ---
$DOCKER_CMD compose version &>/dev/null \
  || die "docker compose plugin not found.\n  Install: https://docs.docker.com/compose/install/linux/"

success "All dependencies present"
info "Docker: $($DOCKER_CMD --version)"
info "Compose: $($DOCKER_CMD compose version --short)"

# =============================================================================
step "3/9  Storage pre-flight check"
# =============================================================================

if [[ "$SOURCE_MODE" == "b2" ]]; then
  info "Source mode: B2 — skipping NAS02 pre-flight. Appdata will be restored from Backblaze B2."
  info "Checking internet connectivity..."
  curl -fsS --max-time 10 https://api.backblazeb2.com/b2api/v2/b2_authorize_account \
    -u "${B2_KEY_ID}:${B2_APPLICATION_KEY}" > /dev/null \
    && success "Backblaze B2 credentials verified" \
    || die "Cannot reach Backblaze B2 API — check internet connection and B2_KEY_ID / B2_APPLICATION_KEY in secrets file."
else

info "Checking NAS02 reachability (${T440_IP})..."
if ! ping -c 2 -W 3 "${T440_IP}" &>/dev/null; then
  die "Cannot reach NAS02 at ${T440_IP}. Check network and that TrueNAS is running."
fi
success "NAS02 is reachable"

# SSH health check via homelab-svc + midclt
# If the SSH key isn't set up on this DR host, warn and skip — don't block DR
TRUENAS_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes"
TRUENAS_SSH="${TRUENAS_SSH_USER}@${T440_IP}"

if ssh ${TRUENAS_SSH_OPTS} "${TRUENAS_SSH}" 'echo ok' &>/dev/null; then
  info "SSH to TrueNAS established — querying storage health..."

  # Pool status
  POOL_STATUS=$(ssh ${TRUENAS_SSH_OPTS} "${TRUENAS_SSH}" \
    "midclt call pool.query | python3 -c \"
import json,sys
pools = json.load(sys.stdin)
for p in pools:
    print(p['name'] + ':' + p['status'])
\"" 2>/dev/null || echo "query_failed")

  if [[ "$POOL_STATUS" == "query_failed" ]]; then
    warn "Could not query pool status via midclt — proceeding without pool check"
  else
    while IFS=: read -r pool_name pool_state; do
      case "$pool_state" in
        ONLINE)
          success "ZFS pool '${pool_name}': ONLINE" ;;
        DEGRADED)
          warn "ZFS pool '${pool_name}' is DEGRADED — a disk may have failed."
          warn "NFS will still work, but replace the failed disk ASAP."
          warn "Check: ssh ${TRUENAS_SSH} 'zpool status ${pool_name}'" ;;
        FAULTED|UNAVAIL|REMOVED)
          die "ZFS pool '${pool_name}' is ${pool_state} — NFS will not be available. Aborting." ;;
        *)
          warn "ZFS pool '${pool_name}' status: ${pool_state} (unexpected — proceeding with caution)" ;;
      esac
    done <<< "$POOL_STATUS"
  fi

  # NFS share availability
  NFS_STATUS=$(ssh ${TRUENAS_SSH_OPTS} "${TRUENAS_SSH}" \
    "midclt call sharing.nfs.query | python3 -c \"
import json,sys
shares = json.load(sys.stdin)
for s in shares:
    print(s['path'] + ':' + str(s['enabled']))
\"" 2>/dev/null || echo "query_failed")

  if [[ "$NFS_STATUS" != "query_failed" ]]; then
    REQUIRED_SHARES=("${T440_MEDIA_SHARE}" "${T440_DOWNLOADS_SHARE}" "${T440_BACKUPS_SHARE}")
    while IFS=: read -r share_path share_enabled; do
      for req in "${REQUIRED_SHARES[@]}"; do
        if [[ "$share_path" == "$req" ]]; then
          if [[ "$share_enabled" == "True" ]]; then
            success "NFS share enabled: ${share_path}"
          else
            warn "NFS share is DISABLED in TrueNAS: ${share_path}"
            warn "Enable it in TrueNAS → Shares → NFS before mounting."
          fi
        fi
      done
    done <<< "$NFS_STATUS"
  fi
else
  warn "Could not SSH to ${TRUENAS_SSH} — skipping storage pre-flight check."
  warn "To enable: ensure your SSH key is loaded and homelab-svc has SSH access on TrueNAS."
  warn "Proceeding — NFS mount will fail if the pool or shares are not healthy."
fi

fi  # end SOURCE_MODE == NAS02 pre-flight block

# =============================================================================
step "4/9  Mount storage"
# =============================================================================

sudo mkdir -p "${MOUNT_BASE}/media_ds" "${MOUNT_BASE}/downloads_ds" "${MOUNT_BASE}/backups"

mount_nfs() {
  local share="$1" mountpoint="$2" label="$3" required="${4:-true}"
  if mountpoint -q "$mountpoint"; then
    success "Already mounted: ${label} → ${mountpoint}"
    return 0
  fi
  info "Mounting ${T440_IP}:${share} → ${mountpoint}"
  # Try NFSv4 first, fall back to v3
  if sudo mount -t nfs "${T440_IP}:${share}" "$mountpoint" -o "rw,nfsvers=4,soft,timeo=60" 2>/dev/null \
    || sudo mount -t nfs "${T440_IP}:${share}" "$mountpoint" -o "rw,nfsvers=3,soft,timeo=60" 2>/dev/null; then
    success "Mounted: ${label}"
  else
    if [[ "$required" == "true" ]]; then
      die "Failed to mount ${label}.\n  Check NAS02 is reachable and NFS exports are configured."
    else
      warn "Could not mount ${label} — skipping (not required for B2 restore)."
      warn "Media and downloads will be unavailable until NAS02 is restored."
    fi
  fi
}

if [[ "$SOURCE_MODE" == "NAS02" ]]; then
  # Full NAS02 mount — all three shares required
  mount_nfs "${T440_MEDIA_SHARE}"     "${MOUNT_BASE}/media_ds"     "media_ds"
  mount_nfs "${T440_DOWNLOADS_SHARE}" "${MOUNT_BASE}/downloads_ds" "downloads_ds"
  mount_nfs "${T440_BACKUPS_SHARE}"   "${MOUNT_BASE}/backups"      "backups"

  # Verify backup directory exists
  [[ -d "${MOUNT_BASE}/backups/homelab-appdata" ]] \
    || die "Backup not found at ${MOUNT_BASE}/backups/homelab-appdata\n  Check that Duplicati has run at least once and the backups share is correct."
  success "NFS mounts verified — backup directory found"

  # Show latest backup timestamp
  LATEST=$(ls -t "${MOUNT_BASE}/backups/homelab-appdata/"*.dblock.zip.aes 2>/dev/null | head -1 | xargs stat -c %y 2>/dev/null | cut -d. -f1 || echo "unknown")
  info "Latest backup file timestamp: ${LATEST}"
else
  # B2 mode — NAS02 media mounts are optional (best-effort)
  info "B2 mode: attempting optional NAS02 media mounts (for Plex availability after restore)..."
  if [[ -n "${T440_IP:-}" ]] && ping -c 1 -W 3 "${T440_IP}" &>/dev/null; then
    mount_nfs "${T440_MEDIA_SHARE:-/mnt/media/media_ds}"         "${MOUNT_BASE}/media_ds"     "media_ds"     false
    mount_nfs "${T440_DOWNLOADS_SHARE:-/mnt/media/downloads_ds}" "${MOUNT_BASE}/downloads_ds" "downloads_ds" false
  else
    warn "NAS02 not reachable — media mounts skipped. Plex will have no library until NAS02 is restored."
    warn "After NAS02 recovery, mount shares manually and restart plex + arr containers."
  fi
  info "Appdata will be restored from Backblaze B2 — no backups NFS mount needed."
fi

# =============================================================================
step "5/9  Clone homelab repo"
# =============================================================================
# Requires a GitHub SSH key on this host. Options:
#   A) Copy your key from a USB/password manager:
#        cp /path/to/id_ed25519 ~/.ssh/id_ed25519 && chmod 600 ~/.ssh/id_ed25519
#        ssh-add ~/.ssh/id_ed25519
#   B) If you stored SSH_KEY_PATH in your secrets file, the block below loads it.

# Start a fresh ssh-agent for this script session and load the key.
# This is necessary because ssh-add in another terminal window only adds
# the key to that window's agent — this script has its own environment.
eval "$(ssh-agent -s)" > /dev/null
SSH_AGENT_STARTED=true

KEY_LOADED=false
if [[ -n "${SSH_KEY_PATH:-}" && -f "${SSH_KEY_PATH}" ]]; then
  info "Loading SSH key from ${SSH_KEY_PATH}"
  ssh-add "${SSH_KEY_PATH}" && KEY_LOADED=true
elif [[ -f "${HOME}/.ssh/id_ed25519" ]]; then
  info "Loading SSH key from ~/.ssh/id_ed25519"
  ssh-add "${HOME}/.ssh/id_ed25519" && KEY_LOADED=true
elif [[ -f "${HOME}/.ssh/id_rsa" ]]; then
  info "Loading SSH key from ~/.ssh/id_rsa"
  ssh-add "${HOME}/.ssh/id_rsa" && KEY_LOADED=true
fi

if [[ "$KEY_LOADED" == "false" ]]; then
  warn "No SSH key found or loaded. Set SSH_KEY_PATH in your secrets file,"
  warn "or place your key at ~/.ssh/id_ed25519"
  warn "Attempting clone anyway — will fail if key not available..."
fi

if [[ -d "${COMPOSE_DIR}/.git" ]]; then
  info "Repo already present — pulling latest..."
  git -C "$COMPOSE_DIR" pull --ff-only || warn "Pull failed — continuing with local version"
else
  info "Cloning from ${REPO_URL}..."
  GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new" \
    git clone "$REPO_URL" "$COMPOSE_DIR" \
    || die "Git clone failed. Check that your SSH key has access to the repo.\n  Test with: ssh -T git@github.com"
fi

success "Repo ready at ${COMPOSE_DIR}"
info "Compose file: ${COMPOSE_DIR}/compose/docker-compose.yml"

# =============================================================================
step "6/9  Restore appdata from Duplicati backup"
# =============================================================================

if [[ "$SOURCE_MODE" == "b2" ]]; then
  BACKUP_STORAGE_URL="b2://yourusername-appdata-backup"
  info "Restoring from Backblaze B2 (${BACKUP_STORAGE_URL})..."
  info "This will download ~46 GB — expect 60-90 minutes depending on connection speed."
else
  BACKUP_STORAGE_URL="file:///backups/homelab-appdata"
  info "Restoring from NAS02 NAS (${BACKUP_STORAGE_URL})..."
  info "This typically takes 2-10 minutes on a local network."
fi

sudo mkdir -p "$APPDATA_PATH"
sudo chown "${USER}:${USER}" "$APPDATA_PATH"

# The linuxserver.io Duplicati image runs via s6-overlay, which sets up its own
# environment (including dotnet). The only reliable way to invoke the CLI is
# inside a *running* container via 'with-contenv', which loads that environment.
# Strategy: start as a daemon, exec the CLI inside it, then stop and remove.

info "Starting Duplicati container (daemon)..."
if [[ "$SOURCE_MODE" == "b2" ]]; then
  $DOCKER_CMD run -d \
    --name duplicati-restore \
    -v "${APPDATA_PATH}:/restore" \
    -e "PUID=$(id -u)" \
    -e "PGID=$(id -g)" \
    -e "SETTINGS_ENCRYPTION_KEY=${DUPLICATI_PASSPHRASE}" \
    lscr.io/linuxserver/duplicati:latest
else
  $DOCKER_CMD run -d \
    --name duplicati-restore \
    -v "${MOUNT_BASE}/backups:/backups:ro" \
    -v "${APPDATA_PATH}:/restore" \
    -e "PUID=$(id -u)" \
    -e "PGID=$(id -g)" \
    -e "SETTINGS_ENCRYPTION_KEY=${DUPLICATI_PASSPHRASE}" \
    lscr.io/linuxserver/duplicati:latest
fi

info "Waiting for Duplicati to initialize (20s)..."
sleep 20

RESTORE_EXIT=0
if [[ "$SOURCE_MODE" == "b2" ]]; then
  $DOCKER_CMD exec duplicati-restore \
    with-contenv /bin/bash -c "
      cd /app/duplicati && ./duplicati-cli restore '${BACKUP_STORAGE_URL}' \
        --passphrase='${DUPLICATI_PASSPHRASE}' \
        --b2-accountid='${B2_KEY_ID}' \
        --b2-applicationkey='${B2_APPLICATION_KEY}' \
        --restore-path=/restore \
        --overwrite=true \
        --allow-sleep=true \
        2>&1
    " || RESTORE_EXIT=$?
else
  $DOCKER_CMD exec duplicati-restore \
    with-contenv /bin/bash -c "
      cd /app/duplicati && ./duplicati-cli restore '${BACKUP_STORAGE_URL}' \
        --passphrase='${DUPLICATI_PASSPHRASE}' \
        --restore-path=/restore \
        --overwrite=true \
        --allow-sleep=true \
        2>&1
    " || RESTORE_EXIT=$?
fi

# Always clean up
$DOCKER_CMD stop duplicati-restore &>/dev/null || true
$DOCKER_CMD rm   duplicati-restore &>/dev/null || true

if [[ $RESTORE_EXIT -ne 0 ]]; then
  warn "Duplicati CLI restore exited with code ${RESTORE_EXIT}"
  warn "Fallback: restore via the web UI instead."
  if [[ "$SOURCE_MODE" == "b2" ]]; then
    warn "  1. $DOCKER_CMD run -d --name dup-ui -p 8200:8200 \\"
    warn "          -v ${APPDATA_PATH}:/restore \\"
    warn "          -e SETTINGS_ENCRYPTION_KEY=${DUPLICATI_PASSPHRASE} \\"
    warn "          lscr.io/linuxserver/duplicati:latest"
    warn "  2. Open http://$(hostname -I | awk '{print $1}'):8200"
    warn "  3. Add backup → Backblaze B2 → bucket: yourusername-appdata-backup"
    warn "     Auth: keyID=${B2_KEY_ID} / applicationKey from secrets"
    warn "  4. Run restore, target path: /restore"
  else
    warn "  1. $DOCKER_CMD run -d --name dup-ui -p 8200:8200 \\"
    warn "          -v ${MOUNT_BASE}/backups:/backups \\"
    warn "          -v ${APPDATA_PATH}:/restore \\"
    warn "          -e SETTINGS_ENCRYPTION_KEY=${DUPLICATI_PASSPHRASE} \\"
    warn "          lscr.io/linuxserver/duplicati:latest"
    warn "  2. Open http://$(hostname -I | awk '{print $1}'):8200"
    warn "  3. Add backup → Import → file:///backups/homelab-appdata"
    warn "  4. Run restore, target path: /restore"
  fi
  read -rp "Press ENTER once restore is complete, or Ctrl+C to abort: "
fi

# Duplicati restores to original path structure: /restore/source/<files>
# Flatten if needed
if [[ -d "${APPDATA_PATH}/source" ]] && [[ ! -d "${APPDATA_PATH}/plex" ]]; then
  info "Adjusting restore path structure (moving from /restore/source/ up)..."
  mv "${APPDATA_PATH}/source/"* "${APPDATA_PATH}/"
  rmdir "${APPDATA_PATH}/source" 2>/dev/null || true
fi

# Spot-check
[[ -d "${APPDATA_PATH}/plex" ]] \
  || warn "plex directory not found in ${APPDATA_PATH} — restore may be incomplete"

success "Appdata restored to ${APPDATA_PATH}"
info "Restored directories: $(ls "${APPDATA_PATH}" | tr '\n' ' ')"

# =============================================================================
step "7/9  Build .env"
# =============================================================================

ENV_FILE="${COMPOSE_DIR}/compose/.env"

cat > "$ENV_FILE" <<EOF
# Generated by dr/restore.sh on $(date)
# DO NOT commit this file to git

# --- Timezone & IDs ---
TZ=America/New_York
PUID=1000
PGID=1000

# --- Paths (adjusted for DR host) ---
APPDATA_PATH=${APPDATA_PATH}
MEDIA_DS=${MOUNT_BASE}/media_ds
DOWNLOADS_DS=${MOUNT_BASE}/downloads_ds
BACKUPS=${MOUNT_BASE}/backups

# --- PIA VPN ---
PIA_USER=${PIA_USER}
PIA_PASS=${PIA_PASS}
OPENVPN_CONFIG=${OPENVPN_CONFIG:-ca_montreal}

# --- Duplicati ---
DUPLICATI_ENCRYPTION_KEY=${DUPLICATI_PASSPHRASE}
DUPLICATI_WEB_PASSWORD=${DUPLICATI_WEB_PASSWORD:-${DUPLICATI_PASSPHRASE}}

# --- Plex ---
# Get a fresh token at https://www.plex.tv/claim (valid 4 min)
# Fill in PLEX_CLAIM below, run: docker compose up -d plex
PLEX_CLAIM=

# --- Watchtower ---
WATCHTOWER_NOTIFICATION_URL=${WATCHTOWER_NOTIFICATION_URL:-}
EOF

chmod 600 "$ENV_FILE"
success ".env written and secured (chmod 600)"

# =============================================================================
step "8/9  Hardware capability check"
# =============================================================================

if [[ -e /dev/dri ]]; then
  success "/dev/dri found — Plex Intel Quick Sync hardware transcoding will be enabled"
else
  warn "/dev/dri not found — disabling Plex hardware transcoding in compose"
  sed -i 's|      - /dev/dri:/dev/dri|      # - /dev/dri:/dev/dri  # DISABLED: no iGPU on this DR host|' \
    "${COMPOSE_DIR}/compose/docker-compose.yml"
  info "Plex will fall back to software transcoding"
fi

if lsmod 2>/dev/null | grep -q '^tun '; then
  success "TUN kernel module loaded — TransmissionVPN can run"
  TUN_AVAILABLE=true
else
  warn "TUN module not loaded — TransmissionVPN will be skipped"
  warn "  To enable: sudo modprobe tun && echo 'tun' | sudo tee -a /etc/modules"
  TUN_AVAILABLE=false
fi

# =============================================================================
step "9/9  Pull images & start stack"
# =============================================================================

cd "${COMPOSE_DIR}/compose"

info "Pulling Docker images (skip with Ctrl+C if already cached)..."
$DOCKER_CMD compose pull || warn "Some images failed to pull — continuing anyway"
success "Images ready"

info "Starting containers..."
if [[ "$TUN_AVAILABLE" == "true" ]]; then
  $DOCKER_CMD compose up -d
  success "Full stack started (including TransmissionVPN)"
else
  $DOCKER_CMD compose up -d --scale transmissionvpn=0
  warn "Stack started WITHOUT TransmissionVPN"
  warn "After loading TUN module: $DOCKER_CMD compose up -d transmissionvpn"
fi

# =============================================================================
step "10/10 Health check"
# =============================================================================

info "Waiting 30 seconds for containers to stabilize..."
sleep 30

HOST_IP=$(hostname -I | awk '{print $1}')

echo ""
printf "${BOLD}%-22s %-12s %s${NC}\n" "CONTAINER" "STATUS" "URL"
printf "%-22s %-12s %s\n" "─────────────────────" "──────────" "───────────────────"

declare -A SERVICE_PORTS=(
  ["plex"]="32400/web"
  ["sonarr"]="8989"
  ["radarr"]="7878"
  ["radarr4k"]="7070"
  ["bazarr"]="6767"
  ["prowlarr"]="9696"
  ["flaresolverr"]="8191"
  ["transmissionvpn"]="9091"
  ["seerr"]="5055"
  ["organizr"]="8006"
  ["agregarr"]="7171"
  ["tautulli"]="8181"
  ["tdarr"]="8265"
  ["stirling-pdf"]="8585"
  ["npm"]="81"
  ["duplicati"]="8200"
  ["uptimekuma"]="3001"
  ["recyclarr"]="(no UI)"
  ["watchtower"]="(no UI)"
)

ALL_GOOD=true
for name in plex sonarr radarr radarr4k bazarr prowlarr flaresolverr transmissionvpn seerr organizr agregarr tautulli tdarr stirling-pdf npm duplicati uptimekuma recyclarr watchtower; do
  state=$($DOCKER_CMD inspect --format '{{.State.Status}}' "$name" 2>/dev/null || echo "missing")
  port_info="${SERVICE_PORTS[$name]:-}"
  if [[ "$port_info" == "(no UI)" || -z "$port_info" ]]; then
    url="$port_info"
  else
    url="http://${HOST_IP}:${port_info%%/*}"
  fi
  if [[ "$state" == "running" ]]; then
    printf "%-22s ${GREEN}%-12s${NC} %s\n" "$name" "running" "$url"
  elif [[ "$state" == "missing" && "$name" == "transmissionvpn" && "$TUN_AVAILABLE" == "false" ]]; then
    printf "%-22s ${YELLOW}%-12s${NC} %s\n" "$name" "skipped" "(TUN not loaded)"
  else
    printf "%-22s ${RED}%-12s${NC} %s\n" "$name" "$state" "$url"
    ALL_GOOD=false
  fi
done

ELAPSED=$(elapsed)
echo ""
if $ALL_GOOD; then
  echo -e "${GREEN}${BOLD}✓ Stack is UP — total restore time: ${ELAPSED}${NC}"
else
  echo -e "${YELLOW}${BOLD}⚠ Some containers not running — check: docker compose logs <name>${NC}"
  echo -e "  Total time: ${ELAPSED}"
fi

# =============================================================================
echo -e "\n${BOLD}${YELLOW}╔══════════════════════════════════════════════╗"
echo "║              NEXT STEPS                      ║"
echo -e "╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  1. Get a Plex claim token:  https://www.plex.tv/claim"
echo "     Fill into .env PLEX_CLAIM=<token>, then:"
echo "     $DOCKER_CMD compose up -d plex"
echo ""
echo "  2. Fix Plex library paths:"
echo "     Settings → Libraries → Edit → change root to /media/*"
echo ""
echo "  3. Update Prowlarr app URLs to point to new IP (${HOST_IP})"
echo ""
echo "  4. Update router port forward: 32400 → ${HOST_IP}"
echo ""
echo "  5. Verify VPN tunnel:"
echo "     docker exec transmissionvpn curl -s ifconfig.me"
echo ""
echo -e "  See ${COMPOSE_DIR}/dr/playbook.html for the full checklist"
echo ""
