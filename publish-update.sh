#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  publish-update.sh - writes the update.json that RedLua's update checker reads.
#
#  The "backend" for in-app updates is one small JSON file. This script builds it
#  from a built APK, so publishing a release is: build, upload the APK, run this,
#  upload update.json next to it.
#
#  usage:
#     scripts/publish-update.sh --apk RedLua-1.3.1.apk \
#         --url https://github.com/<user>/<repo>/releases/download/v1.3.1/RedLua-1.3.1.apk \
#         --notes "What is new, one line per change" \
#         [--required] [--out update.json]
#
#  The version is taken from the APK file name (RedLua-x.y.z.apk). The versionCode
#  is written as a comparable integer (1.3.1 -> 1003001) unless you pass --code N.
# ---------------------------------------------------------------------------
set -euo pipefail

APK=""; URL=""; NOTES=""; OUT="update.json"; REQUIRED="false"; CODE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apk) APK="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    --notes) NOTES="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --code) CODE="$2"; shift 2 ;;
    --required) REQUIRED="true"; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$APK" ]] || { echo "error: --apk is required" >&2; exit 1; }
[[ -f "$APK" ]] || { echo "error: no such file: $APK" >&2; exit 1; }
[[ -n "$URL" ]] || { echo "error: --url is required (where the APK will be hosted)" >&2; exit 1; }

BASE="$(basename "$APK")"
if [[ ! "$BASE" =~ [Rr]ed[Ll]ua[_\ -]?([0-9]+(\.[0-9]+)*)\.apk ]]; then
  echo "error: can't read a version from '$BASE' - name it RedLua-x.y.z.apk" >&2
  exit 1
fi
VERSION="${BASH_REMATCH[1]}"

if [[ -z "$CODE" ]]; then
  # 1.3.1 -> 1003001, so it stays comparable in the app
  IFS='.' read -r MA MI PA <<< "$VERSION"
  CODE=$(( ${MA:-0} * 1000000 + ${MI:-0} * 1000 + ${PA:-0} ))
fi

SIZE=$(stat -c%s "$APK" 2>/dev/null || stat -f%z "$APK")
SHA=$(sha256sum "$APK" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$APK" | cut -d' ' -f1)

# escape the notes for JSON
ESCAPED_NOTES=$(printf '%s' "$NOTES" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])' 2>/dev/null \
  || printf '%s' "$NOTES" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')

cat > "$OUT" <<JSON
{
  "versionName": "$VERSION",
  "versionCode": $CODE,
  "notes": "$ESCAPED_NOTES",
  "apkUrl": "$URL",
  "sizeBytes": $SIZE,
  "required": $REQUIRED,
  "sha256": "$SHA"
}
JSON

echo "wrote $OUT"
echo "  version   $VERSION  (versionCode $CODE)"
echo "  apk       $BASE  ($SIZE bytes)"
echo "  sha256    $SHA"
echo
echo "Next: upload the APK, then upload $OUT to the URL you put in RedLua's Settings > Updates."
