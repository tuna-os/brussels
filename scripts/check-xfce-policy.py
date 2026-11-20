#!/usr/bin/env python3
"""Policy checks for the XFCE layer of this image.

Three checks, each a subcommand (``all`` runs every one):

components
    Every element built from gitlab.xfce.org is pinned to a release tag.
    Core components (the ``xfce/`` group) must be on the 4.21 series, the
    series xfwl4 targets, unless ``tests/xfce-policy.yml`` lists the
    element under ``series_exceptions`` with a reason. A git snapshot (a
    bare commit ref) must be listed under ``snapshot_exceptions``.

patches
    Every patch applied by an element under ``elements/`` (``kind: patch``
    sources and ``patch_queue`` directories of the XFCE layer) carries a
    header with ``Upstream-Status:`` and ``Reason:``, and an
    ``Upstream:`` link unless the status is ``Inappropriate``.

config
    Every xfconf channel file the image ships
    (``**/xfce-perchannel-xml/*.xml`` under ``files/`` and the variant
    directories) is declared in ``tests/xfce-policy.yml`` under
    ``config_overrides``, which lists the properties in which it differs
    from upstream. With ``--upstream`` the file is compared with the
    upstream default for that channel, fetched from gitlab.xfce.org at the
    tag the image pins: a difference that is not declared is drift, and a
    declared property equal to upstream is dead weight.

Exit status is 1 when any check reports a violation.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ELEMENTS = REPO / "elements"
POLICY_FILE = REPO / "tests" / "xfce-policy.yml"
SERIES = "4.21"

# ref written by `bst source track` for a tag: <tag>-<n>-g<sha>
DESCRIBE_REF = re.compile(r"^(?P<tag>.+)-(?P<n>\d+)-g(?P<sha>[0-9a-f]{40})$")
BARE_SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"(\d+\.\d+(?:\.\d+)*)")

# Channel -> (component element, path of the upstream default in its
# repository, format, whole_file). whole_file is True when upstream installs
# that file as the system xfconf default, so an image file at the same path
# replaces it and a property missing from the image file is a removal.
# xfce4-panel is not listed: its default layout is not an xfconf channel
# file, so a shipped panel channel is a whole new layout and every property
# it sets must be declared.
UPSTREAM_DEFAULTS = {
    "xsettings": ("xfce4-settings", "xfsettingsd/xsettings.xml", "xml", True),
    "xfce4-session": ("xfce4-session", "settings/xfce4-session.xml", "xml", True),
    # xfwl4 reads the xfwm4 channel; its built-in defaults are this file.
    "xfwm4": ("xfwl4", "resources/defaults", "keyvalue", False),
}


def load_policy() -> dict:
    return yaml.safe_load(POLICY_FILE.read_text()) or {}


def load_element(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


# ── components ────────────────────────────────────────────────────────────────


def xfce_elements():
    """Yield (element name, first source, group) for gitlab.xfce.org elements."""
    for path in sorted(ELEMENTS.rglob("*.bst")):
        data = load_element(path)
        sources = data.get("sources") or []
        if not sources:
            continue
        src = sources[0]
        url = str(src.get("url", ""))
        if url.startswith("xfce:"):
            group = url[len("xfce:"):].split("/", 1)[0]
        elif url.startswith("xfce_archive:src/"):
            group = url[len("xfce_archive:src/"):].split("/", 1)[0]
        else:
            continue
        yield path.relative_to(ELEMENTS).as_posix(), src, group


def pinned_version(src: dict) -> tuple[str | None, str]:
    """Return (version, kind) where kind is 'tag', 'tarball' or 'snapshot'."""
    if src.get("kind") == "tar":
        m = VERSION.search(Path(str(src["url"])).name)
        return (m.group(1) if m else None), "tarball"
    ref = str(src.get("ref", ""))
    m = DESCRIBE_REF.match(ref)
    if m:
        if m.group("n") != "0":
            return None, "snapshot"
        v = VERSION.search(m.group("tag"))
        return (v.group(1) if v else None), "tag"
    if BARE_SHA.match(ref):
        return None, "snapshot"
    return None, "unknown"


def check_components(policy: dict) -> list[str]:
    errors = []
    series_ex = policy.get("series_exceptions") or {}
    snap_ex = policy.get("snapshot_exceptions") or {}
    seen = set()
    for name, src, group in xfce_elements():
        seen.add(name)
        version, kind = pinned_version(src)
        if kind in ("snapshot", "unknown"):
            if name not in snap_ex:
                errors.append(f"{name}: pinned to a git snapshot ({src.get('ref')}); "
                              "use a release tag or add it to snapshot_exceptions with a reason")
            continue
        if version is None:
            errors.append(f"{name}: cannot read a version from {src.get('ref') or src.get('url')}")
            continue
        if group != "xfce":
            continue  # apps/ and panel-plugins/ have their own version lines
        if version.startswith(SERIES + "."):
            if name in series_ex:
                errors.append(f"{name}: is on {version} now; drop its series_exceptions entry")
            continue
        if name not in series_ex:
            errors.append(f"{name}: {version} is not in the {SERIES} series; bump it or add "
                          "it to series_exceptions with a reason")
        elif str(series_ex[name].get("version")) != version:
            errors.append(f"{name}: series_exceptions records {series_ex[name].get('version')}, "
                          f"the element pins {version}")
    for table, entries in (("series_exceptions", series_ex), ("snapshot_exceptions", snap_ex)):
        for name, entry in entries.items():
            if name not in seen:
                errors.append(f"{table}: {name} is not an XFCE element")
            if not (entry or {}).get("reason"):
                errors.append(f"{table}: {name} has no reason")
    return errors


# ── patches ───────────────────────────────────────────────────────────────────


def applied_patches(policy: dict) -> list[Path]:
    """Patch files applied by elements, minus the policy's junction queues."""
    skip = {REPO / p for p in policy.get("patch_policy_skip") or []}
    found = []
    for path in sorted(ELEMENTS.rglob("*.bst")):
        if path.parent == ELEMENTS:
            continue  # junctions; their queues are listed in patch_policy_skip
        for src in load_element(path).get("sources") or []:
            if src.get("kind") == "patch":
                found.append(REPO / src["path"])
            elif src.get("kind") == "patch_queue":
                found.extend(sorted((REPO / src["path"]).glob("*.patch")))
    return [p for p in found if not any(p.is_relative_to(s) for s in skip)]


