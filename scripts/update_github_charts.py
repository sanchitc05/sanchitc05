from __future__ import annotations

import base64
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


USER = os.environ.get("GITHUB_PROFILE_USER", "sanchitc05")
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
MARKER_START = "<!-- LIVE_GITHUB_CHARTS:START -->"
MARKER_END = "<!-- LIVE_GITHUB_CHARTS:END -->"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "copilot-profile-readme",
}

COLORS = [
    "#0f172a",
    "#2563eb",
    "#14b8a6",
    "#f97316",
    "#a855f7",
    "#ef4444",
    "#22c55e",
    "#eab308",
]


def fetch_json(url: str):
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def load_repo_contents(repo: dict) -> dict[str, dict]:
    contents_url = repo["contents_url"].split("{")[0]
    default_branch = repo.get("default_branch") or "main"
    try:
        contents = fetch_json(f"{contents_url}?ref={default_branch}")
    except Exception:
        return {}

    return {
        item["name"].lower(): item
        for item in contents
        if isinstance(item, dict) and item.get("type") == "file"
    }


def read_repo_file(file_entry: dict) -> str:
    download_url = file_entry.get("download_url")
    if download_url:
        try:
            return fetch_text(download_url)
        except Exception:
            pass

    content = file_entry.get("content")
    if content:
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            return ""

    return ""


def detect_framework(repo: dict, file_map: dict[str, dict]) -> str:
    haystack = " ".join(
        [repo.get("name") or "", repo.get("description") or "", " ".join(repo.get("topics") or [])]
    ).lower()

    package_entry = file_map.get("package.json")
    if package_entry:
        try:
            package_data = json.loads(read_repo_file(package_entry))
        except Exception:
            package_data = {}

        dependencies = {}
        dependencies.update(package_data.get("dependencies") or {})
        dependencies.update(package_data.get("devDependencies") or {})
        if any(name in dependencies for name in ("next", "nextjs")):
            return "Next.js"
        if "react" in dependencies:
            return "React"
        if "vue" in dependencies:
            return "Vue"
        if "angular" in dependencies or "@angular/core" in dependencies:
            return "Angular"
        if "express" in dependencies:
            return "Node.js / Express"
        if "tailwindcss" in dependencies:
            return "Tailwind CSS"
        if "vite" in dependencies:
            return "Vite / SPA"

    manifest_text = "\n".join(
        read_repo_file(file_map[name])
        for name in ("requirements.txt", "pyproject.toml", "pipfile")
        if name in file_map
    )
    if manifest_text:
        if re.search(r"\bdjango\b", manifest_text, re.IGNORECASE):
            return "Django"
        if re.search(r"\bfastapi\b", manifest_text, re.IGNORECASE):
            return "FastAPI"
        if re.search(r"\bflask\b", manifest_text, re.IGNORECASE):
            return "Flask"
        if re.search(r"\sstreamlit\b", manifest_text, re.IGNORECASE):
            return "Streamlit"
        if re.search(r"\bpytorch\b", manifest_text, re.IGNORECASE):
            return "PyTorch / ML"

    pubspec_entry = file_map.get("pubspec.yaml")
    if pubspec_entry:
        pubspec_text = read_repo_file(pubspec_entry).lower()
        if "flutter:" in pubspec_text:
            return "Flutter"

    if "django" in haystack:
        return "Django"
    if "streamlit" in haystack:
        return "Streamlit"
    if "flutter" in haystack:
        return "Flutter"
    if "fastapi" in haystack:
        return "FastAPI"
    if "flask" in haystack:
        return "Flask"
    if "react" in haystack:
        return "React"
    if "angular" in haystack:
        return "Angular"
    if "express" in haystack or "node.js" in haystack or "nodejs" in haystack:
        return "Node.js / Express"
    if "next.js" in haystack or "nextjs" in haystack:
        return "Next.js"
    if "php" in haystack:
        return "PHP / Laravel"
    if "html" in haystack and "css" in haystack:
        return "HTML / CSS"

    return "Other / custom"


def build_chart_url(title: str, labels: list[str], values: list[int]) -> str:
    config = {
        "type": "pie",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "data": values,
                    "backgroundColor": COLORS,
                    "borderColor": "#ffffff",
                    "borderWidth": 2,
                }
            ],
        },
        "options": {
            "plugins": {
                "legend": {"position": "bottom"},
                "title": {"display": True, "text": title},
            }
        },
    }
    encoded = quote(json.dumps(config, separators=(",", ":")))
    return f"https://quickchart.io/chart?format=svg&width=700&height=420&backgroundColor=white&c={encoded}"


def build_chart_section(language_labels: list[str], language_values: list[int], framework_labels: list[str], framework_values: list[int]) -> str:
    language_url = build_chart_url(
        "Primary Languages Across My Own GitHub Repos",
        language_labels,
        language_values,
    )
    framework_url = build_chart_url(
        "Framework / Stack Signals Across My Own GitHub Repos",
        framework_labels,
        framework_values,
    )

    return "\n".join(
        [
            MARKER_START,
            '<p align="center">',
            f'  <img src="{language_url}" width="48%" alt="Primary languages across my own GitHub repos" />',
            f'  <img src="{framework_url}" width="48%" alt="Framework and stack signals across my own GitHub repos" />',
            "</p>",
            "",
            '<p align="center"><sub>Charts are refreshed from GitHub profile data by a scheduled workflow.</sub></p>',
            MARKER_END,
        ]
    )


def update_readme() -> str:
    repos = fetch_json(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=updated")
    owned = [repo for repo in repos if not repo.get("fork") and not repo.get("archived")]

    language_counts = Counter(repo.get("language") or "Mixed / unknown" for repo in owned)

    framework_counts = Counter()
    for repo in owned:
        file_map = load_repo_contents(repo)
        framework_counts[detect_framework(repo, file_map)] += 1

    language_labels, language_values = zip(*language_counts.most_common())
    framework_labels, framework_values = zip(*framework_counts.most_common())

    section = build_chart_section(
        list(language_labels),
        list(language_values),
        list(framework_labels),
        list(framework_values),
    )

    readme_text = README_PATH.read_text(encoding="utf-8")
    if MARKER_START not in readme_text or MARKER_END not in readme_text:
        raise RuntimeError("Chart markers were not found in README.md")

    before, remainder = readme_text.split(MARKER_START, 1)
    _, after = remainder.split(MARKER_END, 1)
    updated = f"{before}{section}{after}"

    if updated != readme_text:
        README_PATH.write_text(updated, encoding="utf-8")

    return f"updated {len(owned)} owned repos, {len(language_counts)} language slices, {len(framework_counts)} framework slices"


if __name__ == "__main__":
    print(update_readme())
