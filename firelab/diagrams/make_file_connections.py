"""Draw how firelab's files connect, from the imports in the source.

    python3 diagrams/make_file_connections.py      # run from firelab/

Writes five diagrams into `diagrams/`:

    file-connections.mmd   the overview: one box per layer, arrows between layers
    app.mmd                what each file in app/ uses
    engine.mmd             what each file in app/engine/ uses
    adapters.mmd           what each file in adapters/ uses
    domain.mmd             what each file in domain/ uses

Every arrow is read from a real `from .. import` line, so the pictures cannot
drift from the code: an arrow A --> B means "A uses B".

Three simplifications keep the per-layer pictures readable. Small packages are
one box each (`adapters/buildsim/`, `adapters/publisher/`, `app/api/`,
`app/snapshot/`), the arrows from each engine module back to `state.py` are left out, because
every one of them takes the engine as its first argument (said once, in a
note), and `state.py`'s own grip on the domain — it holds one of everything —
is one arrow to the domain box rather than nine.
"""

import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # firelab/
OUT = ROOT / "diagrams"

# module path -> (layer, box id, label). Packages shown as one box come first.
PACKAGES = {
    "adapters.buildsim": ("adapters", "BS_CLIENT", "buildsim/<br/>client · transport · viewer"),
    "adapters.publisher": ("adapters", "PUB", "publisher/<br/>layers · effects · beliefs<br/>people · hardware · routes"),
    "app.api": ("app", "API", "api/<br/>one router per panel"),
    "app.snapshot": ("app", "SNAP", "snapshot/<br/>state → JSON for the panel"),
    "app.engine": ("engine", "E_CORE", "core.py"),  # `from ..engine import Engine`
}
LAYERS = ["app", "engine", "adapters", "domain"]
TITLES = {
    "app": "app/ — the running program",
    "engine": "app/engine/ — the tick loop",
    "adapters": "adapters/ — the BuildSim boundary",
    "domain": "domain/ — the pure rules",
}
SKIP = {"app.engine.constants", "app.engine.__init__", "adapters.__init__", "domain.__init__", "app.__init__"}

INIT = (
    "%%{init: {'theme':'dark','themeVariables':{'background':'#1e1e2e','lineColor':'#a0a0b8',"
    "'clusterBkg':'#26263a','clusterBorder':'#6a6a8a','edgeLabelBackground':'#1e1e2e',"
    "'fontFamily':'Arial, Helvetica, sans-serif','fontSize':'14px'},"
    "'flowchart':{'padding':12,'nodeSpacing':22,'rankSpacing':80,'curve':'basis'}}}%%"
)
STYLE = [
    "    linkStyle default stroke:#8a8aa8,stroke-width:1px",
    "    classDef app      fill:#2e2a4a,stroke:#b07cd8,color:#eeeeee",
    "    classDef engine   fill:#1e3a2a,stroke:#58d68d,color:#eeeeee",
    "    classDef adapters fill:#4a3d1a,stroke:#f1c40f,color:#eeeeee",
    "    classDef domain   fill:#1e2e5a,stroke:#5dade2,color:#eeeeee",
    "    classDef ext      fill:#2a2a3a,stroke:#8a8aaa,color:#eeeeee",
    "    classDef note     fill:#1e1e2e,stroke:#6a6a8a,color:#c0c0d0,stroke-dasharray:4 3",
]
NOTE = 'NOTE["every engine module takes the engine<br/>(state.py) as its first argument"]'
BUILDSIM = 'BUILDSIM[("BuildSim<br/>port 9090")]'


# ---------------------------------------------------------------- reading the code


def module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def box_of(module: str):
    """Which box a module is drawn in, or None if it is not drawn."""
    for pkg, box in PACKAGES.items():
        if module == pkg or (pkg != "app.engine" and module.startswith(pkg + ".")):
            return box
    if module in SKIP:
        return None
    layer, _, name = module.rpartition(".")
    if layer == "app.engine":
        return ("engine", "E_" + name.upper(), f"{name}.py")
    if layer in ("domain", "adapters", "app"):
        return (layer, layer[0].upper() + "_" + name.upper(), f"{name}.py")
    return None


def resolve(importer: str, node: ast.ImportFrom) -> list[str]:
    """The modules an `ImportFrom` line refers to."""
    base = importer.split(".")
    if (ROOT / Path(*base) / "__init__.py").exists():  # importer is a package
        base = base[: len(base) - node.level + 1]
    else:
        base = base[: len(base) - node.level]
    base = base + (node.module.split(".") if node.module else [])
    targets = []
    for alias in node.names:
        cand = base + [alias.name]
        if (ROOT / Path(*cand)).with_suffix(".py").exists() or (ROOT / Path(*cand)).is_dir():
            targets.append(".".join(cand))  # `from . import actuation`
        else:
            targets.append(".".join(base))  # `from .state import EngineState`
    return targets


def source_files():
    for path in ROOT.rglob("*.py"):
        if not any(part in ("tests", ".venv", "ui", "diagrams", "__pycache__") for part in path.parts):
            yield path


