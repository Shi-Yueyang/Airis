#!/usr/bin/env python3
"""Standalone Ark app package helpers (stdlib only; no arkbd imports)."""

from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path
from typing import Any

APP_PACKAGE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
IDENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
FIELD_TYPES = {
    "text",
    "long_text",
    "number",
    "money",
    "boolean",
    "date",
    "datetime",
    "enum",
    "multi_enum",
    "user",
    "department",
    "attachment",
    "link",
    "status",
    "priority",
    "tags",
    "summary",
    "body",
    "metric",
    "dimension",
    "time_dimension",
    "reference",
    "json",
}
CHAT_EMPTY_ICON_KEYS = {
    "code",
    "folder",
    "bug",
    "rocket",
    "search",
    "file",
    "chart",
    "line",
    "read",
    "book",
    "bolt",
}
OPENCODE_OPTIONAL_DIRS = {"commands", "agents", "modes", "plugins", "skills", "tools"}
DEFAULT_USER_CONFIG_SEED_DIR = ".ark-user-config-defaults"
# Package-root allowlist aligned with opencode_offline_app_package_guide.md (+ data_schema sync file).
PACKAGE_ROOT_FILES = {"manifest.json", "data_schema.json"}
PACKAGE_ROOT_DIRS = {".opencode"}
OPENCODE_STRIP_FILES = {"package.json", "package-lock.json", "bun.lock"}
# Skills that live in the source tree for standalone development but must never
# ship inside the .opapp.tgz (they re-implement the packaging toolchain itself).
DEV_ONLY_SKILLS = {"package-and-validate"}
STRIP_HINTS = ("node_modules", "package-lock.json", "bun.lock", "package.json")
SYSTEM_FIELD_IDS = {"id", "record_version", "created_at", "updated_at", "created_by", "updated_by"}
UI_COMPONENT_TYPES = {
    "data_table",
    "record_form",
    "record_detail",
    "related_records",
    "metric_card",
    "basic_chart",
}
UI_COMPONENTS_REQUIRING_BINDING = {
    "data_table",
    "record_form",
    "record_detail",
    "related_records",
    "metric_card",
    "basic_chart",
}
UI_COMPONENT_FIELD_COLLECTION = {
    "data_table": "columns",
    "record_form": "fields",
    "record_detail": "fields",
    "related_records": "columns",
}
WORKBENCH_CAPS = {"read", "create", "update", "delete", "export"}
SUPPORTED_A2A_MODES = {"text", "file", "data"}


def _a2a_issue(code: str, path: str) -> dict[str, str]:
    return {"code": code, "path": path}


def load_manifest(package_root: Path) -> dict[str, Any]:
    path = package_root / "manifest.json"
    if not path.is_file():
        raise ValueError("安装包缺少 manifest.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"manifest.json 格式错误: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("manifest.json 格式错误")
    return data


def validate_chat_empty_state(raw: Any) -> list[str]:
    errors: list[str] = []
    if raw is None:
        return errors
    if not isinstance(raw, dict):
        return ["chat_empty_state 必须是对象"]
    cards = raw.get("cards")
    if cards is None:
        return errors
    if not isinstance(cards, list):
        return ["chat_empty_state.cards 必须是数组"]
    if len(cards) > 4:
        errors.append("chat_empty_state.cards 最多 4 条")
    for idx, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"cards[{idx}] 必须是对象")
            continue
        if not str(card.get("title") or "").strip():
            errors.append(f"cards[{idx}].title 必填")
        if not str(card.get("prompt") or "").strip():
            errors.append(f"cards[{idx}].prompt 必填")
        icon = str(card.get("icon") or "code").strip()
        if icon and icon not in CHAT_EMPTY_ICON_KEYS:
            errors.append(f"cards[{idx}].icon 不合法")
    return errors


