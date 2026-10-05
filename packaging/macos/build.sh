#!/usr/bin/env bash
# Build dist/Chronicle.app and dist/Chronicle-<version>-<arch>.dmg.
#
# Unsigned (ad-hoc) by default: fine on this Mac, blocked by Gatekeeper elsewhere. For distribution set
#   CHRONICLE_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
# and, to notarize, either
#   NOTARY_KEYCHAIN_PROFILE=<name saved with `xcrun notarytool store-credentials`>
# or (CI) APPLE_ID, APPLE_TEAM_ID and APPLE_APP_PASSWORD (an app-specific password).
set -euo pipefail
cd "$(dirname "$0")/../.."

uv sync --locked --extra app --group build
# the version comes from the git tag (hatch-vcs): v0.7.0 -> 0.7.0, later commits -> 0.7.1.dev3+g1a2b3c4
VERSION=$(uv run --no-sync python -c "from importlib.metadata import version; print(version('agents-chronicle'))")
ARCH=${CHRONICLE_TARGET_ARCH:-$(uname -m)}
IDENTITY=${CHRONICLE_CODESIGN_IDENTITY:-}
APP=dist/Chronicle.app
DMG=dist/Chronicle-$VERSION-$ARCH.dmg

echo "==> Chronicle $VERSION ($ARCH), ${IDENTITY:-ad-hoc signature}"
uv run --no-sync pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller \
    packaging/macos/Chronicle.spec

echo "==> smoke test"
"$APP/Contents/MacOS/Chronicle" --help >/dev/null
if [ -n "$IDENTITY" ]; then
    codesign --verify --deep --strict --verbose=2 "$APP"
fi

echo "==> $DMG"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
ditto "$APP" "$STAGE/Chronicle.app"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -quiet -volname "Chronicle" -srcfolder "$STAGE" -ov -format UDZO "$DMG"

if [ -n "$IDENTITY" ]; then
    codesign --sign "$IDENTITY" --timestamp "$DMG"
    if [ -n "${NOTARY_KEYCHAIN_PROFILE:-}" ]; then
        NOTARY=(--keychain-profile "$NOTARY_KEYCHAIN_PROFILE")
    elif [ -n "${APPLE_ID:-}" ]; then
        NOTARY=(--apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD")
    else
        NOTARY=()
    fi
    if [ ${#NOTARY[@]} -gt 0 ]; then
        echo "==> notarizing (takes a few minutes)"
        xcrun notarytool submit "$DMG" "${NOTARY[@]}" --wait
        xcrun stapler staple "$DMG"
        spctl --assess --type open --context context:primary-signature --verbose "$DMG"
    else
        echo "!! signed but not notarized: set NOTARY_KEYCHAIN_PROFILE or APPLE_ID/APPLE_TEAM_ID/APPLE_APP_PASSWORD"
    fi
fi
echo "==> done: $APP, $DMG"