HEADER_FIELD = re.compile(r"^(Upstream|Upstream-Status|Reason):\s*(.+)$", re.M)


def patch_header(text: str) -> dict:
    head = text.split("\n---\n", 1)[0].split("\ndiff --git", 1)[0]
    return {k: v.strip() for k, v in HEADER_FIELD.findall(head)}


def check_patches(policy: dict) -> list[str]:
    errors = []
    for patch in applied_patches(policy):
        rel = patch.relative_to(REPO)
        if not patch.exists():
            errors.append(f"{rel}: referenced by an element but missing")
            continue
        fields = patch_header(patch.read_text(errors="replace"))
        status = fields.get("Upstream-Status", "")
        if not status:
            errors.append(f"{rel}: no Upstream-Status: header")
        if not fields.get("Reason"):
            errors.append(f"{rel}: no Reason: header")
        if not status.startswith("Inappropriate") and not fields.get("Upstream", "").startswith("http"):
            errors.append(f"{rel}: no Upstream: link (required unless Upstream-Status is Inappropriate)")
    return errors


# ── config ────────────────────────────────────────────────────────────────────


def channel_files() -> list[Path]:
    roots = [REPO / "files"] + [REPO / d for d in ("variants",) if (REPO / d).exists()]
    out = []
    for root in roots:
        out.extend(sorted(root.rglob("xfce-perchannel-xml/*.xml")))
    return out


def flatten_xml(text: str) -> dict[str, str]:
    """xfconf channel XML -> {'/prop/path': 'value'} (arrays joined with ';')."""
    root = ET.fromstring(text)
    out: dict[str, str] = {}

    def walk(node, prefix):
        for prop in node.findall("property"):
            path = f"{prefix}/{prop.get('name')}"
            ptype = prop.get("type")
            if ptype == "array":
                out[path] = ";".join(v.get("value", "") for v in prop.findall("value"))
            elif ptype != "empty":
                out[path] = prop.get("value", "")
            walk(prop, path)

    walk(root, "")
    return out


def flatten_keyvalue(text: str, prefix: str = "/general") -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[f"{prefix}/{k.strip()}"] = v.strip()
    return out


