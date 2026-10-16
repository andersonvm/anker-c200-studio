#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-0.5.0}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid version" >&2; exit 1; }
[[ "$(dpkg --print-architecture)" == amd64 ]] || { echo 'amd64 required' >&2; exit 1; }
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
install -d "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/lib/anker-c200-studio" "$STAGE/usr/share/applications" "$STAGE/usr/share/doc/anker-c200-studio"
install -m 644 "$ROOT/src/app.py" "$STAGE/usr/lib/anker-c200-studio/app.py"
install -m 755 "$ROOT/vendor/anker-powerconf-c200-linux-tools" "$STAGE/usr/lib/anker-c200-studio/anker-powerconf-c200-linux-tools"
install -m 644 "$ROOT/vendor/LICENSE" "$STAGE/usr/share/doc/anker-c200-studio/LICENSE-anker-tools"
install -m 644 "$ROOT/LICENSE" "$STAGE/usr/share/doc/anker-c200-studio/LICENSE-studio"
install -m 644 "$ROOT/packaging/anker-c200-studio.desktop" "$STAGE/usr/share/applications/anker-c200-studio.desktop"
cat > "$STAGE/usr/bin/anker-c200-studio" <<'SCRIPT'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/anker-c200-studio/app.py "$@"
SCRIPT
cat > "$STAGE/usr/bin/anker-c200-tools" <<'SCRIPT'
#!/bin/sh
exec /usr/lib/anker-c200-studio/anker-powerconf-c200-linux-tools "$@"
SCRIPT
chmod 755 "$STAGE/usr/bin/"*
cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: anker-c200-studio
Version: $VERSION
Section: video
Priority: optional
Architecture: amd64
Maintainer: Anker C200 Studio Contributors <noreply@example.invalid>
Depends: python3, python3-tk, python3-opencv, python3-pil, python3-pil.imagetk, v4l-utils, libc6
Description: Anker C200 Studio GUI with bundled camera controller
 Camera controls, live preview and profiles for Anker PowerConf C200.
 Includes the original MIT-licensed third-party camera controller.
CONTROL
mkdir -p "$ROOT/dist"
dpkg-deb --build --root-owner-group "$STAGE" "$ROOT/dist/anker-c200-studio_${VERSION}_amd64.deb"
