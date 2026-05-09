import re


_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def contains_chinese(text):
    return bool(_CHINESE_RE.search(text or ""))


def sanitize_identifier(text):
    normalized = (text or "").strip()
    parts = re.split(r"[^a-zA-Z0-9]+", normalized)
    parts = [part for part in parts if part]

    if not parts:
        return ""

    first_part = parts[0].lower()
    remaining_parts = [part[:1].upper() + part[1:].lower() for part in parts[1:]]
    return first_part + "".join(remaining_parts)


def build_sequential_names(activity_type, model_name, count, existing_names, suffix=""):
    names = []
    taken_names = set(existing_names or set())
    serial_number = 1
    suffix = sanitize_identifier(suffix)

    while len(names) < count:
        if suffix:
            candidate = f"mesh_{activity_type}_{model_name}_{suffix}{serial_number:02d}"
        else:
            candidate = f"mesh_{activity_type}_{model_name}{serial_number:02d}"
        if candidate not in taken_names:
            names.append(candidate)
            taken_names.add(candidate)
        serial_number += 1

    return names
