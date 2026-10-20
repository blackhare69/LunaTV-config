#!/usr/bin/env python3
"""Idempotently merge the curated ziyuanzu overlay and rebuild LunaTV feeds."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "LunaTV-config.json"
OVERLAY = ROOT / "ziyuanzu-sources.json"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_api(value):
    return value.strip().rstrip("/").lower()


def base58(data):
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    leading_zeroes = len(data) - len(data.lstrip(b"\0"))
    return "1" * leading_zeroes + encoded


def main():
    config = read_json(CONFIG)
    overlay = read_json(OVERLAY)
    if not isinstance(config, dict) or not isinstance(config.get("api_site"), dict):
        raise SystemExit("LunaTV-config.json must contain an api_site object")
    if not isinstance(overlay, dict) or not overlay:
        raise SystemExit("ziyuanzu-sources.json must be a non-empty object")

    api_site = config["api_site"]
    known_apis = {
        normalize_api(item["api"])
        for item in api_site.values()
        if isinstance(item, dict) and isinstance(item.get("api"), str)
    }
    added = 0
    for key, item in overlay.items():
        if not isinstance(item, dict) or not all(
            isinstance(item.get(field), str) and item[field].strip()
            for field in ("name", "api", "detail")
        ):
            raise SystemExit(f"Invalid source entry: {key}")
        api = normalize_api(item["api"])
        if not item["api"].startswith(("http://", "https://")):
            raise SystemExit(f"Invalid API URL: {key}")
        if api in known_apis:
            continue
        if key in api_site:
            raise SystemExit(f"Refusing to replace existing config key: {key}")
        api_site[key] = item
        known_apis.add(api)
        added += 1

    config["api_site"] = api_site
    write_json(CONFIG, config)

    # Match the upstream builder's subscription rules.
    jingjian_sites = {
        key: item for key, item in api_site.items()
        if not item.get("_comment")
    }
    jingjian = {"cache_time": config["cache_time"], "api_site": jingjian_sites}
    jin18 = {
        "cache_time": config["cache_time"],
        "api_site": {
            key: item for key, item in jingjian_sites.items()
            if not item["name"].startswith("🔞")
        },
    }
    write_json(ROOT / "jingjian.json", jingjian)
    write_json(ROOT / "jin18.json", jin18)

    # Point the repository's own subscription entry points at this fork.
    worker_path = ROOT / "CORSAPI" / "_worker.js"
    if worker_path.exists():
        worker_text = worker_path.read_text(encoding="utf-8")
        worker_text = worker_text.replace(
            "raw.githubusercontent.com/hafrey1/LunaTV-config",
            "raw.githubusercontent.com/blackhare69/LunaTV-config",
        )
        worker_path.write_text(worker_text, encoding="utf-8")

    readme_path = ROOT / "README.md"
    if readme_path.exists():
        readme_text = readme_path.read_text(encoding="utf-8")
        readme_text = readme_text.replace(
            "raw.githubusercontent.com/hafrey1/LunaTV-config",
            "raw.githubusercontent.com/blackhare69/LunaTV-config",
        )
        count_lines = {
            "- **`source=jin18`**": (
                f"- **`source=jin18`** - 精简版（{len(jin18['api_site'])}个资源，仅普通内容）"
            ),
            "- **`source=jingjian`**": (
                f"- **`source=jingjian`** - 精简+成人版（{len(jingjian_sites)}个资源）"
            ),
            "- **`source=full`**": (
                f"- **`source=full`** - 完整版（{len(api_site)}个资源，**默认**）"
            ),
        }
        readme_lines = []
        for line in readme_text.splitlines():
            replacement = next(
                (value for prefix, value in count_lines.items() if line.startswith(prefix)),
                line,
            )
            readme_lines.append(replacement)
        readme_text = "\n".join(readme_lines) + "\n"

        note_marker = "<!-- fork-subscription-source-note -->"
        if note_marker not in readme_text:
            note = (
                note_marker + "\n"
                "> 本 fork 的 raw `.txt` 订阅直链使用当前仓库。若使用 CORSAPI 的 "
                "`?format=...` 订阅，请把本仓库更新后的 `CORSAPI/_worker.js` 部署到"
                "你自己的 Worker；GitHub 同步不会自动部署 Cloudflare Worker。"
            )
            anchor = "\n# 🌐 CORSAPI"
            if anchor in readme_text:
                readme_text = readme_text.replace(anchor, "\n\n" + note + anchor, 1)
            else:
                readme_text = readme_text.rstrip() + "\n\n" + note + "\n"
        readme_path.write_text(readme_text, encoding="utf-8")


    for source, target in (
        (CONFIG, ROOT / "LunaTV-config.txt"),
        (ROOT / "jingjian.json", ROOT / "jingjian.txt"),
        (ROOT / "jin18.json", ROOT / "jin18.txt"),
    ):
        target.write_text(base58(source.read_bytes()), encoding="ascii")

    print(
        f"Preserved {len(overlay)} overlay entries; added {added}; "
        f"full={len(api_site)}, jingjian={len(jingjian_sites)}, "
        f"jin18={len(jin18['api_site'])}"
    )


if __name__ == "__main__":
    main()