def scan():
    """All boxes, and every (user, used) pair between them."""
    boxes = {}
    links = set()
    for path in source_files():
        src = box_of(module_name(path))
        if src is None:
            continue
        boxes[src[1]] = src
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level:
                for target in resolve(module_name(path), node):
                    dst = box_of(target)
                    if dst is None or dst[1] == src[1]:
                        continue
                    if src[0] == "engine" and dst[1] == "E_STATE":
                        continue  # said once in the note instead
                    boxes[dst[1]] = dst
                    links.add((src[1], dst[1]))
    return boxes, links


# ---------------------------------------------------------------- drawing


def header(title: str, note: str) -> list[str]:
    return [
        "---",
        f"title: {title}",
        "---",
        INIT,
        "",
        "%% An arrow A --> B means: A uses B. Generated; do not edit by hand. Regenerate with",
        "%%     python3 diagrams/make_file_connections.py",
        f"%% {note}",
        "",
        "flowchart LR",
    ]


def subgraph(layer: str, members: list[tuple[str, str]]) -> list[str]:
    lines = [f'    subgraph {layer}["{TITLES[layer]}"]']
    lines += [f'        {box_id}["{label}"]' for box_id, label in sorted(members)]
    lines.append("    end")
    return lines


def classes(boxes: dict, extra: list[str]) -> list[str]:
    lines = list(STYLE)
    for layer in LAYERS:
        ids = sorted(b for b, (lay, _, _) in boxes.items() if lay == layer)
        if ids:
            lines.append(f"    class {','.join(ids)} {layer}")
    return lines + extra + [""]


def write(name: str, lines: list[str]) -> None:
    (OUT / name).write_text("\n".join(lines))


def overview(boxes: dict, links: set) -> None:
    """One box per layer, listing its files; arrows between layers with a count."""
    lines = header(
        "firelab — how the layers connect (generated from the imports)",
        "Each arrow stands for the number of file-level uses written on it.",
    )
    for layer in LAYERS:
        files = sorted(label.split("<br/>")[0] for lay, _, label in boxes.values() if lay == layer)
        lines.append(f'    {layer.upper()}["<b>{TITLES[layer]}</b><br/>{" · ".join(files)}"]')
    lines += [f"    {BUILDSIM}", ""]
    counts = Counter((boxes[a][0], boxes[b][0]) for a, b in links)
    ordered = sorted(counts.items(), key=lambda kv: (LAYERS.index(kv[0][0]), LAYERS.index(kv[0][1])))
    for (a, b), n in ordered:
        if a != b:
            lines.append(f'    {a.upper()} -->|"{n} uses"| {b.upper()}')
    lines += ['    ADAPTERS -.->|"HTTP"| BUILDSIM', ""]
    lines += STYLE
    lines += [f"    class {layer.upper()} {layer}" for layer in LAYERS]
    lines += ["    class BUILDSIM ext", ""]
    write("file-connections.mmd", lines)


def per_layer(layer: str, boxes: dict, links: set) -> None:
    """This layer's files on the left, and only what they use on the right."""
    mine = {b for b, (lay, _, _) in boxes.items() if lay == layer}
    used = {b for a, b in links if a in mine} - mine
    inside = {(a, b) for a, b in links if a in mine and b in mine}
    outward = {(a, b) for a, b in links if a in mine and b not in mine}
    lines = header(
        f"firelab — what {TITLES[layer].split(' — ')[0]} uses (generated from the imports)",
        "Left: this layer's files. Right: the files they use, grouped by layer.",
    )
    lines += subgraph(layer, [(b, boxes[b][2]) for b in mine])
    for other in LAYERS:
        members = [(b, boxes[b][2]) for b in used if boxes[b][0] == other]
        if members:
            lines += subgraph(other, members)
    extra = []
    if layer == "engine":
        lines += [f"    {NOTE}", "    E_STATE ~~~ NOTE"]
        extra.append("    class NOTE note")
    if layer == "adapters":
        lines += [f"    {BUILDSIM}", '    BS_CLIENT -.->|"HTTP"| BUILDSIM']
        extra.append("    class BUILDSIM ext")
    lines.append("")
    lines += [f"    {a} --> {b}" for a, b in sorted(inside)]
    if layer == "engine":
        # state.py holds one of everything in the domain: one arrow, not nine
        outward = {(a, b) for a, b in outward if not (a == "E_STATE" and boxes[b][0] == "domain")}
        lines.append('    E_STATE -->|"holds one of each"| domain')
    lines += [f"    {a} --> {b}" for a, b in sorted(outward)]
    lines.append("")
    shown = {b: boxes[b] for b in mine | used}
    lines += classes(shown, extra)
    write(f"{layer}.mmd", lines)


def main() -> None:
    boxes, links = scan()
    overview(boxes, links)
    for layer in LAYERS:
        per_layer(layer, boxes, links)
        mine = {b for b, (lay, _, _) in boxes.items() if lay == layer}
        n = sum(1 for a, b in links if a in mine and not (a == "E_STATE" and boxes[b][0] == "domain"))
        n += 1 if layer == "engine" else 0  # the one "holds one of each" arrow
        print(f"  {layer + '.mmd':22} {len(mine):2} files, {n:2} arrows")
    print(f"  file-connections.mmd   {len(LAYERS)} layers, {len(links)} uses in total")


if __name__ == "__main__":
    main()