def validate_agent_ui(raw: Any) -> list[str]:
    """Validate the standalone shape of optional manifest.agent_ui settings."""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ["manifest.agent_ui must be an object"]

    errors: list[str] = []
    visible = raw.get("visible")
    if "visible" in raw:
        if not isinstance(visible, list):
            errors.append("manifest.agent_ui.visible must be an array")
        else:
            seen: set[str] = set()
            for name in visible:
                if not isinstance(name, str) or not name.strip():
                    errors.append("manifest.agent_ui.visible entries must be non-empty strings")
                    continue
                if name in seen:
                    errors.append(f"manifest.agent_ui.visible contains duplicate Agent name '{name}'")
                    continue
                seen.add(name)

    labels = raw.get("labels")
    if "labels" in raw:
        if not isinstance(labels, dict):
            errors.append("manifest.agent_ui.labels must be an object")
        else:
            for name, value in labels.items():
                if not isinstance(name, str) or not name.strip():
                    errors.append("manifest.agent_ui.labels keys must be non-empty strings")
                    continue
                if not isinstance(value, dict):
                    errors.append(f"manifest.agent_ui.labels.{name} must be an object")
                    continue
                for locale, label in value.items():
                    if (
                        not isinstance(locale, str)
                        or not locale.strip()
                        or not isinstance(label, str)
                        or not label.strip()
                    ):
                        errors.append(
                            f"manifest.agent_ui.labels.{name} values must be non-empty string labels"
                        )
    return errors


def validate_a2a_config(raw: Any) -> list[dict[str, str]]:
    """Validate optional manifest.a2a without importing the Ark backend.

    The standalone result deliberately carries the platform's stable codes and
    JSON paths, allowing developers to resolve package errors before upload.
    Agent visibility is platform-owned and therefore is not checked here.
    """
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return [_a2a_issue("A2A_INVALID_TYPE", "a2a")]

    errors: list[dict[str, str]] = []
    exposed = raw.get("exposed", False)
    if not isinstance(exposed, bool):
        errors.append(_a2a_issue("A2A_INVALID_TYPE", "a2a.exposed"))
        exposed = False
    if exposed and (not isinstance(raw.get("name"), str) or not raw["name"].strip()):
        errors.append(_a2a_issue("A2A_NAME_REQUIRED", "a2a.name"))
    if exposed and (
        not isinstance(raw.get("description"), str) or not raw["description"].strip()
    ):
        errors.append(_a2a_issue("A2A_DESCRIPTION_REQUIRED", "a2a.description"))

    skills = raw.get("skills")
    if exposed and (not isinstance(skills, list) or not skills):
        errors.append(_a2a_issue("A2A_SKILLS_REQUIRED", "a2a.skills"))
        skills = []
    elif skills is not None and not isinstance(skills, list):
        errors.append(_a2a_issue("A2A_INVALID_TYPE", "a2a.skills"))
        skills = []
    elif skills is None:
        skills = []

    seen_skill_ids: set[str] = set()
    for index, skill in enumerate(skills):
        path = f"a2a.skills[{index}]"
        if not isinstance(skill, dict):
            errors.append(_a2a_issue("A2A_INVALID_TYPE", path))
            continue
        skill_id = skill.get("id").strip() if isinstance(skill.get("id"), str) else ""
        if (exposed or "id" in skill) and not skill_id:
            errors.append(_a2a_issue("A2A_SKILL_ID_REQUIRED", f"{path}.id"))
        elif skill_id in seen_skill_ids:
            errors.append(_a2a_issue("A2A_SKILL_ID_DUPLICATE", f"{path}.id"))
        if skill_id:
            seen_skill_ids.add(skill_id)
        for key in ("name", "description"):
            if (exposed or key in skill) and (
                not isinstance(skill.get(key), str) or not skill[key].strip()
            ):
                errors.append(_a2a_issue("A2A_INVALID_TYPE", f"{path}.{key}"))
        for key in ("input_modes", "output_modes"):
            modes = skill.get(key)
            if modes is None and not exposed:
                continue
            if not isinstance(modes, list) or not modes or any(
                not isinstance(mode, str) or mode not in SUPPORTED_A2A_MODES
                for mode in modes
            ):
                errors.append(_a2a_issue("A2A_MODE_UNSUPPORTED", f"{path}.{key}"))
    return errors


