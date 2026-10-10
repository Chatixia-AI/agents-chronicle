#!/usr/bin/env bash
# Build dist/Interlatch.app and dist/Interlatch-<version>-<arch>.dmg.
#
# Unsigned (ad-hoc) by default: fine on this Mac, blocked by Gatekeeper elsewhere. For distribution set
#   INTERLATCH_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
# and, to notarize, either
#   NOTARY_KEYCHAIN_PROFILE=<name saved with `xcrun notarytool store-credentials`>
# or (CI) APPLE_ID, APPLE_TEAM_ID and APPLE_APP_PASSWORD (an app-specific password).
# The CHRONICLE_* names from before the rename still work when the INTERLATCH_* one isn't set.
set -euo pipefail
cd "$(dirname "$0")/../.."

# Interlatch.spec reads these two
export INTERLATCH_CODESIGN_IDENTITY=${INTERLATCH_CODESIGN_IDENTITY:-${CHRONICLE_CODESIGN_IDENTITY:-}}
export INTERLATCH_TARGET_ARCH=${INTERLATCH_TARGET_ARCH:-${CHRONICLE_TARGET_ARCH:-}}

uv sync --locked --extra app --group build
# the version comes from the git tag (hatch-vcs): v0.7.0 -> 0.7.0, later commits -> 0.7.1.dev3+g1a2b3c4
VERSION=$(uv run --no-sync python -c "from importlib.metadata import version; print(version('interlatch'))")
ARCH=${INTERLATCH_TARGET_ARCH:-$(uname -m)}
IDENTITY=$INTERLATCH_CODESIGN_IDENTITY
APP=dist/Interlatch.app
DMG=dist/Interlatch-$VERSION-$ARCH.dmg

echo "==> Interlatch $VERSION ($ARCH), ${IDENTITY:-ad-hoc signature}"
uv run --no-sync pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller \
    packaging/macos/Interlatch.spec

echo "==> smoke test"
"$APP/Contents/MacOS/Interlatch" --help >/dev/null
if [ -n "$IDENTITY" ]; then
    codesign --verify --deep --strict --verbose=2 "$APP"
fi

echo "==> $DMG"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
ditto "$APP" "$STAGE/Interlatch.app"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -quiet -volname "Interlatch" -srcfolder "$STAGE" -ov -format UDZO "$DMG"

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
