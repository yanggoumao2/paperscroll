# Android app

The Android app is a thin [Capacitor](https://capacitorjs.com) shell. It opens the interface served by
**your** PaperScroll server, adds native touches (haptics, share sheet, file export, status-bar colours,
back button, splash screen) and shows an offline page with a retry button when the server is unreachable.
Because the interface is loaded from the server, later UI updates reach the phone without reinstalling.

The server address is baked into the APK at build time, so everyone builds their own APK (about 5 minutes).

> Don't want to build anything? Open `http://<server-address>` in Chrome on the phone and choose
> *Add to home screen*. You get the same interface without native haptics/sharing.

## 1. Find the address the phone will use

Usually your computer's Tailscale address with the TCP serve from [server.md](server.md#reach-it-from-your-phone):
`http://100.x.y.z:8766`. Open it in the phone's browser first and make sure the feed loads.

## 2. Build

### Windows (no Android Studio needed)

```powershell
cd paperscroll\app
# one-time: portable JDK 21 + Android SDK into ..\toolchain (~2 GB, git-ignored)
powershell -ExecutionPolicy Bypass -File scripts\setup-android.ps1
# build (needs Node.js 20+)
powershell -ExecutionPolicy Bypass -File build-apk.ps1 -Server http://100.x.y.z:8766
```

If you already have JDK 21 and the Android SDK, set `JAVA_HOME` and `ANDROID_HOME` and skip the setup script.
Gradle 8.11 does **not** run on JDK 22+; use JDK 21.

### Linux / macOS

```bash
cd paperscroll/app
export JAVA_HOME=/path/to/jdk-21
export ANDROID_HOME=$HOME/Android/Sdk        # needs platforms;android-35 and build-tools;35.0.0
./build-apk.sh http://100.x.y.z:8766
```

The SDK packages can be installed with `sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"`
or through Android Studio.

### Output

- `dist/PaperScroll.apk` — debug-signed, ~5 MB, Android 6.0+ (API 23).
- A copy in `web/download/PaperScroll.apk`, so the phone can download it from
  `http://<server-address>/download/PaperScroll.apk`.

## 3. Install

1. On the phone (Tailscale connected), open `http://<server-address>/download/PaperScroll.apk`, or send the file
   over USB / a messenger.
2. Allow installing from this source when Android asks.
3. Open PaperScroll and describe your research topic.

To update the app later, install the new APK over the old one; your library lives on the server and is kept.

## What the build does

1. Copies `web/` into `app/www` (the bundled copy only provides the offline page).
2. `npx cap sync android` — copies web assets and the Capacitor config into the Android project.
3. `scripts/set-server.mjs` — writes your server address into the generated
   `android/app/src/main/assets/capacitor.config.json` (`server.url`) and the offline page.
4. `gradlew assembleDebug`.

The repository copy of `capacitor.config.json` holds a placeholder; your address never ends up in git.

## Customising

| What | Where |
|---|---|
| App name / package id | `app/capacitor.config.json` (`appName`, `appId`) and `app/android/app/build.gradle` (`applicationId`, `namespace`) |
| Icon and splash | edit `app/icon/icon.html`, then `app/icon/render-icons.ps1` (headless Edge) and `python app/icon/make-res.py` |
| Splash / window colours | `app/android/app/src/main/res/values/ps_colors.xml` (+ `values-night/`) |
| Release signing | standard Gradle `signingConfigs`; see the [Android docs](https://developer.android.com/studio/publish/app-signing) |

## Notes

- The app ignores the system font-size setting (WebView text zoom) because it breaks the one-card-per-screen
  layout; use *Settings → 阅读 → 字号* in the app instead.
- Cleartext HTTP is enabled because traffic inside a tailnet is already encrypted by WireGuard. If you serve
  PaperScroll over plain HTTP on an untrusted network, use HTTPS instead (e.g. `tailscale serve --https`).