def validate_user_config(package_root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    raw = manifest.get("user_config")
    if not isinstance(raw, dict) or not raw.get("enabled"):
        return errors
    seed_dir_name = raw.get("seed_dir")
    if not isinstance(seed_dir_name, str) or not seed_dir_name.strip():
        seed_dir_name = DEFAULT_USER_CONFIG_SEED_DIR
    else:
        seed_dir_name = seed_dir_name.strip().replace("\\", "/").strip("/")
    seed_path = package_root / seed_dir_name
    if not seed_path.is_dir():
        errors.append(f"user_config.enabled 时缺少目录: {seed_dir_name}")
        return errors
    targets = raw.get("mcp_targets")
    if not isinstance(targets, list):
        return errors
    seen: set[str] = set()
    for item in targets:
        if not isinstance(item, dict):
            continue
        mcp_name = str(item.get("mcp_name") or "").strip()
        if not mcp_name:
            errors.append("mcp_targets.mcp_name 不能为空")
            continue
        if mcp_name in seen:
            errors.append(f"mcp_targets 重复: {mcp_name}")
        seen.add(mcp_name)
        seed_subdir = str(item.get("seed_subdir") or "").strip() or mcp_name
        seed_subdir = seed_subdir.replace("\\", "/").strip("/")
        if not (seed_path / seed_subdir).exists():
            errors.append(f"mcp_targets seed 子目录不存在: {seed_subdir}")
    return errors


def validate_listing(manifest: dict[str, Any]) -> list[str]:
    """Submit-oriented listing checks (blocking for import-ready claims)."""
    errors: list[str] = []
    listing = manifest.get("listing") if isinstance(manifest.get("listing"), dict) else {}
    name = str(listing.get("name") or manifest.get("name") or "").strip()
    if len(name) < 2 or len(name) > 40:
        errors.append("Listing name 需为 2-40 字（manifest.name 或 listing.name）")
    subtitle = str(listing.get("subtitle") or "").strip()
    if not subtitle or len(subtitle) > 120:
        errors.append("Listing subtitle 必填且不超过 120 字")
    desc = str(listing.get("description_md") or manifest.get("description") or "").strip()
    if len(desc) < 100:
        errors.append("Listing description_md 需不少于 100 字")
    if not str(listing.get("category") or "").strip():
        errors.append("Listing category 必填")
    if not str(listing.get("support_contact") or "").strip():
        errors.append("Listing support_contact 必填")
    return errors


def _require_ident(value: str, path: str, errors: list[str]) -> None:
    if not IDENT_RE.fullmatch(value):
        errors.append(f"{path} 须匹配 ^[A-Za-z][A-Za-z0-9_]{{0,63}}$: {value}")


def validate_data_schema_shape(schema: Any, *, path: str = "data_schema") -> list[str]:
    errors: list[str] = []
    if schema is None:
        return errors
    if not isinstance(schema, dict):
        return [f"{path} 必须是对象"]
    version = schema.get("version")
    if version not in (None, "app-data-schema.v1"):
        errors.append(f"{path}.version 应为 app-data-schema.v1")
    sources = schema.get("data_sources")
    if sources is None:
        return errors
    if not isinstance(sources, list):
        return [f"{path}.data_sources 必须是数组"]
    seen_source_ids: set[str] = set()
    seen_stable_sources: set[str] = set()
    for si, source in enumerate(sources):
        sp = f"{path}.data_sources[{si}]"
        if not isinstance(source, dict):
            errors.append(f"{sp} 必须是对象")
            continue
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            errors.append(f"{sp}.source_id 必填")
        else:
            _require_ident(source_id, f"{sp}.source_id", errors)
            if source_id in seen_source_ids:
                errors.append(f"{sp}.source_id 重复: {source_id}")
            seen_source_ids.add(source_id)
        stable_source = str(source.get("stable_source_id") or source_id).strip()
        if not stable_source:
            errors.append(f"{sp}.stable_source_id 必填（可与 source_id 相同）")
        else:
            _require_ident(stable_source, f"{sp}.stable_source_id", errors)
            if stable_source in seen_stable_sources:
                errors.append(f"{sp}.stable_source_id 重复: {stable_source}")
            seen_stable_sources.add(stable_source)
        source_type = str(source.get("source_type") or "internal").strip()
        tables = source.get("tables") or []
        if not isinstance(tables, list):
            errors.append(f"{sp}.tables 必须是数组")
            continue
        seen_table_keys: set[str] = set()
        seen_stable_tables: set[str] = set()
        for ti, table in enumerate(tables):
            tp = f"{sp}.tables[{ti}]"
            if not isinstance(table, dict):
                errors.append(f"{tp} 必须是对象")
                continue
            table_key = str(table.get("table_key") or "").strip()
            if not table_key:
                errors.append(f"{tp}.table_key 必填")
            else:
                _require_ident(table_key, f"{tp}.table_key", errors)
                if table_key in seen_table_keys:
                    errors.append(f"{tp}.table_key 重复: {table_key}")
                seen_table_keys.add(table_key)
            stable_table = str(table.get("stable_table_id") or table_key).strip()
            if not stable_table:
                errors.append(f"{tp}.stable_table_id 必填（可与 table_key 相同）")
            else:
                _require_ident(stable_table, f"{tp}.stable_table_id", errors)
                if stable_table in seen_stable_tables:
                    errors.append(f"{tp}.stable_table_id 重复: {stable_table}")
                seen_stable_tables.add(stable_table)
            view_config = table.get("view_config") if isinstance(table.get("view_config"), dict) else {}
            caps = ((view_config.get("capabilities") or {}).get("workbench") if isinstance(view_config.get("capabilities"), dict) else None)
            if isinstance(caps, dict):
                for key in caps:
                    if key not in WORKBENCH_CAPS:
                        errors.append(f"{tp}.view_config.capabilities.workbench 未知能力: {key}")
            fields = table.get("fields") or []
            if not isinstance(fields, list):
                errors.append(f"{tp}.fields 必须是数组")
                continue
            seen_field_keys: set[str] = set()
            seen_stable_fields: set[str] = set()
            for fi, field in enumerate(fields):
                fp = f"{tp}.fields[{fi}]"
                if not isinstance(field, dict):
                    errors.append(f"{fp} 必须是对象")
                    continue
                field_key = str(field.get("field_key") or "").strip()
                if not field_key:
                    errors.append(f"{fp}.field_key 必填")
                else:
                    _require_ident(field_key, f"{fp}.field_key", errors)
                    if field_key in seen_field_keys:
                        errors.append(f"{fp}.field_key 重复: {field_key}")
                    seen_field_keys.add(field_key)
                if field_key in SYSTEM_FIELD_IDS:
                    errors.append(f"{fp} 不可定义系统字段 {field_key}")
                stable_field = str(field.get("stable_field_id") or field_key).strip()
                if not stable_field:
                    errors.append(f"{fp}.stable_field_id 必填（可与 field_key 相同）")
                else:
                    _require_ident(stable_field, f"{fp}.stable_field_id", errors)
                    if stable_field in seen_stable_fields:
                        errors.append(f"{fp}.stable_field_id 重复: {stable_field}")
                    seen_stable_fields.add(stable_field)
                ftype = str(field.get("type") or "").strip()
                if ftype and ftype not in FIELD_TYPES:
                    errors.append(f"{fp}.type 不支持: {ftype}")
                if ftype == "enum":
                    enum_values = field.get("enum_values")
                    if not isinstance(enum_values, list) or not enum_values:
                        errors.append(f"{fp}.enum_values 对 enum 必填且非空")
                for flag in ("workbench_readable", "workbench_writable"):
                    if flag in field and not isinstance(field.get(flag), bool):
                        errors.append(f"{fp}.{flag} 必须是布尔")
                if field.get("workbench_writable") is True and field.get("workbench_readable") is False:
                    errors.append(f"{fp} workbench_writable 时必须 workbench_readable")
                write_privilege = str(field.get("write_privilege") or "standard").strip().lower() or "standard"
                if write_privilege not in {"standard", "elevated"}:
                    errors.append(f"{fp}.write_privilege 不支持: {field.get('write_privilege')}")
                workbench_create = bool(caps.get("create")) if isinstance(caps, dict) else False
                required = field.get("required") is True
                if write_privilege == "elevated" and required and field.get("default_value") is None and workbench_create:
                    errors.append(f"{fp} elevated 必填字段在开放 create 时必须提供 default_value")
                default_value = field.get("default_value")
                if default_value is not None and not isinstance(default_value, str):
                    errors.append(
                        f"{fp}.default_value 必须是字符串（数字/布尔请写成 \"0\" / \"false\"，不要用裸 0/false）"
                    )
        if source_type == "external":
            pass
    return errors


def _build_data_catalog(manifest: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    data_schema = manifest.get("data_schema")
    if not isinstance(data_schema, dict):
        errors.append("工作台需要 manifest.data_schema")
        return {}
    catalog: dict[str, dict[str, Any]] = {}
    for source in data_schema.get("data_sources") or []:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("stable_source_id") or "").strip()
        if not source_id:
            continue
        tables: dict[str, Any] = {}
        for table in source.get("tables") or []:
            if not isinstance(table, dict):
                continue
            stable_table_id = str(table.get("stable_table_id") or "").strip()
            if not stable_table_id:
                continue
            fields: dict[str, Any] = {}
            for field in table.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                stable_field_id = str(field.get("stable_field_id") or "").strip()
                if stable_field_id:
                    fields[stable_field_id] = field
            tables[stable_table_id] = {"source": source, "table": table, "fields": fields}
        catalog[source_id] = tables
    return catalog


def _resolve_ui_binding(
    component: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    path: str,
    errors: list[str],
) -> dict[str, Any] | None:
    binding = component.get("binding")
    if not isinstance(binding, dict):
        errors.append(f"{path}.binding 必填")
        return None
    source_id = str(binding.get("stable_source_id") or "").strip()
    table_id = str(binding.get("stable_table_id") or "").strip()
    if not source_id:
        errors.append(f"{path}.binding.stable_source_id 必填")
        return None
    if not table_id:
        errors.append(f"{path}.binding.stable_table_id 必填")
        return None
    source_tables = catalog.get(source_id)
    if source_tables is None:
        errors.append(f"{path}.binding.stable_source_id 不存在: {source_id}")
        return None
    resolved = source_tables.get(table_id)
    if resolved is None:
        errors.append(f"{path}.binding.stable_table_id 不存在: {table_id}")
        return None
    if str(resolved["source"].get("source_type") or "internal") != "internal":
        errors.append(f"{path}.binding 工作台仅支持 internal 数据源")
        return None
    return resolved


def _validate_ui_component_fields(
    component: dict[str, Any],
    resolved: dict[str, Any] | None,
    path: str,
    errors: list[str],
) -> None:
    if resolved is None:
        return
    ctype = str(component.get("type") or "").strip()
    collection = UI_COMPONENT_FIELD_COLLECTION.get(ctype)
    if not collection:
        return
    items = component.get(collection)
    if not isinstance(items, list) or not items:
        errors.append(f"{path}.{collection} 至少需要一项")
        return
    for index, item in enumerate(items):
        ip = f"{path}.{collection}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{ip} 必须是对象")
            continue
        stable_field_id = item.get("stable_field_id")
        system_field_id = item.get("system_field_id")
        has_stable = isinstance(stable_field_id, str) and bool(stable_field_id.strip())
        has_system = isinstance(system_field_id, str) and bool(system_field_id.strip())
        if has_stable == has_system:
            errors.append(f"{ip} 业务字段与系统字段必须二选一")
            continue
        if has_stable:
            field = resolved["fields"].get(str(stable_field_id).strip())
            if not field:
                errors.append(f"{ip} 稳定字段不存在: {stable_field_id}")
                continue
            if not field.get("workbench_readable", False):
                errors.append(f"{ip} 字段未授予 workbench_readable")
            if ctype == "record_form" and not item.get("read_only", False) and not field.get("workbench_writable", False):
                errors.append(f"{ip} 表单字段未授予 workbench_writable")
        elif str(system_field_id).strip() not in SYSTEM_FIELD_IDS:
            errors.append(f"{ip} 系统字段不存在: {system_field_id}")
        elif ctype == "record_form" and not item.get("read_only", False):
            errors.append(f"{ip} 系统字段不能作为可写表单字段")


