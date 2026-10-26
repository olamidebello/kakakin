# Kakakin Android client

Owner: Olamide Olatayo Bello Corporation. Package `world.africandroid.kakakin`, version 1.0.0 (1), Android 8+. This is a small native Java client for the live Kakakin HTTPS website, not a bundled offline copy. Existing website accounts, campaigns, marketplace, orders and platform controls load inside Android System WebView. Payment gateways and user-selected external links open the browser. CSV/PDF/image uploads use the Android document picker. Browser exports may require signing in again. No Contacts, SMS, phone or broad storage permission; only INTERNET is declared. No native push or background sending. Hardware acceptance testing remains pending.

## Build and upgrades

Install Java JDK 17, Android SDK platform 35 and build-tools 35.0.0. Set ANDROID_HOME, KAKAKIN_KEYSTORE (private backup path), KAKAKIN_KEY_ALIAS=kakakin and KAKAKIN_KEY_PASSWORD in the local environment. Run `bash mobile/android/tools/build.sh`. If a JDK compiler is unavailable, KAKAKIN_ECJ_JAR may point to an Eclipse compiler. Passwords are read through the environment, not committed or put in command arguments. Reuse the private signing backup for every upgrade and increment AndroidManifest.xml versionCode/versionName. Verify with `apksigner verify --verbose --print-certs` and update public/downloads release metadata and the store listing checksums together. Never regenerate the signing key for an update.

The first release signing key is preserved in a separate private backup supplied to the owner. No keystore/password is included in either repository. The public APK is under public/downloads; dist/build directories are excluded from source control.

## Device acceptance checklist

Install on a real Android 8+ device; verify login, logout, tenant switching, small-screen navigation, CSV file selection, back/reload, network outage recovery, SSL rejection and checkout handoff with provider test credentials. Test iPhone Safari Add to Home Screen separately; no iOS native binary is included. This app is not published on Google Play or Apple App Store.
