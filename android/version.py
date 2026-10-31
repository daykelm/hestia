"""App version bookkeeping for deploy.sh.

  python3 android/version.py changed   exit 0 when the shell source differs from the last built APK
  python3 android/version.py bump      raise versionCode by one in the manifest
  python3 android/version.py record    write static/app-version.json for the APK just built
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "AndroidManifest.xml"
RECORD = ROOT.parent / "static" / "app-version.json"
APK = ROOT.parent / "static" / "hestia.apk"
VERSION = re.compile(r'android:versionCode="(\d+)"\s+android:versionName="[^"]*"')


def source_hash():
    digest = hashlib.sha256()
    digest.update(VERSION.sub("", MANIFEST.read_text()).encode())
    for path in sorted([*ROOT.glob("src/**/*.java"), *ROOT.glob("res/**/*.xml")]):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def current_code():
    return int(VERSION.search(MANIFEST.read_text()).group(1))


def main(command):
    if command == "changed":
        try:
            last = json.loads(RECORD.read_text()).get("source_hash")
        except (OSError, ValueError):
            last = None
        sys.exit(0 if last != source_hash() or not APK.is_file() else 1)
    if command == "bump":
        code = current_code() + 1
        MANIFEST.write_text(VERSION.sub(f'android:versionCode="{code}"\n    android:versionName="1.{code}"', MANIFEST.read_text()))
        print(code)
        return
    if command == "record":
        RECORD.write_text(json.dumps({"version_code": current_code(), "source_hash": source_hash()}, indent=2) + "\n")
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
