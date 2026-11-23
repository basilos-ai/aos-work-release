"""Build the next deployment package from the previous published package."""
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

KEYS = {"workbench-backend": "WORKBENCH_VERSION", "workbench-frontend": "WORKBENCH_FRONTEND_VERSION", "workbench-runtime": "RUNTIME_VERSION"}


def replace_one(text, pattern, replacement):
    result, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Expected exactly one match for {pattern!r}, found {count}")
    return result


def update_image_row(notes, component, old_image, image_tag):
    # The group is a display name. The image column identifies the component.
    row = (rf"^\|[^|\r\n]+\|[ \t]*`{re.escape(component)}`[ \t]*\|[ \t]*"
           r"`(?P<tag>[^`\r\n]+)`(?=[ \t]*(?:\||\r?$))")
    matches = list(re.finditer(row, notes, flags=re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected one release notes row for {component}, found {len(matches)}")
    match = matches[0]
    if match["tag"] != old_image:
        raise ValueError(f"{component} release notes show {match['tag']}, expected {old_image}")
    start, end = match.span("tag")
    return notes[:start] + image_tag + notes[end:]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(tree, previous, out, component, image_tag, tag):
    meta = json.loads((previous / "release.json").read_text())
    old_tag = meta["tag_name"]
    if not re.fullmatch(r"v\d{4}\.\d{2}\.\d{2}(?:\.\d+)?", old_tag):
        raise ValueError("Unexpected previous release tag")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", image_tag):
        raise ValueError("Invalid image tag")
    key = KEYS[component]
    env = (tree / ".env.workbench").read_text()
    old_image, = re.findall(rf"^{key}=([^\s]+)$", env, re.MULTILINE)
    new_env = replace_one(env, rf"^{key}=.*$", f"{key}={image_tag}")
    # Preserve the other table rows, prose and download links to unrelated releases.
    notes = update_image_row(meta["body"], component, old_image, image_tag)
    release_ref = rf"(?<![\w.]){re.escape(old_tag)}(?![\w.])"
    notes = re.sub(release_ref, tag, notes)
    title = replace_one(meta["name"], release_ref, tag)

    archive = (previous / "deploy.tar.gz").read_bytes()
    raw = gzip.decompress(archive)
    checks = dict((name, digest) for digest, name in
                  (line.split() for line in (previous / "SHA256SUMS").read_text().splitlines()))
    if checks != {"deploy.tar.gz": sha(archive), "deploy.tar": sha(raw)}:
        raise ValueError("Previous package checksums do not match")
    installer = (tree / "deploy.sh").read_text()
    if installer.encode() != (previous / "deploy.sh").read_bytes():
        raise ValueError("Previous standalone installer differs from its tag")
    new_installer = replace_one(installer, rf"^# aos-work deployment release: {re.escape(old_tag)}$", f"# aos-work deployment release: {tag}")
    new_installer = replace_one(new_installer, rf"^    '{re.escape(old_tag)}': None,$",
                                f"    '{tag}': None,\n    '{old_tag}': '{sha(archive)}',")
    new_installer = replace_one(new_installer, rf"^{key}={re.escape(old_image)}$", f"{key}={image_tag}")
    replacements = {".env.workbench": new_env.encode(), "deploy.sh": new_installer.encode()}
    out.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as source, tarfile.open(out / "deploy.tar", "w") as target:
        seen = set()
        for entry in source:
            name = entry.name
            if entry.isdir():
                target.addfile(entry)
                continue
            if not entry.isfile() or name in seen:
                raise ValueError(f"Unexpected archive entry: {name}")
            seen.add(name)
            data = source.extractfile(entry).read()
            if name in replacements:
                if data != (tree / name).read_bytes():
                    raise ValueError(f"Previous archive differs from tagged file: {name}")
                data = replacements[name]
                entry.size = len(data)
            target.addfile(entry, io.BytesIO(data))
        if not replacements.keys() <= seen:
            raise ValueError("Previous archive missing installer or environment")
    for name, data in replacements.items():
        (tree / name).write_bytes(data)
    readme = tree / "README.md"
    readme.write_text(re.sub(release_ref, tag, readme.read_text()))
    (out / "deploy.sh").write_bytes(replacements["deploy.sh"])
    raw = (out / "deploy.tar").read_bytes()
    compressed = gzip.compress(raw, mtime=0)
    (out / "deploy.tar.gz").write_bytes(compressed)
    (out / "SHA256SUMS").write_text(f"{sha(raw)}  deploy.tar\n{sha(compressed)}  deploy.tar.gz\n")
    (out / "notes.md").write_bytes(notes.encode())
    (out / "title").write_text(title)


if __name__ == "__main__":
    tree, previous, out, component, image, tag = sys.argv[1:]
    prepare(Path(tree), Path(previous), Path(out), component, image, tag)