def validate_ui_schema_shape(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = manifest.get("ui_schema")
    if schema is None:
        return errors
    if not isinstance(schema, dict):
        return ["ui_schema 必须是对象"]
    if not schema.get("enabled"):
        return errors
    if schema.get("version") != "app-ui-schema.v1":
        errors.append("ui_schema.version 必须为 app-ui-schema.v1")
    if schema.get("renderer") != "managed_data_workbench":
        errors.append("ui_schema.renderer 必须为 managed_data_workbench")
    pages = schema.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("启用工作台时至少需要一个页面")
        return errors
    catalog = _build_data_catalog(manifest, errors)
    page_ids: set[str] = set()
    component_ids: set[str] = set()
    for pi, page in enumerate(pages):
        pp = f"ui_schema.pages[{pi}]"
        if not isinstance(page, dict):
            errors.append(f"{pp} 必须是对象")
            continue
        page_id = str(page.get("id") or "").strip()
        if not page_id:
            errors.append(f"{pp}.id 必填")
        elif page_id in page_ids:
            errors.append(f"{pp}.id 重复: {page_id}")
        else:
            page_ids.add(page_id)
        path = page.get("path")
        if not isinstance(path, str) or not path or path.startswith("/") or "//" in path or "?" in path or "#" in path:
            errors.append(f"{pp}.path 必须是非空应用内相对路径")
        components = page.get("components")
        if not isinstance(components, list) or not components:
            errors.append(f"{pp}.components 至少需要一个组件")
            continue
        for ci, component in enumerate(components):
            cp = f"{pp}.components[{ci}]"
            if not isinstance(component, dict):
                errors.append(f"{cp} 必须是对象")
                continue
            cid = str(component.get("id") or "").strip()
            if not cid:
                errors.append(f"{cp}.id 必填")
            elif cid in component_ids:
                errors.append(f"{cp}.id 重复: {cid}")
            else:
                component_ids.add(cid)
            ctype = str(component.get("type") or "").strip()
            if not ctype:
                errors.append(f"{cp}.type 必填")
            elif ctype not in UI_COMPONENT_TYPES:
                errors.append(f"{cp}.type 不支持: {ctype}")
            resolved = None
            if ctype in UI_COMPONENTS_REQUIRING_BINDING:
                resolved = _resolve_ui_binding(component, catalog, cp, errors)
            _validate_ui_component_fields(component, resolved, cp, errors)
    for pi, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        for ci, component in enumerate(page.get("components") or []):
            if not isinstance(component, dict):
                continue
            for ai, action in enumerate(component.get("actions") or []):
                if not isinstance(action, dict):
                    continue
                target = action.get("target")
                if target and str(target) not in component_ids:
                    errors.append(
                        f"ui_schema.pages[{pi}].components[{ci}].actions[{ai}].target 不存在: {target}"
                    )
    nav = schema.get("navigation") if isinstance(schema.get("navigation"), dict) else {}
    default_page = nav.get("default_page")
    if default_page and str(default_page) not in page_ids:
        errors.append("ui_schema.navigation.default_page 不存在")
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    if entrypoints.get("default") == "workbench" and not schema.get("enabled"):
        errors.append("entrypoints.default=workbench 但 ui_schema.enabled 未开启")
    return errors


def collect_skill_mcp_server_names(package_root: Path) -> set[str]:
    names: set[str] = set()
    skills_root = package_root / ".opencode" / "skills"
    if not skills_root.is_dir():
        return names
    for skill_dir in skills_root.iterdir():
        if not skill_dir.is_dir():
            continue
        mcp_path = skill_dir / "mcp.json"
        if not mcp_path.is_file():
            continue
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            names.update(str(k) for k in servers.keys())
    return names


def validate_skill_mcp_json(package_root: Path) -> tuple[list[str], list[str]]:
    """Errors/warnings for oh-my-openagent skill mcp.json shape."""
    errors: list[str] = []
    warnings: list[str] = []
    skills_root = package_root / ".opencode" / "skills"
    if not skills_root.is_dir():
        return errors, warnings
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        mcp_path = skill_dir / "mcp.json"
        if not mcp_path.is_file():
            continue
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{mcp_path.relative_to(package_root).as_posix()} 无法解析: {exc}")
            continue
        if not isinstance(data, dict) or "mcpServers" not in data:
            errors.append(
                f"{mcp_path.relative_to(package_root).as_posix()} 必须包含顶层 mcpServers（oh-my-openagent）"
            )
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or not servers:
            errors.append(f"{mcp_path.relative_to(package_root).as_posix()} mcpServers 不能为空")
            continue
        for name, conf in servers.items():
            if not isinstance(conf, dict):
                errors.append(f"mcpServers.{name} 必须是对象")
                continue
            if not str(conf.get("type") or "").strip():
                errors.append(f"mcpServers.{name}.type 必填")
            if conf.get("type") in {"http", "remote"} and not str(conf.get("url") or "").strip():
                errors.append(f"mcpServers.{name}.url 必填（HTTP MCP）")
    return errors, warnings


def scan_opencode_plugin(package_root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    path = package_root / ".opencode" / "opencode.json"
    has_skill_mcp = any(
        (package_root / ".opencode" / "skills").glob("*/mcp.json")
    ) if (package_root / ".opencode" / "skills").is_dir() else False
    if not path.is_file():
        if has_skill_mcp:
            errors.append("存在 skills/*/mcp.json 但缺少 .opencode/opencode.json（需 plugin: oh-my-openagent）")
        return errors, warnings
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("opencode.json 无法解析")
        return errors, warnings
    if not isinstance(config, dict):
        return errors, warnings
    plugin = config.get("plugin")
    plugins = plugin if isinstance(plugin, list) else []
    if has_skill_mcp and not any("oh-my-openagent" in str(p) for p in plugins):
        errors.append("存在 skills/*/mcp.json 但 opencode.json plugin 未声明 oh-my-openagent")
    if isinstance(config.get("mcp"), dict) and config["mcp"]:
        errors.append(
            "opencode.json 声明了非空 mcp；oh-my-openagent 技能主路径必须使用 skills/*/mcp.json 的 mcpServers"
        )
    return errors, warnings


def validate_mcp_target_alignment(package_root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    user_config = manifest.get("user_config")
    if not isinstance(user_config, dict) or not user_config.get("enabled"):
        return errors
    targets = user_config.get("mcp_targets")
    if not isinstance(targets, list) or not targets:
        return errors
    server_names = collect_skill_mcp_server_names(package_root)
    if not server_names:
        errors.append("user_config.enabled 且声明了 mcp_targets，但未找到任何 skills/*/mcp.json 的 mcpServers")
        return errors
    for item in targets:
        if not isinstance(item, dict):
            continue
        mcp_name = str(item.get("mcp_name") or "").strip()
        if mcp_name and mcp_name not in server_names:
            errors.append(
                f"mcp_targets.mcp_name={mcp_name} 未出现在任何 skills/*/mcp.json 的 mcpServers keys 中"
            )
    return errors


def validate_package_root(package_root: Path, *, expected_app_id: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if (package_root / ".casco").exists():
        warnings.append("包内包含已废弃的 .casco 目录，建议移除")
    try:
        manifest = load_manifest(package_root)
    except ValueError as exc:
        return {
            "valid": False,
            "errors": [str(exc)],
            "warnings": warnings,
            "manifest": {},
            "checklist": {"has_manifest": False, "has_opencode": (package_root / ".opencode").is_dir()},
        }

    app_id = str(manifest.get("app_id") or "").strip()
    if not app_id:
        errors.append("manifest.app_id 必填")
    elif app_id == "default":
        errors.append("目标 app_id 不能为 default")
    if expected_app_id and app_id != expected_app_id:
        errors.append(f"manifest.app_id 与期望不一致: {app_id}")
    version = str(manifest.get("version") or "").strip()
    if not version:
        errors.append("manifest.version 必填")
    elif not APP_PACKAGE_VERSION_RE.fullmatch(version):
        errors.append("版本号不合法")
    elif not re.fullmatch(r"^\d+\.\d+\.\d+$", version):
        warnings.append("version 建议使用生产形态 MAJOR.MINOR.PATCH")

    opencode_dir = package_root / ".opencode"
    if not opencode_dir.is_dir():
        errors.append("缺少运行配置目录 .opencode")
    else:
        for hint in STRIP_HINTS:
            if (opencode_dir / hint).exists() and hint == "node_modules":
                warnings.append(".opencode/node_modules 不应打进包（构建脚本会跳过）")

    errors.extend(validate_chat_empty_state(manifest.get("chat_empty_state")))
    errors.extend(validate_agent_ui(manifest.get("agent_ui")))
    a2a_errors = validate_a2a_config(manifest.get("a2a"))
    errors.extend(f"{issue['code']}: {issue['path']}" for issue in a2a_errors)
    errors.extend(validate_user_config(package_root, manifest))
    errors.extend(validate_listing(manifest))
    errors.extend(validate_data_schema_shape(manifest.get("data_schema")))
    errors.extend(validate_ui_schema_shape(manifest))

    data_schema = manifest.get("data_schema")
    if isinstance(data_schema, dict) and data_schema:
        copy_path = package_root / "data_schema.json"
        if copy_path.is_file():
            try:
                disk = json.loads(copy_path.read_text(encoding="utf-8"))
                if disk != data_schema:
                    errors.append("data_schema.json is out of sync with manifest.data_schema")
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"data_schema.json unreadable: {exc}")
        else:
            errors.append("manifest.data_schema 存在时必须同步写入 data_schema.json")

    mcp_errors, mcp_warnings = validate_skill_mcp_json(package_root)
    errors.extend(mcp_errors)
    warnings.extend(mcp_warnings)
    plugin_errors, plugin_warnings = scan_opencode_plugin(package_root)
    errors.extend(plugin_errors)
    warnings.extend(plugin_warnings)
    errors.extend(validate_mcp_target_alignment(package_root, manifest))

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "manifest": manifest,
        "checklist": {
            "has_opencode": opencode_dir.is_dir(),
            "has_manifest": True,
            "agent_ui": manifest.get("agent_ui"),
            "a2a": None
            if manifest.get("a2a") is None
            else {"valid": not a2a_errors, "errors": [issue["code"] for issue in a2a_errors]},
            "user_config": manifest.get("user_config"),
            "engine": "airis-standalone",
        },
    }


def _is_empty_directory(path: Path) -> bool:
    if not path.is_dir():
        return False
    return not any(p.is_file() for p in path.rglob("*"))


def _user_config_seed_dir_name(source_dir: Path) -> str:
    try:
        manifest = load_manifest(source_dir)
    except ValueError:
        return DEFAULT_USER_CONFIG_SEED_DIR
    user_config = manifest.get("user_config")
    if not isinstance(user_config, dict):
        return DEFAULT_USER_CONFIG_SEED_DIR
    raw = str(user_config.get("seed_dir") or DEFAULT_USER_CONFIG_SEED_DIR).strip().replace("\\", "/")
    name = raw.strip("/")
    if not name or "/" in name or name in {".", ".."}:
        return DEFAULT_USER_CONFIG_SEED_DIR
    return name


def _is_packaged_relpath(source_dir: Path, rel: str) -> bool:
    """Only ship package-contract paths; ignore fixtures/docs/etc. without a growing blacklist."""
    parts = [p for p in rel.split("/") if p]
    if not parts:
        return False
    if any(p == "__pycache__" or p.endswith(".pyc") for p in parts):
        return False

    root = parts[0]
    seed_dir = _user_config_seed_dir_name(source_dir)
    allowed_roots = PACKAGE_ROOT_DIRS | {seed_dir}

    if len(parts) == 1:
        return root in PACKAGE_ROOT_FILES

    if root not in allowed_roots:
        return False

    if root == ".opencode":
        if parts[1] == "node_modules":
            return False
        if len(parts) >= 3 and parts[1] == "skills" and parts[2] in DEV_ONLY_SKILLS:
            return False
        if len(parts) == 2 and parts[1] in OPENCODE_STRIP_FILES:
            return False
        if len(parts) >= 2 and parts[1] in OPENCODE_OPTIONAL_DIRS:
            optional_dir = source_dir / ".opencode" / parts[1]
            if _is_empty_directory(optional_dir):
                return False
    return True


def build_tgz_from_directory(source_dir: Path, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_file, "w:gz") as tar:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(source_dir).as_posix()
            if not _is_packaged_relpath(source_dir, rel):
                continue
            tar.add(path, arcname=rel)
