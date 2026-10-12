#!/usr/bin/env python3
"""
publish_to_github.py - publish a RedLua build to GitHub and regenerate update.json.

RedLua's in-app updater reads ONE file (update.json) and downloads the APK it points at.
This script makes that file, and keeps the repository in sync:

  1. creates the repository if it does not exist yet (skips if it does)
  2. creates a release for the version and uploads the APK / AAB / source zips / notes
  3. writes update.json with the real download URL, size and sha256
  4. commits update.json, README, docs and screenshots to the repository
  5. prints the exact URL to paste into RedLua > Settings > Updates

The token is read from the GITHUB_TOKEN environment variable and is never written to disk,
never printed, and never included in a commit. Everything goes through the REST API, so no
credential file (`.git-credentials`) is ever created.

    GITHUB_TOKEN=... python3 tools/publish_to_github.py \
        --repo redlua --version 1.3.0 \
        --apk /path/RedLua-1.3.0.apk \
        --assets /path/RedLua-1.3.0.aab /path/RedLua-1.3.0-source.zip \
        --notes-file /path/RedLua-1.3.0-release-notes.md

Add --dry-run to do everything except talk to GitHub: it writes update.json locally and prints
the plan, which is how you check a release before the token ever exists.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
UA = "RedLua-publisher/1.0"


# --------------------------------------------------------------------------- plumbing

def token() -> str:
    value = os.environ.get("GITHUB_TOKEN", "").strip()
    if not value:
        sys.exit("error: set GITHUB_TOKEN (never pass it as an argument - it would land in your shell history)")
    return value


def call(method: str, path: str, body=None, tok: str = "", expect=(200, 201), raw_url=False):
    """One REST call. Returns parsed JSON, or the raw text when the endpoint is not JSON."""
    url = path if raw_url or path.startswith("http") else API + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        return e.code, {"message": detail}
    except Exception as e:  # network down, DNS, timeout...
        return 0, {"message": f"{type(e).__name__}: {e}"}
    if status not in expect:
        return status, {"message": f"unexpected status {status}"}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def upload_asset(release: dict, path: str, tok: str):
    """
    Uploads one release asset, replacing an existing asset of the same name.

    Uses curl: the releases upload host rejects urllib's request body with
    "Multipart form data required" (400) even for a plain octet-stream body.
    The token goes into a 0600 --config file, so it never appears in argv / ps.
    """
    import subprocess
    import tempfile

    name = os.path.basename(path)
    url = f"{release['upload_url'].split('{')[0]}?name={urllib.parse.quote(name)}"

    with tempfile.NamedTemporaryFile("w", suffix=".curlrc", delete=False) as cfg:
        cfg.write(f'header = "Authorization: Bearer {tok}"\n'
                  f'header = "User-Agent: {UA}"\n'
                  'header = "Content-Type: application/octet-stream"\n')
        cfg_path = cfg.name
    os.chmod(cfg_path, 0o600)

    def once():
        proc = subprocess.run(
            ["curl", "-s", "-K", cfg_path, "-o", "-", "-w", "\n%{http_code}",
             "-X", "POST", "--data-binary", f"@{path}", url],
            capture_output=True, timeout=900)
        out = proc.stdout.decode("utf-8", "replace")
        body, _, code = out.rpartition("\n")
        try:
            return int(code), json.loads(body)
        except Exception:
            return 0, {"message": body[:300]}

    try:
        status, res = once()
        if status in (400, 422) and ("already_exists" in str(res) or status == 422):
            # replace it: drop the old asset, then upload once more
            st, assets = call("GET", f"/repos/{release['_owner']}/{release['_repo']}"
                                     f"/releases/{release['id']}/assets", tok=tok)
            if st == 200:
                for a in assets:
                    if a.get("name") == name:
                        call("DELETE", f"/repos/{release['_owner']}/{release['_repo']}"
                                      f"/releases/assets/{a['id']}", tok=tok)
            status, res = once()
        return status, res
    finally:
        try:
            os.remove(cfg_path)
        except OSError:
            pass


def push_files(owner: str, repo: str, specs, message: str, tok: str, note: str = ""):
    """Commit local files into the repo tree (Contents API - no git, no credential files)."""
    pushed = set()
    for spec in specs:
        if ":" not in spec:
            print(f"  skipping '{spec}' (expected localpath:repopath)")
            continue
        local, remote = spec.split(":", 1)
        if not os.path.isfile(local):
            print(f"  skipping {local} (not found)")
            continue
        with open(local, "rb") as f:
            content = f.read()
        status, res = put_file(owner, repo, remote, content, f"{message}{note}", tok)
        print(f"  committed {remote}" if status in (200, 201) else
              f"  WARNING: could not commit {remote}: {str(res.get('message', ''))[:200]}")
        if status in (200, 201):
            pushed.add(remote)
    return pushed


def put_file(owner: str, repo: str, path: str, content: bytes, message: str, tok: str):
    """Create or update a file in the repo (Contents API - no git, no credential files)."""
    status, existing = call("GET", f"/repos/{owner}/{repo}/contents/{path}", tok=tok, expect=(200, 404))
    body = {"message": message, "content": base64.b64encode(content).decode()}
    if status == 200 and isinstance(existing, dict) and "sha" in existing:
        try:  # identical content -> leave it alone instead of writing an empty commit
            if existing.get("encoding") == "base64" and base64.b64decode(existing["content"]) == content:
                return 200, existing
        except Exception:
            pass
        body["sha"] = existing["sha"]
    return call("PUT", f"/repos/{owner}/{repo}/contents/{path}", body, tok=tok, expect=(200, 201))


def apk_version_code(apk_path: str):
    """
    Reads android:versionCode straight out of the built APK's binary manifest.

    The manifest must publish the SAME number the APK carries, or the app will offer an
    update it is already running. Reading it from the artifact makes that impossible to
    get wrong (no aapt / SDK required).
    Returns None if the manifest cannot be understood - then pass --version-code.
    """
    import struct
    import zipfile

    try:
        with zipfile.ZipFile(apk_path) as z:
            data = z.read("AndroidManifest.xml")
    except Exception:
        return None

    if len(data) < 8:
        return None
    try:
        ctype, header_size, _ = struct.unpack_from("<HHI", data, 0)
    except struct.error:
        return None
    if ctype != 0x0003:            # must be the XML root chunk
        return None

    def read_strings(off: int):
        count, _style, flags, strings_start, _styles = struct.unpack_from("<IIIII", data, off + 8)
        utf8 = bool(flags & (1 << 8))
        out = []
        for i in range(count):
            (str_off,) = struct.unpack_from("<I", data, off + 28 + i * 4)
            pos = off + strings_start + str_off
            if utf8:
                n = data[pos]
                pos += 2 if (n & 0x80) else 1      # high bit -> two-byte length
                if n & 0x80:
                    n = ((n & 0x7F) << 8) | data[pos - 1]
                out.append(data[pos:pos + n].decode("utf-8", "replace"))
            else:
                n = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                if n & 0x8000:
                    n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, pos)[0]
                    pos += 2
                out.append(data[pos:pos + n * 2].decode("utf-16-le", "replace"))
        return out

    strings = []
    off = header_size
    while off + 8 <= len(data):
        ctype, chdr, csize = struct.unpack_from("<HHI", data, off)
        if csize <= 0:
            break
        if ctype == 0x0001:                      # string pool
            strings = read_strings(off)
        elif ctype == 0x0102 and strings:        # start element
            _ns, name_idx, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", data, off + 16)
            node = strings[name_idx] if name_idx < len(strings) else ""
            if node == "manifest":
                attrs = off + 16 + attr_start
                for a in range(attr_count):
                    base = attrs + a * attr_size
                    a_ns, a_name, a_raw = struct.unpack_from("<III", data, base)
                    _sz, _res0, dtype, dval = struct.unpack_from("<HBBI", data, base + 12)
                    key = strings[a_name] if a_name < len(strings) else ""
                    if key == "versionCode" and dtype == 0x10:   # INT_DEC
                        return int(dval)
        off += csize
    return None


def version_code(version: str) -> int:
    """1.3.0 -> 1003000. Comparable, so 1.10.0 correctly beats 1.9.9."""
    parts = [int(p) for p in version.split(".") if p.isdigit()][:3]
    while len(parts) < 3:
        parts.append(0)
    return parts[0] * 1_000_000 + parts[1] * 1_000 + parts[2]


def human(n: int) -> str:
    return f"{n / (1024 * 1024):.2f} MB" if n >= 1024 * 1024 else f"{n / 1024:.0f} KB"


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="Publish a RedLua release to GitHub and refresh update.json")
    ap.add_argument("--repo", required=True, help="repository name, e.g. redlua")
    ap.add_argument("--version", required=True, help="version name, e.g. 1.3.0")
    ap.add_argument("--tag", default=None, help="release tag (default vVERSION)")
    ap.add_argument("--apk", required=True, help="the built APK - this is what the updater downloads")
    ap.add_argument("--assets", nargs="*", default=[], help="extra release assets (AAB, source zips, notes)")
    ap.add_argument("--notes-file", default=None, help="markdown file used as the release description")
    ap.add_argument("--notes", default=None, help="short changelog (one line per change) for update.json")
    ap.add_argument("--files", nargs="*", default=[], help="repo files as localpath:repopath (e.g. README.md:README.md)")
    ap.add_argument("--description", default="RedLua - offline Luau editor, app builder and course for Android.")
    ap.add_argument("--private", action="store_true", help="create a private repo (NOT usable for in-app updates)")
    ap.add_argument("--dry-run", action="store_true", help="do everything except call GitHub")
    ap.add_argument("--version-code", dest="code_arg", type=int, default=None,
                    help="override the versionCode (default: read from the APK)")
    ap.add_argument("--out", default="update.json", help="where to write the manifest")
    args = ap.parse_args()

    tag = args.tag or f"v{args.version}"
    apk = os.path.abspath(args.apk)
    if not os.path.isfile(apk):
        sys.exit(f"error: no such APK: {apk}")
    size = os.path.getsize(apk)

    def sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    # ---------------------------------------------------------------- dry run
    if args.dry_run:
        url = f"https://github.com/<owner>/{args.repo}/releases/download/{tag}/{os.path.basename(apk)}"
        manifest = {
            "versionName": args.version,
            "versionCode": args.code_arg or apk_version_code(apk) or version_code(args.version),
            "notes": args.notes or "",
            "apkUrl": url,
            "sizeBytes": size,
            "required": False,
            "sha256": sha256(apk),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("DRY RUN - nothing was sent to GitHub.")
        print(f"  repo        <owner>/{args.repo} ({'private' if args.private else 'public'})")
        print(f"  release     {tag}")
        print(f"  apk         {os.path.basename(apk)}  {human(size)}  sha256 {manifest['sha256'][:16]}...")
        for a in args.assets:
            print(f"  asset       {os.path.basename(a)}  {human(os.path.getsize(a))}")
        for spec in args.files:
            local = spec.split(":")[0]
            print(f"  repo file   {spec.split(':', 1)[1]}  <- {local}")
        print(f"  manifest    {args.out}")
        print(f"  manifest url will be: https://raw.githubusercontent.com/<owner>/{args.repo}/main/{os.path.basename(args.out)}")
        print("\nNote: the APK/AAB/zips go to the release; only small text + screenshots go in the repo tree.")
        return 0

    tok = token()

    # ---------------------------------------------------------------- who are we
    status, me = call("GET", "/user", tok=tok)
    if status != 200:
        sys.exit(f"error: the token was rejected ({status}). Check it is valid and not expired.")
    owner = me["login"]
    print(f"token OK, authenticated as {owner}")

    # ---------------------------------------------------------------- repo
    status, repo = call("GET", f"/repos/{owner}/{args.repo}", tok=tok, expect=(200, 404))
    if status == 200:
        print(f"repo {owner}/{args.repo} already exists - reusing it")
    else:
        print(f"creating repo {owner}/{args.repo} ...")
        status, repo = call("POST", "/user/repos", {
            "name": args.repo,
            "description": args.description,
            "private": args.private,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False,
        }, tok=tok)
        if status not in (200, 201):
            msg = repo.get("message", "")[:300]
            print(f"error: could not create the repository ({status}): {msg}")
            print("A classic token needs the 'repo' scope (or 'public_repo' for a public repo).")
            print(f"Alternative: create an empty repo at https://github.com/new named '{args.repo}' and re-run.")
            return 1
        print(f"created {repo['html_url']}")

    if args.private:
        print("WARNING: a private repo's downloads need authentication - the in-app updater cannot use them.")

    # ------------------------------------------------------- seed an empty repo
    # GitHub refuses to create a release in a repo that has no commits at all
    # ("Repository is empty"), so the first publish commits the docs/screenshots
    # before touching the release API.
    seeded = False
    status, probe = call("GET", f"/repos/{owner}/{args.repo}/contents/README.md", tok=tok, expect=(200, 404))
    if status == 404 and args.files:
        print("repo has no commits yet - seeding it with the docs and screenshots ...")
        push_files(owner, args.repo, args.files, f"Seed RedLua {args.version}", tok)
        seeded = True

    # ---------------------------------------------------------------- release
    status, rel = call("GET", f"/repos/{owner}/{args.repo}/releases/tags/{tag}", tok=tok, expect=(200, 404))
    body = ""
    if args.notes_file and os.path.isfile(args.notes_file):
        with open(args.notes_file, encoding="utf-8") as f:
            body = f.read()
    if status == 200:
        print(f"release {tag} already exists - uploading/replacing assets")
        rel["_owner"], rel["_repo"] = owner, args.repo
    else:
        print(f"creating release {tag} ...")
        status, rel = call("POST", f"/repos/{owner}/{args.repo}/releases", {
            "tag_name": tag,
            "name": f"RedLua {args.version}",
            "body": body or f"RedLua {args.version}",
            "draft": False,
            "prerelease": False,
        }, tok=tok)
        if status not in (200, 201):
            sys.exit(f"error: could not create the release ({status}): {rel.get('message', '')[:300]}")
        rel["_owner"], rel["_repo"] = owner, args.repo

    # ---------------------------------------------------------------- assets
    to_upload = [apk] + [os.path.abspath(a) for a in args.assets]
    if args.notes_file and args.notes_file.endswith(".md") and os.path.abspath(args.notes_file) not in to_upload:
        to_upload.append(os.path.abspath(args.notes_file))

    apk_url = ""
    for path in to_upload:
        name = os.path.basename(path)
        status, res = upload_asset(rel, path, tok)
        if status not in (200, 201):
            sys.exit(f"error: uploading {name} failed ({status}): {str(res.get('message', ''))[:300]}")
        print(f"  uploaded {name}  ({human(os.path.getsize(path))})")
        if os.path.abspath(path) == apk:
            apk_url = res["browser_download_url"]

    # ---------------------------------------------------------------- update.json
    code = args.code_arg or apk_version_code(apk) or version_code(args.version)
    print(f"  versionCode {code}" + (" (read from the APK)" if apk_version_code(apk) == code else " (from the version name)"))

    manifest = {
        "versionName": args.version,
        "versionCode": code,
        "notes": args.notes or f"RedLua {args.version}",
        "apkUrl": apk_url,
        "sizeBytes": size,
        "required": False,
        "sha256": sha256(apk),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {args.out}  (apkUrl -> {apk_url or 'MISSING'})")

    # ---------------------------------------------------------------- repo files
    commit_msg = f"Publish RedLua {args.version}"
    status, res = put_file(owner, args.repo, os.path.basename(args.out),
                           open(args.out, "rb").read(), commit_msg, tok)
    print(f"  committed {os.path.basename(args.out)}" if status in (200, 201) else
          f"  WARNING: could not commit {args.out}: {str(res.get('message', ''))[:200]}")

    if seeded:
        print("  (docs and screenshots were pushed in the seeding commit above)")
    else:
        push_files(owner, args.repo, args.files, commit_msg, tok)

    raw_base = f"https://raw.githubusercontent.com/{owner}/{args.repo}/main"
    print()
    print("=" * 74)
    print("DONE")
    print(f"  repo          https://github.com/{owner}/{args.repo}")
    print(f"  release       {rel.get('html_url', '')}")
    print(f"  apk           {apk_url}")
    print()
    print("  Paste THIS into RedLua > Settings > Updates:")
    print(f"    {raw_base}/{os.path.basename(args.out)}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
