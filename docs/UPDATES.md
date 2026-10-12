# How RedLua updates itself (the "backend")

From 1.3.0 the app can tell you when a newer build exists and install it for you, without hunting
for a file. There is no RedLua server and nothing is hard-coded: **the backend is one small JSON
file you host**, plus the APK it points at. You can use anything that serves a file over HTTPS.

```
Settings > Updates
  [x] Check for updates          <- off by default, you turn it on once
  https://…/redlua/update.json   <- the manifest address
  [Check now]  [Preview the update screen]
```

## The manifest

`update.json` next to your APK:

```json
{
  "versionName": "1.3.1",
  "versionCode": 1003001,
  "notes": "• What is new goes here\n• One line per change",
  "apkUrl": "https://github.com/<you>/<repo>/releases/download/v1.3.1/RedLua-1.3.1.apk",
  "sizeBytes": 12324072,
  "required": false
}
```

Only `versionName` or `versionCode` is strictly needed for the comparison; `apkUrl` is what the
install button downloads. `required: true` shows a "REQUIRED" badge for updates you consider
mandatory. The app compares `versionCode` first (falling back to the dotted `versionName`), so
"1.10.0" is correctly newer than "1.9.9".

Generate it instead of typing it:

```bash
scripts/publish-update.sh \
  --apk RedLua-1.3.1.apk \
  --url https://github.com/<you>/<repo>/releases/download/v1.3.1/RedLua-1.3.1.apk \
  --notes "Red now floats on the home screen
In-app updates"
```

That writes `update.json` with the version read from the file name, the exact byte size, and a
sha256 you can publish alongside.

## Where to host it (pick one)

| Option | How | Cost |
|---|---|---|
| **GitHub Releases** (easiest) | Create a release, attach the APK, copy the asset's "Copy link" address into `apkUrl`. Put `update.json` in the repo (or in the same release) and use its raw link as the manifest URL. | free |
| Any static host / object store | Upload `update.json` + the APK, use their URLs. Works with S3, Cloudflare R2, Netlify, a VPS, anything HTTPS. | free–cheap |
| Your own PC on the same Wi-Fi | `python3 -m http.server 8000` in the folder with both files, then use `http://<your-pc-ip>:8000/update.json` on the phone. | free, LAN only |

The manifest URL must start with `http://` or `https://` — the app refuses anything else.

## What the user sees

1. Launch (with checks on) → the app quietly fetches the manifest after a couple of seconds.
2. Newer build found → a **"NEW UPDATE AVAILABLE!"** banner at the top of Home, plus a sheet with
   the version, size, what is new, and **[Download & install]** / **[Later]**.
3. Tapping install downloads the APK into the app's cache, then hands it to Android's own
   installer: *"Do you want to update this app?"* → Update. Projects, themes and lesson progress
   are untouched by an update.
4. The first time, Android asks you to allow RedLua to install packages. The app opens that screen
   for you (`Settings > Apps > RedLua > Install unknown apps`) and explains the step.
5. Failure is never silent: no signal, a 404, an HTML error page or a corrupt download all produce
   a readable message and a **Try again** button. Nothing installs unless the file starts with the
   right bytes and you confirm with Android.

## No hosting? Two offline paths

- **Preview the update screen** (in Settings) shows the banner/sheet with sample data, so you can
  see the flow without any server.
- **Manual installs still work exactly as before** — hand the APK to the phone and tap it.

## About the two permissions this adds

Installing updates needs permissions, so 1.3.0 declares two things it did not have before — and
this is the honest trade:

| Permission | Why | When it is used |
|---|---|---|
| `INTERNET` | to fetch the manifest JSON and, only if you tap install, the APK | only while update checks are on, and only against the URL you typed |
| `REQUEST_INSTALL_PACKAGES` | so Android will let the app hand an APK to its installer | only when you tap *Download & install* |

With update checks left off (the default) no request is ever made — the app has no hard-coded
server, no analytics and no phone-home. If you would rather keep the binary free of the network
permission entirely, build with `--no-updates`: the whole feature is isolated in
`core/update/`.
