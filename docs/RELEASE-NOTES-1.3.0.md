# RedLua 1.3.0 — all Luau, Red floats, and updates itself

**Install:** `RedLua-1.3.0.apk` (12,356,912 bytes, Android 8.0+, signed). Installs straight over 1.2.0
or 1.0.1 — same signing key, higher version code — and your projects, themes and lesson progress are
untouched.

---

## 1 · Completely Luau now — no "Lua" left in the app

The engine switched in 1.2.0; this release finishes the job everywhere the word used to appear:

| Was | Now |
|---|---|
| Project type "Lua Script" / badge `LUA` | **"Luau Script"** / `LUAU` |
| Console badge `lua 5.4` | **`luau`** |
| Settings: "LuaJ 3.0.1 runtime" / "LuaJ 3.0.1 (Lua 5.4 semantics)" | **"Luau runtime"** / **"Luau (types, continue, interpolation)"** |
| Onboarding: "Write Lua anywhere" | **"Write Luau anywhere"** |
| Builder: "watch the Lua source regenerate" / "Lua source updated" / "lua code, e.g." | **Luau** in all three |
| Empty state: "Create your first Lua project" | **"Create your first Luau project"** |
| Tutorial "Lua in 60 seconds" (plain `..` style) | **"Luau in 60 seconds"** — annotations, backticks, if-expressions, `continue`, `-=` |
| Tutorial "Tables are everything" (`pairs`, `tostring`) | **generalized iteration** `for key, value in hero do` and interpolation |
| Blank template | already Luau in 1.2.0 (interpolation, annotations, `+=`, `continue`) |

Language coverage is unchanged from 1.2.0 and remains real: type annotations and `type X = …`,
`continue` in every loop form, backtick interpolation, `+= … ..=`, generalized iteration,
if-expressions, bitwise operators, `//`, `0b1010`/`1_000_000`, and Luau's stdlib additions
(`string.split`, `table.clone/find/create/clear`, `math.clamp/round/sign/lerp`, `typeof`, `warn`).
Line numbers are preserved through translation, so errors point where you wrote them.

## 2 · Red floats on the home screen

Red is no longer just a tab — it drifts over the Home page, bobbing and swaying while it goes,
with a speech bubble that makes the introductions:

> *"Ask me anything — I live on your device, no internet needed."*
> *"Try: \"what is continue?\" or \"explain tables\"."*
> *"Paste code and tap send — I will read it line by line."*
> *"Say \"run this\" and I will run it in the sandbox."*
> *"Drag me anywhere. Tap me to chat."*

- **Drag it anywhere** — the position is remembered across launches, and it is clamped so it can
  never be lost off-screen (rotation and split-screen included).
- **Tap it** (or the bubble) to open the chat.
- It stays clear of the header buttons, the New project button and the navigation bar, and it only
  takes touches on itself — the page underneath stays fully usable.
- The tips cycle every ~26 seconds and never interrupt a drag.

Red is still 100% local: ~40 app/Luau topics, a real code reader, sandbox execution on request,
quick arithmetic. No cloud model, no network call.

## 3 · In-app updates — "new update available!"

This is the "backend" you asked for, and it is deliberately small: **one JSON file you host**, plus
the APK it points at. No RedLua server, nothing hard-coded, nothing sent about you.

**How it works**

1. Settings → **Updates** → switch on *Check for updates* and paste your manifest URL. (Both off /
   empty by default; there is no built-in server.)
2. On each launch the app fetches that one file and compares versions.
3. Newer build found → a **"NEW UPDATE AVAILABLE!"** banner at the top of Home and a sheet with the
   version, size, what is new, **[Download & install]** and **[Later]**.
4. Install downloads the APK into the app cache and hands it to Android's own installer:
   *"Do you want to update this app?"* → Update. RedLua cannot install anything silently.
5. First time only, Android asks you to allow RedLua to install packages; the app opens that screen
   for you and explains the step.
