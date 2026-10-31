#!/bin/sh
# Builds android/build/hestia.apk with the plain SDK tools (no Gradle) and copies it to static/ for download.
set -eu
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
TOOLS="$SDK/build-tools/35.0.0"
JAR="$SDK/platforms/android-35/android.jar"
JAVA_HOME="${JAVA_HOME:-$(ls -d ../.tools/jdk-*/Contents/Home | head -1)}"
OUT=build

rm -rf "$OUT" && mkdir -p "$OUT/res" "$OUT/gen" "$OUT/classes" "$OUT/dex"
"$TOOLS/aapt2" compile --dir res -o "$OUT/res.zip"
"$TOOLS/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -o "$OUT/base.apk" --java "$OUT/gen" "$OUT/res.zip"
"$JAVA_HOME/bin/javac" -nowarn -Xlint:-deprecation --release 11 -classpath "$JAR" -d "$OUT/classes" $(find src "$OUT/gen" -name '*.java')
"$TOOLS/d8" --min-api 26 --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && zip -q ../unsigned.apk classes.dex)
"$TOOLS/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

KEY=hestia.keystore
if [ ! -f "$KEY" ]; then
  "$JAVA_HOME/bin/keytool" -genkeypair -keystore "$KEY" -storepass hestia -keypass hestia -alias hestia \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Hestia" >/dev/null
fi
JAVA_HOME="$JAVA_HOME" PATH="$JAVA_HOME/bin:$PATH" "$TOOLS/apksigner" sign --ks "$KEY" --ks-pass pass:hestia --key-pass pass:hestia \
  --out "$OUT/hestia.apk" "$OUT/aligned.apk"
cp "$OUT/hestia.apk" ../static/hestia.apk
echo "built $(du -h "$OUT/hestia.apk" | cut -f1) android/build/hestia.apk"
