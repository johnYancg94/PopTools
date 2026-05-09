import re


def _clean_name(value):
    return (value or "").replace(".", "_")


def resolve_export_mesh_name(original_obj):
    data_name = getattr(getattr(original_obj, "data", None), "name", "")
    if data_name:
        return _clean_name(data_name)
    return _clean_name(getattr(original_obj, "name", ""))


def build_export_identity(original_obj):
    clean_name = resolve_export_mesh_name(original_obj)
    return {
        "object_name": clean_name,
        "file_stem": clean_name,
        "sync_mesh_data_name": False,
    }


def build_obj_export_options(export_filepath, global_scale, forward_axis, up_axis, export_materials):
    return {
        "filepath": export_filepath,
        "export_selected_objects": True,
        "global_scale": global_scale,
        "forward_axis": forward_axis,
        "up_axis": up_axis,
        "export_materials": export_materials,
        "path_mode": "COPY",
        "export_normals": True,
        "export_smooth_groups": True,
        "export_object_groups": True,
        "export_material_groups": bool(export_materials),
        "apply_modifiers": False,
        "export_triangulated_mesh": False,
    }


def rewrite_obj_group_name(obj_text, desired_name):
    desired_name = desired_name or ""
    if not desired_name:
        return obj_text

    rewritten_text = re.sub(r"^g\s+.+$", f"g {desired_name}", obj_text, count=1, flags=re.MULTILINE)
    rewritten_text = re.sub(r"^o\s+.+$", f"o {desired_name}", rewritten_text, count=1, flags=re.MULTILINE)
    return rewritten_text