6. Everything that can go wrong is reported in plain words — no signal, a 404, an HTML error page,
   a truncated file — each with a **Try again** button.

**Publishing a release** (three commands from now on):

```bash
scripts/publish-update.sh \
  --apk RedLua-1.3.1.apk \
  --url https://github.com/<you>/<repo>/releases/download/v1.3.1/RedLua-1.3.1.apk \
  --notes "What is new, one line per change"
# upload the APK, upload update.json next to it, done.
```

The script reads the version from the file name, writes the exact byte size and a sha256, and
emits a manifest that the app parses. Free hosting options (GitHub Releases, any static host, or a
PC on your Wi-Fi) are in `README-UPDATES.md`, along with the manifest format and the two
permissions this adds.

**The honesty part.** An updater needs the network, so 1.3.0 adds `INTERNET` (to fetch the manifest
and, only when you tap install, the APK) and `REQUEST_INSTALL_PACKAGES` (so the system installer can
be handed the file). With checks off — the default — no request is ever made. If you would rather
keep the app network-free, the whole feature lives in `core/update/` and can be dropped without
touching anything else; say the word and I will build you that variant.

---

## Verification

- **Android: 125 tests, 0 failures.** New this release: `UpdateTest` (16 — version maths including
  `1.10.0 > 1.9.9` and junk versions, manifest parsing, offline/404/missing-URL failures, folder
  scanning, download naming, APK magic-byte check, FileProvider install intent, prefs round-trip and
  opt-in defaults) and `UpdateUiTest` (5 — the banner text and button, the dialog with notes, the
  permission step, the failure state, and floating Red being tappable and draggable). Everything
  from 1.0.1/1.2.0 still passes: Luau 21, Red+course 20, Red UI 8 (now including a real render of
  Home with Red floating and the banner showing).
- **Desktop: 44 tests, 0 failures** (4 new for the desktop updater; the mirror carries the rebrand,
  floating Red, the banner and the same manifest logic — on desktop "Update" opens your browser).
- APK: v2 signature verified, `versionCode 4`, `versionName 1.3.0`, both permissions present, and the
  dex contains `UpdateChecker`, `ApkInstaller`, `UpdateInfo`, `FloatingRed`, `UpdateBanner`,
  `UpdateDialog` alongside the 1.2.0 classes.
- Upgrade path checked: 1.2.0 and 1.3.0 share the same signing SHA-256
  (`32ebbacc…19af`) and the version code goes 3 → 4, which is exactly what Android requires for an
  in-place update.
- Screenshots: `screenshots/android-home-red-update.png` (Red floating + banner over Home),
  `screenshots/android-settings-updates.png` (the Updates settings).

## Files

| File | What |
|---|---|
| `RedLua-1.3.0.apk` | The app (12,356,912 bytes, signed) |
| `RedLua-1.3.0.aab` | Play Store bundle |
| `RedLua-1.3.0-source.zip` | Full Android source |
| `RedLua-1.3.0-desktop-source.zip` | Desktop/Windows source mirror |
| `README-UPDATES.md` | How to host the manifest + publish a release |
| `update.json` | A ready-made manifest for 1.3.0 — replace `YOUR-HOST` with where you upload the APK |
| `update.example.json` | The same manifest with an example next version, for testing the banner |
| `scripts/publish-update.sh` | Generates the manifest from an APK |
| `RedLua-1.3.0-release-notes.md` | This document |

## Two notes, stated plainly

- **One-time install.** The updater cannot help the build you already have installed, because 1.2.0
  has no updater in it. Install **1.3.0** once by hand (as usual); every release after this one can
  arrive through the app, provided you have published a manifest URL in Settings.
- **Nothing is published for you.** There is no server I can host, so `update.json` ships with a
  `YOUR-HOST` placeholder. Upload the APK somewhere with a direct link, put that link in
  `update.json`'s `apkUrl`, upload `update.json`, and paste its address into Settings → Updates. If
  you tell me which host you want (GitHub Releases is the fastest), I will fill the file in for you.
