#!/usr/bin/env python3
"""
Converte customizacoes do settings.json para o tema VS Code.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mescla customizacoes do settings.json em um arquivo de tema VS Code."
    )
    parser.add_argument(
        "--settings",
        required=True,
        help="Caminho para o settings.json de origem.",
    )
    parser.add_argument(
        "--theme",
        default=str(
            Path(__file__).resolve().parents[1]
            / "themes"
            / "cursor-style-by-kalleu-color-theme.json"
        ),
        help="Caminho do arquivo de tema de destino.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Nao cria backup antes de atualizar o tema.",
    )
    return parser.parse_args()


def load_jsonc(path: Path) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    content = strip_json_comments(content)
    content = strip_trailing_commas(content)
    return json.loads(content)


def strip_json_comments(raw: str) -> str:
    result: List[str] = []
    i = 0
    in_string = False
    escape = False
    length = len(raw)

    while i < length:
        ch = raw[i]

        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < length:
            nxt = raw[i + 1]
            if nxt == "/":
                i += 2
                while i < length and raw[i] not in ("\n", "\r"):
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < length and not (raw[i] == "*" and raw[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        result.append(ch)
        i += 1

    return "".join(result)


def strip_trailing_commas(raw: str) -> str:
    pattern = re.compile(r",(\s*[}\]])")
    while True:
        new_raw = pattern.sub(r"\1", raw)
        if new_raw == raw:
            return raw
        raw = new_raw


def rule_key(rule: Dict[str, Any]) -> Tuple[str, str]:
    scope = rule.get("scope", "")
    if isinstance(scope, list):
        scope_key = ",".join(sorted(str(item) for item in scope))
    else:
        scope_key = str(scope)
    name = str(rule.get("name", ""))
    return (scope_key, name)


def merge_textmate_rules(
    existing_rules: List[Dict[str, Any]], incoming_rules: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int]:
    merged = list(existing_rules)
    index_by_key = {rule_key(rule): idx for idx, rule in enumerate(merged)}
    replaced = 0

    for rule in incoming_rules:
        key = rule_key(rule)
        if key in index_by_key:
            merged[index_by_key[key]] = rule
            replaced += 1
        else:
            index_by_key[key] = len(merged)
            merged.append(rule)

    return merged, replaced


def deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def create_backup(path: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".bak.{ts}")
    shutil.copy2(path, backup_path)
    return backup_path


def main() -> int:
    args = parse_args()
    settings_path = Path(args.settings).expanduser().resolve()
    theme_path = Path(args.theme).expanduser().resolve()

    if not settings_path.is_file():
        print(f"[erro] settings.json nao encontrado: {settings_path}", file=sys.stderr)
        return 1

    if not theme_path.is_file():
        print(f"[erro] arquivo de tema nao encontrado: {theme_path}", file=sys.stderr)
        return 1

    try:
        settings_data = load_jsonc(settings_path)
    except json.JSONDecodeError as exc:
        print(f"[erro] settings.json invalido: {exc}", file=sys.stderr)
        return 1

    try:
        theme_data = json.loads(theme_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[erro] tema atual invalido: {exc}", file=sys.stderr)
        return 1

    color_customizations = settings_data.get("workbench.colorCustomizations", {})
    token_customizations = settings_data.get("editor.tokenColorCustomizations", {})
    semantic_customizations = settings_data.get(
        "editor.semanticTokenColorCustomizations", {}
    )

    if not isinstance(color_customizations, dict):
        print(
            "[erro] workbench.colorCustomizations precisa ser um objeto JSON.",
            file=sys.stderr,
        )
        return 1

    textmate_rules = token_customizations.get("textMateRules", [])
    if textmate_rules is None:
        textmate_rules = []
    if not isinstance(textmate_rules, list):
        print("[erro] textMateRules precisa ser uma lista.", file=sys.stderr)
        return 1

    if semantic_customizations and not isinstance(semantic_customizations, dict):
        print(
            "[erro] editor.semanticTokenColorCustomizations precisa ser um objeto JSON.",
            file=sys.stderr,
        )
        return 1

    theme_data.setdefault("colors", {})
    theme_data.setdefault("tokenColors", [])

    if not isinstance(theme_data["colors"], dict):
        print("[erro] tema.colors precisa ser um objeto JSON.", file=sys.stderr)
        return 1
    if not isinstance(theme_data["tokenColors"], list):
        print("[erro] tema.tokenColors precisa ser uma lista.", file=sys.stderr)
        return 1

    backup_path = None
    if not args.no_backup:
        backup_path = create_backup(theme_path)

    previous_color_count = len(theme_data["colors"])
    theme_data["colors"].update(color_customizations)
    added_or_updated_colors = len(color_customizations)
    final_color_count = len(theme_data["colors"])

    merged_rules, replaced_count = merge_textmate_rules(
        theme_data["tokenColors"], textmate_rules
    )
    theme_data["tokenColors"] = merged_rules
    appended_count = max(len(textmate_rules) - replaced_count, 0)

    semantic_updates = 0
    if semantic_customizations:
        theme_data.setdefault("semanticTokenColors", {})
        if not isinstance(theme_data["semanticTokenColors"], dict):
            print(
                "[erro] tema.semanticTokenColors precisa ser um objeto JSON.",
                file=sys.stderr,
            )
            return 1
        incoming_semantic = semantic_customizations.get("rules")
        if isinstance(incoming_semantic, dict):
            semantic_updates = len(incoming_semantic)
            deep_merge(theme_data["semanticTokenColors"], incoming_semantic)
        elif isinstance(semantic_customizations, dict):
            filtered_semantic = {
                key: value
                for key, value in semantic_customizations.items()
                if key not in {"enabled"}
            }
            semantic_updates = len(filtered_semantic)
            deep_merge(theme_data["semanticTokenColors"], filtered_semantic)

    json.dumps(theme_data)
    theme_path.write_text(
        json.dumps(theme_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("[ok] Tema atualizado com sucesso.")
    print(f"[resumo] Arquivo de tema: {theme_path}")
    if backup_path:
        print(f"[resumo] Backup criado: {backup_path}")
    print(
        "[resumo] Colors: "
        f"{previous_color_count} -> {final_color_count} "
        f"(entrada: {added_or_updated_colors})"
    )
    print(
        "[resumo] Token rules (textMate): "
        f"regras recebidas={len(textmate_rules)}, substituidas={replaced_count}, adicionadas={appended_count}"
    )
    print(f"[resumo] Semantic tokens atualizados: {semantic_updates}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
