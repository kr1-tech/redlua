# RedLua 1.3.1

**Nothing to type any more.** RedLua now knows where its own updates live, so updating is a tap
instead of a paste.

## What changed

- **The update feed is built in.** `Settings → Updates` comes with RedLua's own feed already filled
  in — `https://raw.githubusercontent.com/kr1-tech/redlua/main/update.json`. No typing, no copying,
  no "set a manifest URL first".
- **One tap to switch it on.** A *Turn on automatic updates* button in Settings (and a card right on
  the home screen) turns checking on. One tap, once, ever.
- **A reminder on Home.** While updates are off, the home screen shows a small card: *Turn on
  automatic updates*. Tap it and it's done — or tap *Not now* and it stays gone.
- **The feed field is still yours.** RedLua's address is only the default. Type your own URL and the
  app follows that instead — nothing is hard-coded, nothing is locked.
- **Still 100% offline until you say otherwise.** Checking is off on a fresh install. Until you flip
  it on, the app makes no network requests at all. When it is on, the only request it makes is for
  that one JSON file, and the only download it ever performs is the APK that file points at.

## Version

- `versionName 1.3.1` — `versionCode 1003001`
- Same signing key as every previous build, so it installs straight over 1.2.0 / 1.3.0.
- Android 8.0+ (API 26), unchanged permissions: `INTERNET` (used only by the update check) and
  `REQUEST_INSTALL_PACKAGES` (used only to hand a downloaded APK to Android's installer).

## The update flow, end to end

1. RedLua fetches `update.json` from its feed when it launches (and whenever you tap *Check now*).
2. If that file's `versionCode` (or dotted version) is newer than the installed build, the home
   screen shows **NEW UPDATE AVAILABLE!**
3. Tap it → a sheet shows the version, size and notes → *Download & install*.
4. The APK is saved to the app cache, checked to be a real APK, then handed to Android's installer.
5. Android asks you to confirm once (the normal "install unknown apps" prompt). Done.

## Upgrading from 1.3.0

If you already have 1.3.0 with the manifest URL typed in, this arrives on its own as soon as you tap
*Check now* — the old version already knows how to update itself.

If you are still on **1.2.0 or older**, install this one file by hand one last time; those builds
have no updater inside them:

https://github.com/kr1-tech/redlua/releases/download/v1.3.1/RedLua-1.3.1.apk
