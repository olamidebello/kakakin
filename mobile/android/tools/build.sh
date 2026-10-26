#!/bin/bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
: "${ANDROID_HOME:?Set ANDROID_HOME to an Android SDK with platform 35 and build-tools 35.0.0}"
: "${KAKAKIN_KEYSTORE:?Set KAKAKIN_KEYSTORE to a persistent signing key}"
: "${KAKAKIN_KEY_PASSWORD:?Set signing password in environment}"
KAKAKIN_KEY_ALIAS=${KAKAKIN_KEY_ALIAS:-kakakin}
TOOLS="$ANDROID_HOME/build-tools/35.0.0"
BUILD="$ROOT/build"
mkdir -p "$BUILD/gen" "$BUILD/classes" "$BUILD/dex" "$ROOT/dist"
"$TOOLS/aapt" package -f -M "$ROOT/app/src/main/AndroidManifest.xml" -S "$ROOT/app/src/main/res" -I "$ANDROID_HOME/platforms/android-35/android.jar" -J "$BUILD/gen" -F "$BUILD/resources.apk"
find "$ROOT/app/src/main/java" "$BUILD/gen" -name '*.java' > "$BUILD/sources.txt"
if command -v javac >/dev/null 2>&1; then
  javac -source 8 -target 8 -bootclasspath "$ANDROID_HOME/platforms/android-35/android.jar" -d "$BUILD/classes" @"$BUILD/sources.txt"
else
  : "${KAKAKIN_ECJ_JAR:?Install a JDK or provide the Eclipse Java compiler JAR}"
  java -jar "$KAKAKIN_ECJ_JAR" -source 8 -target 8 -bootclasspath "$ANDROID_HOME/platforms/android-35/android.jar" -d "$BUILD/classes" @"$BUILD/sources.txt"
fi
python3 - "$BUILD" <<'PYZIP'
import sys,zipfile,pathlib
b=pathlib.Path(sys.argv[1])
with zipfile.ZipFile(b/'classes.jar','w',zipfile.ZIP_DEFLATED) as z:
    for f in (b/'classes').rglob('*.class'): z.write(f,f.relative_to(b/'classes'))
PYZIP
"$TOOLS/d8" --min-api 26 --lib "$ANDROID_HOME/platforms/android-35/android.jar" --output "$BUILD/dex" "$BUILD/classes.jar"
cp "$BUILD/resources.apk" "$BUILD/unsigned.apk"
(cd "$BUILD/dex" && "$TOOLS/aapt" add "$BUILD/unsigned.apk" classes.dex)
"$TOOLS/zipalign" -f -p 4 "$BUILD/unsigned.apk" "$BUILD/aligned.apk"
"$TOOLS/apksigner" sign --ks "$KAKAKIN_KEYSTORE" --ks-key-alias "$KAKAKIN_KEY_ALIAS" --ks-pass env:KAKAKIN_KEY_PASSWORD --key-pass env:KAKAKIN_KEY_PASSWORD --out "$ROOT/dist/kakakin.apk" "$BUILD/aligned.apk"
"$TOOLS/apksigner" verify --verbose "$ROOT/dist/kakakin.apk"
"$TOOLS/aapt" dump badging "$ROOT/dist/kakakin.apk" | head -1
(cd "$ROOT/dist" && sha256sum kakakin.apk > kakakin.apk.sha256)
