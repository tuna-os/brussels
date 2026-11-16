"""Dependency-tree parsing for the BuildStream dashboard."""

from __future__ import annotations


def parse_bst_show_deps(output: str) -> dict[str, list[str]]:
    """Parse `bst show --deps all --format "%{name}\\t%{deps}\\n"` output.

    %{deps} prints a YAML block sequence, for example:

        name.bst\\t- dep1.bst
        - dep2.bst
        - dep3.bst

    or "[]" when the element has no dependencies. Continuation "- dep" lines
    belong to the element named on the last tab-separated line.
    """
    nodes: dict[str, list[str]] = {}
    current_name: str | None = None
    current_deps: list[str] = []

    def _flush():
        if current_name is not None:
            nodes[current_name] = current_deps[:]

    for raw_line in output.splitlines():
        if "\t" in raw_line:
            _flush()
            name_part, dep_part = raw_line.split("\t", 1)
            current_name = name_part.strip()
            current_deps = []
            dep_part = dep_part.strip()
            if dep_part and dep_part != "[]":
                dep = dep_part.lstrip("-").strip()
                if dep:
                    current_deps.append(dep)
        elif current_name is not None:
            stripped = raw_line.strip()
            if stripped.startswith("-"):
                dep = stripped.lstrip("-").strip()
                if dep:
                    current_deps.append(dep)
    _flush()
    return nodes