def upstream_ref(component: str) -> tuple[str, str]:
    """(gitlab project path, tag) of the element that builds the component."""
    for path in ELEMENTS.rglob(f"{component}.bst"):
        src = (load_element(path).get("sources") or [{}])[0]
        url = str(src.get("url", ""))
        m = DESCRIBE_REF.match(str(src.get("ref", "")))
        if url.startswith("xfce:") and m:
            return url[len("xfce:"):].removesuffix(".git"), m.group("tag")
    raise LookupError(f"no tag-pinned element for {component}")


def fetch_upstream(component: str, file: str) -> str:
    project, tag = upstream_ref(component)
    url = (f"https://gitlab.xfce.org/{project}/-/raw/{urllib.parse.quote(tag)}/"
           f"{urllib.parse.quote(file)}")
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (fixed host)
        return resp.read().decode()


def declared(prop: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(prop, pat) for pat in patterns)


def check_config(policy: dict, upstream: bool) -> list[str]:
    """Shipped xfconf channel files against their config_overrides entry.

    An entry lists the properties in which the file differs from upstream
    (fnmatch patterns are allowed). Offline, every property the file sets
    must be declared, except for whole-file replacements of an upstream
    default, where the unchanged upstream properties are carried along.
    With upstream=True the actual difference against the upstream default
    at the pinned tag must equal the declared set: an undeclared
    difference is drift, a declared property equal to upstream is dead.
    """
    errors = []
    overrides = policy.get("config_overrides") or {}
    shipped = {f.relative_to(REPO).as_posix(): f for f in channel_files()}
    for rel in sorted(set(overrides) - set(shipped)):
        errors.append(f"config_overrides: {rel} is declared but not shipped")
    for rel, path in sorted(shipped.items()):
        entry = overrides.get(rel)
        if entry is None:
            errors.append(f"{rel}: shipped xfconf channel is not declared in config_overrides")
            continue
        if not entry.get("reason"):
            errors.append(f"config_overrides: {rel} has no reason")
        text = path.read_text()
        props = flatten_xml(text)
        patterns = entry.get("properties") or []
        channel = ET.fromstring(text).get("name")
        base_spec = UPSTREAM_DEFAULTS.get(channel)
        whole_file = bool(base_spec and base_spec[3])
        for pat in patterns:
            if not any(fnmatch.fnmatchcase(p, pat) for p in props) and not whole_file:
                errors.append(f"config_overrides: {rel} declares {pat}, which the file does not set")
        if not whole_file:
            for p in sorted(props):
                if not declared(p, patterns):
                    errors.append(f"{rel}: sets {p} but config_overrides does not declare it")
        if not upstream or base_spec is None:
            continue
        component, file, fmt, _ = base_spec
        try:
            base_text = fetch_upstream(component, file)
        except (urllib.error.URLError, LookupError) as exc:
            errors.append(f"{rel}: cannot fetch the upstream {channel} default ({exc})")
            continue
        base = flatten_xml(base_text) if fmt == "xml" else flatten_keyvalue(base_text)
        keys = set(props) | (set(base) if whole_file else set())
        diff = {p for p in keys if props.get(p) != base.get(p)}
        for p in sorted(diff):
            if not declared(p, patterns):
                errors.append(f"{rel}: {p} = {props.get(p)!r} differs from upstream "
                              f"{component} {file} ({base.get(p)!r}) but is not declared (drift)")
        for p in sorted(set(props) - diff):
            if declared(p, patterns):
                errors.append(f"{rel}: {p} = {props[p]!r} is the upstream default; "
                              "drop it from config_overrides")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("check", choices=["components", "patches", "config", "all"])
    ap.add_argument("--upstream", action="store_true",
                    help="config: also compare with upstream defaults (needs network)")
    args = ap.parse_args(argv)
    policy = load_policy()
    errors = []
    if args.check in ("components", "all"):
        errors += check_components(policy)
    if args.check in ("patches", "all"):
        errors += check_patches(policy)
    if args.check in ("config", "all"):
        errors += check_config(policy, args.upstream)
    for e in errors:
        print(f"::error::{e}" if "GITHUB_ACTIONS" in os.environ else e)
    print(f"{len(errors)} violation(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
