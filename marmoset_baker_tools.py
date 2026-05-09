# -*- coding: utf-8 -*-
"""
Marmoset Toolbag one-click baking bridge.

MVP scope:
- identify Blender meshes by _low and _high suffixes
- export selected or scene meshes to one FBX
- generate a Toolbag boot script
- bake Normal, AO, and Curvature maps
- apply baked Normal/AO texture nodes back to low-poly materials
"""

import json
import os
import re
import shutil
import subprocess
import time
import glob

import bpy
from bpy.types import Operator, Panel

from .utils import get_addon_preferences
from .translation_tools import ai_translate_text_tool


LOW_SUFFIX = "_low"
HIGH_SUFFIX = "_high"
ACTIVE_BAKE_JOB = None
MARMORSET_MODEL_TRANSLATE_PROMPT = (
    "你正在为游戏资产生成英文模型名称，用于 Blender 模型和贴图命名。"
    "请把输入转换成符合游戏开发习惯的简洁英文，不要直译成长词。"
    "要求："
    "1. 只返回结果，不要解释；"
    "2. 优先使用游戏行业常见简称和习惯叫法，例如 金币 -> coin，不要输出 goldcoin；"
    "3. 结果不要包含下划线、空格、连字符或其他符号；"
    "4. 多词请直接使用 lowerCamelCase；"
    "5. 保持简洁准确，避免冗长描述。"
)

MAP_DEFINITIONS = {
    "normal": {
        "prop": "bake_normal",
        "marmoset_names": ["Normals", "Normal"],
        "canonical_suffix": "_normal",
        "suffixes": ["normal", "normals", "nrm"],
        "material_kind": "NORMAL",
    },
    "ao": {
        "prop": "bake_ao",
        "marmoset_names": ["Ambient Occlusion", "AO"],
        "canonical_suffix": "_ao",
        "suffixes": ["ao", "ambient_occlusion", "ambientocclusion"],
        "material_kind": "AO",
    },
    "albedo": {
        "prop": "bake_albedo",
        "marmoset_names": ["Albedo"],
        "canonical_suffix": "_albedo",
        "suffixes": ["albedo", "base_color", "basecolor", "diffuse"],
        "material_kind": "ALBEDO",
    },
    "curvature": {
        "prop": "bake_curvature",
        "marmoset_names": ["Curvature"],
        "canonical_suffix": "_curvature",
        "suffixes": ["curvature", "cavity"],
        "material_kind": None,
    },
}


def clean_base_name(name):
    clean_name = re.sub(r"\.\d+$", "", name or "")
    lowered = clean_name.lower()
    for suffix in (LOW_SUFFIX, HIGH_SUFFIX):
        if lowered.endswith(suffix):
            return clean_name[: -len(suffix)]
    return clean_name


def get_bake_role(obj):
    lowered = (obj.name or "").lower()
    if lowered.endswith(LOW_SUFFIX):
        return "LOW"
    if lowered.endswith(HIGH_SUFFIX):
        return "HIGH"
    return None


def mesh_complexity(obj):
    data = getattr(obj, "data", None)
    if not data:
        return 0
    return len(getattr(data, "polygons", [])) or len(getattr(data, "vertices", []))


def normalize_identifier(name):
    cleaned = re.sub(r"\.\d+$", "", name or "")
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", cleaned).strip("_")
    return cleaned or "marmoset_bake"


def rename_mesh_data(obj):
    if getattr(obj, "data", None):
        obj.data.name = obj.name


def selected_meshes(context):
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


def build_pair_base_name(prefix, fallback_name, index, total):
    base = normalize_identifier(prefix or clean_base_name(fallback_name))
    if total > 1:
        return f"{base}{index + 1:02d}"
    return base


def infer_high_low_pairs(objects, prefix=""):
    tagged_lows, tagged_highs, untagged = split_high_low(objects)
    pairs = []

    if tagged_lows or tagged_highs:
        sorted_lows = sorted(tagged_lows, key=lambda obj: clean_base_name(obj.name).lower())
        sorted_highs = sorted(tagged_highs, key=lambda obj: clean_base_name(obj.name).lower())
        pair_count = min(len(sorted_lows), len(sorted_highs))
        for index in range(pair_count):
            low_obj = sorted_lows[index]
            high_obj = sorted_highs[index]
            base_name = build_pair_base_name(prefix, high_obj.name, index, pair_count)
            low_obj.name = f"{base_name}{LOW_SUFFIX}"
            high_obj.name = f"{base_name}{HIGH_SUFFIX}"
            rename_mesh_data(low_obj)
            rename_mesh_data(high_obj)
            pairs.append({
                "base_name": base_name,
                "low": low_obj,
                "high": high_obj,
            })
        leftovers = untagged + sorted_lows[pair_count:] + sorted_highs[pair_count:]
        return pairs, leftovers

    sorted_objects = sorted(objects, key=lambda obj: mesh_complexity(obj))
    if len(sorted_objects) < 2:
        return [], list(objects)

    pair_count = len(sorted_objects) // 2
    lows = sorted_objects[:pair_count]
    highs = sorted_objects[pair_count:]
    highs = sorted(highs, key=lambda obj: mesh_complexity(obj))

    for index, low_obj in enumerate(lows):
        high_obj = highs[index] if index < len(highs) else None
        if not high_obj:
            continue
        base_name = build_pair_base_name(prefix, high_obj.name, index, pair_count)
        low_obj.name = f"{base_name}{LOW_SUFFIX}"
        high_obj.name = f"{base_name}{HIGH_SUFFIX}"
        rename_mesh_data(low_obj)
        rename_mesh_data(high_obj)
        pairs.append({"base_name": base_name, "low": low_obj, "high": high_obj})

    leftovers = sorted_objects[pair_count * 2:]
    return pairs, leftovers


def get_candidate_meshes(context, settings):
    if settings.bake_scope == "SCENE":
        return [obj for obj in context.scene.objects if obj.type == "MESH"]
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


def split_high_low(objects):
    lows = []
    highs = []
    untagged = []

    for obj in objects:
        role = get_bake_role(obj)
        if role == "LOW":
            lows.append(obj)
        elif role == "HIGH":
            highs.append(obj)
        else:
            untagged.append(obj)

    return lows, highs, untagged


def apply_decimate_to_objects(context, objects, ratio):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    ratio = max(0.0001, min(1.0, float(ratio)))
    processed = 0
    previous_active = context.view_layer.objects.active
    previous_selection = list(context.selected_objects)

    try:
        for obj in objects:
            if obj.type != "MESH":
                continue
            for selected in context.selected_objects:
                selected.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj

            decimate = obj.modifiers.new(name="High Asset Decimate", type="DECIMATE")
            decimate.decimate_type = "COLLAPSE"
            decimate.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=decimate.name)
            processed += 1
    finally:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.scene.objects:
            obj.select_set(False)
        for obj in previous_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if previous_active and previous_active.name in bpy.data.objects:
            context.view_layer.objects.active = previous_active

    return processed


def insert_base_color_adjustment_nodes(material):
    if not material or not material.use_nodes or not material.node_tree:
        return False

    tree = material.node_tree
    processed = False
    for node in tree.nodes:
        if node.bl_idname != "ShaderNodeBsdfPrincipled":
            continue
        roughness = node.inputs.get("Roughness")
        if roughness:
            roughness.default_value = 0.5
            processed = True
        base_color = node.inputs.get("Base Color")
        if not base_color or not base_color.is_linked:
            continue

        existing_link = base_color.links[0]
        source_socket = existing_link.from_socket
        source_node = existing_link.from_node
        if source_node.bl_idname in {"ShaderNodeHueSaturation", "ShaderNodeRGBCurve"}:
            continue

        tree.links.remove(existing_link)
        hue_node = tree.nodes.new(type="ShaderNodeHueSaturation")
        hue_node.location = (source_node.location.x + 220, source_node.location.y)
        hue_node.inputs["Hue"].default_value = 0.49
        hue_node.inputs["Saturation"].default_value = 1.25

        curve_node = tree.nodes.new(type="ShaderNodeRGBCurve")
        curve_node.location = (hue_node.location.x + 220, hue_node.location.y)

        tree.links.new(source_socket, hue_node.inputs["Color"])
        tree.links.new(hue_node.outputs["Color"], curve_node.inputs["Color"])
        tree.links.new(curve_node.outputs["Color"], base_color)
        processed = True

    return processed


def insert_base_color_adjustments(objects):
    changed = 0
    seen_materials = set()
    for obj in objects:
        for slot in getattr(obj, "material_slots", []):
            material = slot.material
            if not material or material.name in seen_materials:
                continue
            seen_materials.add(material.name)
            if insert_base_color_adjustment_nodes(material):
                changed += 1
    return changed


def selected_map_keys(settings):
    return [
        key
        for key, definition in MAP_DEFINITIONS.items()
        if getattr(settings, definition["prop"], False)
    ]


def ensure_directory(path):
    os.makedirs(path, exist_ok=True)
    return path


def find_toolbag_executable():
    executable_names = [
        "toolbag.exe",
        "Toolbag.exe",
        "Marmoset Toolbag.exe",
        "marmosettoolbag.exe",
    ]

    for executable_name in executable_names:
        found_path = shutil.which(executable_name)
        if found_path and os.path.isfile(found_path):
            return found_path

    search_roots = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        env_path = os.environ.get(env_name)
        if env_path:
            search_roots.append(env_path)

    patterns = []
    for root in search_roots:
        patterns.extend([
            os.path.join(root, "Marmoset", "Toolbag*", "*.exe"),
            os.path.join(root, "Marmoset Toolbag*", "*.exe"),
            os.path.join(root, "*Marmoset*", "*Toolbag*", "*.exe"),
        ])

    candidates = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            filename = os.path.basename(path).lower()
            if "toolbag" in filename and os.path.isfile(path):
                candidates.append(path)

    if not candidates:
        return ""

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[0]


def resolve_toolbag_path(settings=None):
    prefs = get_addon_preferences()
    pref_path = getattr(prefs, "marmoset_toolbag_path", "")
    return bpy.path.abspath(pref_path) if pref_path else ""


def resolve_work_dir(settings=None):
    prefs = get_addon_preferences()
    pref_path = getattr(prefs, "marmoset_bake_work_dir", "")
    return bpy.path.abspath(pref_path) if pref_path else bpy.path.abspath("//marmoset_bake/")


def save_marmoset_path_to_preferences(context, toolbag_path):
    prefs = get_addon_preferences()
    if toolbag_path:
        prefs.marmoset_toolbag_path = toolbag_path
    bpy.ops.wm.save_userpref()


def iter_base_color_images(obj):
    for material_slot in getattr(obj, "material_slots", []):
        material = material_slot.material
        if not material or not material.use_nodes or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            base_color = node.inputs.get("Base Color")
            if not base_color:
                continue
            for link in base_color.links:
                from_node = link.from_node
                if from_node and from_node.type == "TEX_IMAGE" and from_node.image:
                    yield from_node.image


def export_image_for_toolbag(image, target_dir):
    ensure_directory(target_dir)
    source_path = bpy.path.abspath(image.filepath) if getattr(image, "filepath", "") else ""
    extension = os.path.splitext(source_path)[1].lower()
    if extension not in {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd"}:
        extension = ".png"

    image_name = normalize_identifier(os.path.splitext(image.name)[0])
    target_path = os.path.join(target_dir, f"{image_name}{extension}")

    if source_path and os.path.isfile(source_path):
        if os.path.abspath(source_path) != os.path.abspath(target_path):
            shutil.copy2(source_path, target_path)
        return target_path

    original_filepath = image.filepath
    original_file_format = getattr(image, "file_format", None)
    try:
        if extension == ".png" and hasattr(image, "file_format"):
            image.file_format = "PNG"
        image.filepath_raw = target_path
        image.save()
        return target_path
    finally:
        image.filepath = original_filepath
        if original_file_format and hasattr(image, "file_format"):
            image.file_format = original_file_format


def prepare_high_material_textures(high_objects, target_dir):
    prepared = []
    assignments = []
    seen_images = set()
    for obj in high_objects:
        first_exported_path = ""
        for image in iter_base_color_images(obj):
            image_key = image.as_pointer()
            if image_key in seen_images:
                exported_path = next((item[2] for item in prepared if item[0] == image), "")
            else:
                seen_images.add(image_key)
                original_filepath = image.filepath
                try:
                    exported_path = export_image_for_toolbag(image, target_dir)
                    image.filepath = exported_path
                    prepared.append((image, original_filepath, exported_path))
                except Exception as exc:
                    print(f"PopTools Marmoset Baker: failed to prepare Base Color image '{image.name}': {exc}")
                    exported_path = ""
            if exported_path and not first_exported_path:
                first_exported_path = exported_path
        if first_exported_path:
            assignments.append({
                "object_name": obj.name,
                "texture_path": first_exported_path.replace("\\", "/"),
            })
    return prepared, assignments


def restore_prepared_images(prepared_images):
    for image, original_filepath, _exported_path in prepared_images:
        try:
            image.filepath = original_filepath
        except Exception:
            pass


def export_bake_fbx(context, objects, fbx_path, high_objects=None, include_material_textures=False):
    previous_active = context.view_layer.objects.active
    previous_selected = [obj for obj in context.scene.objects if obj.select_get()]
    prepared_images = []
    albedo_assignments = []

    try:
        if include_material_textures and high_objects:
            texture_dir = os.path.join(os.path.dirname(fbx_path), "source_textures")
            prepared_images, albedo_assignments = prepare_high_material_textures(high_objects, texture_dir)

        for obj in context.scene.objects:
            obj.select_set(False)

        for obj in objects:
            obj.select_set(True)

        context.view_layer.objects.active = objects[0]
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_NONE",
            bake_space_transform=False,
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            path_mode="COPY",
            embed_textures=True,
        )
    finally:
        restore_prepared_images(prepared_images)

        for obj in context.scene.objects:
            obj.select_set(False)

        for obj in previous_selected:
            if obj.name in context.scene.objects:
                obj.select_set(True)

        if previous_active and previous_active.name in context.scene.objects:
            context.view_layer.objects.active = previous_active

    return albedo_assignments


def write_toolbag_script(script_path, config):
    script = f'''# Auto-generated by PopTools. Run by Marmoset Toolbag at launch.
import json
import os
import time
import traceback
import mset

CONFIG = json.loads(r"""{json.dumps(config, ensure_ascii=False)}""")

MAP_ALIASES = {{
    "normal": ["Normals"],
    "ao": ["Ambient Occlusion", "AO"],
    "albedo": ["Albedo"],
    "curvature": ["Curvature"],
}}

STRICT_MAP_ALIASES = {{
    "normal": ["Normals"],
    "ao": ["Ambient Occlusion", "AO"],
    "albedo": ["Albedo"],
    "curvature": ["Curvature"],
}}

CANONICAL_SUFFIXES = {{
    "normal": "_normal",
    "ao": "_ao",
    "albedo": "_albedo",
    "curvature": "_curvature",
}}

IMAGE_EXTENSIONS = (".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd")
STATUS_EXTRA = {{}}

def write_status(state, message="", extra=None):
    if extra:
        STATUS_EXTRA.update(extra)
    payload = {{
        "state": state,
        "message": message,
        "time": time.time(),
    }}
    payload.update(STATUS_EXTRA)
    with open(CONFIG["status_path"], "w", encoding="utf-8") as status_file:
        json.dump(payload, status_file, ensure_ascii=False, indent=2)

def list_output_files():
    if not os.path.isdir(CONFIG["output_dir"]):
        return []
    return sorted(os.listdir(CONFIG["output_dir"]))

def try_set_attr(obj, attr, value):
    try:
        setattr(obj, attr, value)
        return True
    except Exception:
        return False

def force_png_output(obj):
    for attr in ("format", "outputFormat", "fileFormat", "imageFormat"):
        try_set_attr(obj, attr, "PNG")

def set_map_suffix(baker_map, key):
    suffix = CANONICAL_SUFFIXES.get(key)
    if suffix:
        try_set_attr(baker_map, "suffix", suffix)

def move_baked_files_to_output_dir():
    os.makedirs(CONFIG["output_dir"], exist_ok=True)
    moved = []
    work_dir = CONFIG["work_dir"]
    if not os.path.isdir(work_dir):
        return moved
    for filename in os.listdir(work_dir):
        source_path = os.path.join(work_dir, filename)
        if not os.path.isfile(source_path):
            continue
        if not filename.lower().endswith(IMAGE_EXTENSIONS):
            continue
        target_path = os.path.join(CONFIG["output_dir"], filename)
        try:
            os.replace(source_path, target_path)
            moved.append(filename)
        except Exception:
            pass
    return moved

def get_first_map(baker, aliases):
    for name in aliases:
        try:
            baker_map = baker.getMap(name)
            if baker_map:
                return baker_map
        except Exception:
            pass
    return None

def object_debug_name(obj):
    return getattr(obj, "name", type(obj).__name__)

def parent_chain_names(obj):
    names = []
    current = obj
    for _ in range(20):
        try:
            current = current.parent
        except Exception:
            current = None
        if not current:
            break
        names.append(object_debug_name(current))
    return names

def is_under_group(obj, group_name):
    return group_name in parent_chain_names(obj)

def scene_object_matches_high(obj, name):
    obj_name = getattr(obj, "name", "")
    base_name = name.rsplit("_high", 1)[0] if name.endswith("_high") else name
    if obj_name.lower() in {"low", "default", "scene", "render", "sky", "main camera"}:
        return False
    if obj_name.endswith("_low") or "_low" in obj_name:
        return False
    if not (is_under_group(obj, "High") or obj_name.endswith("_high") or "_high" in obj_name):
        return False
    return (
        obj_name == name
        or obj_name.startswith(name + ".")
        or obj_name.startswith(name + "_")
        or (obj_name == base_name and is_under_group(obj, "High"))
        or (obj_name.startswith(base_name + ".") and is_under_group(obj, "High"))
        or (obj_name.startswith(base_name + "_") and is_under_group(obj, "High"))
    )

def collect_children(obj):
    children = []
    try:
        direct_children = obj.getChildren()
    except Exception:
        direct_children = []
    for child in direct_children:
        children.append(child)
        children.extend(collect_children(child))
    return children

def find_high_scene_objects(name):
    matches = []
    try:
        obj = mset.findObject(name)
        if obj and scene_object_matches_high(obj, name):
            matches.append(obj)
    except Exception:
        pass

    try:
        all_objects = mset.getAllObjects()
    except Exception:
        all_objects = []

    for obj in all_objects:
        if scene_object_matches_high(obj, name):
            matches.append(obj)
        for child in collect_children(obj):
            if scene_object_matches_high(child, name):
                matches.append(child)

    if not matches:
        high_group = None
        try:
            high_group = mset.findObject("High")
        except Exception:
            high_group = None
        if high_group:
            high_children = collect_children(high_group)
            mesh_like_children = [
                child for child in high_children
                if object_debug_name(child).lower() not in {"high", "low"}
            ]
            if len(mesh_like_children) == 1:
                matches.append(mesh_like_children[0])

    unique_matches = []
    seen = set()
    for obj in matches:
        key = getattr(obj, "uid", None) or id(obj)
        if key in seen:
            continue
        seen.add(key)
        unique_matches.append(obj)
    return unique_matches

def assigned_object_matches(material, target_objects):
    target_ids = set(getattr(obj, "uid", None) or id(obj) for obj in target_objects)
    try:
        assigned_objects = material.getAssignedObjects()
    except Exception:
        assigned_objects = []
    for obj in assigned_objects:
        key = getattr(obj, "uid", None) or id(obj)
        if key in target_ids:
            return True
        for child in collect_children(obj):
            child_key = getattr(child, "uid", None) or id(child)
            if child_key in target_ids:
                return True
    return False

def find_materials_assigned_to_objects(target_objects):
    materials = []
    try:
        all_materials = mset.getAllMaterials()
    except Exception:
        all_materials = []
    for material in all_materials:
        if assigned_object_matches(material, target_objects):
            materials.append(material)
    return materials

def material_name_matches_high(material, object_name):
    material_name = getattr(material, "name", "").lower()
    object_name = (object_name or "").lower()
    base_name = object_name.rsplit("_high", 1)[0] if object_name.endswith("_high") else object_name
    if not material_name or "_low" in material_name:
        return False
    return (
        object_name in material_name
        or (base_name in material_name and ("high" in material_name or material_name.endswith("_mat")))
    )

def find_materials_named_like_high(object_name):
    try:
        all_materials = mset.getAllMaterials()
    except Exception:
        all_materials = []
    return [material for material in all_materials if material_name_matches_high(material, object_name)]

def list_scene_object_names():
    names = []
    try:
        all_objects = mset.getAllObjects()
    except Exception:
        all_objects = []
    for obj in all_objects:
        names.append(object_debug_name(obj))
        for child in collect_children(obj):
            names.append(object_debug_name(child))
    return sorted(set(names))

def set_subroutine_texture(material, slot_name, texture_path):
    assigned_fields = []
    srgb_fields = []
    field_names_seen = []
    try:
        material.setSubroutine(slot_name, "Albedo" if slot_name == "albedo" else "Texture")
    except Exception:
        pass

    subroutine = None
    for accessor in (
        lambda: getattr(material, slot_name),
        lambda: material.getSubroutine(slot_name),
    ):
        try:
            subroutine = accessor()
            if subroutine:
                break
        except Exception:
            pass

    if not subroutine:
        return {{
            "assigned_fields": assigned_fields,
            "srgb_fields": srgb_fields,
            "field_names": field_names_seen,
        }}

    common_fields = [
        "Albedo Map" if slot_name == "albedo" else "",
        "Texture",
        "texture",
        "Map",
        "map",
        "Albedo",
        "albedo",
        "Color",
        "color",
        "Base Color",
        "baseColor",
    ]
    try:
        field_names = list(subroutine.getFieldNames())
    except Exception:
        field_names = []
    field_names_seen = list(field_names)

    for field_name in common_fields + field_names:
        if not field_name:
            continue
        try:
            subroutine.setField(field_name, texture_path)
            assigned_fields.append(field_name)
            try:
                field_value = subroutine.getField(field_name)
                if hasattr(field_value, "sRGB"):
                    field_value.sRGB = True
                    srgb_fields.append(field_name)
            except Exception:
                pass
        except Exception:
            pass
    if slot_name == "albedo":
        try:
            subroutine.setField("sRGB Color", True)
            srgb_fields.append("sRGB Color")
        except Exception:
            pass

    return {{
        "assigned_fields": sorted(set(assigned_fields)),
        "srgb_fields": sorted(set(srgb_fields)),
        "field_names": field_names_seen,
    }}

def apply_high_albedo_materials():
    results = []
    for assignment in CONFIG.get("high_albedo_textures", []):
        object_name = assignment.get("object_name", "")
        texture_path = assignment.get("texture_path", "")
        if not object_name or not texture_path or not os.path.isfile(texture_path):
            results.append({{"object_name": object_name, "texture_path": texture_path, "status": "missing_texture"}})
            continue

        objects = find_high_scene_objects(object_name)
        if not objects:
            results.append({{
                "object_name": object_name,
                "texture_path": texture_path,
                "status": "missing_object",
                "scene_objects": list_scene_object_names(),
            }})
            continue

        target_materials = find_materials_assigned_to_objects(objects)
        named_materials = find_materials_named_like_high(object_name)
        for named_material in named_materials:
            if named_material not in target_materials:
                target_materials.append(named_material)

        material = None
        material_source = "existing"
        if target_materials:
            material = target_materials[0]
        else:
            material_source = "imported"
            try:
                material = mset.importMaterial(texture_path)
            except Exception as exc:
                results.append({{"object_name": object_name, "texture_path": texture_path, "status": "import_failed", "error": str(exc)}})
                continue

        materials_to_process = target_materials if target_materials else [material]
        material_results = []
        for current_material in materials_to_process:
            material_results.append({{
                "material": getattr(current_material, "name", ""),
                "albedo_set_result": set_subroutine_texture(current_material, "albedo", texture_path),
            }})

        assigned_objects = []
        assigned_material_names = []
        assign_errors = []
        for obj in objects:
            for current_material in materials_to_process:
                try:
                    current_material.assign(obj, True)
                    assigned_objects.append(object_debug_name(obj))
                    assigned_material_names.append(getattr(current_material, "name", ""))
                except Exception as exc:
                    assign_errors.append({{"object": object_debug_name(obj), "material": getattr(current_material, "name", ""), "error": str(exc)}})

        results.append({{
            "object_name": object_name,
            "texture_path": texture_path,
            "material": getattr(material, "name", ""),
            "material_source": material_source,
            "existing_materials": [getattr(mat, "name", "") for mat in target_materials],
            "named_materials": [getattr(mat, "name", "") for mat in named_materials],
            "material_results": material_results,
            "matched_objects": [object_debug_name(obj) for obj in objects],
            "matched_parent_chains": dict((object_debug_name(obj), parent_chain_names(obj)) for obj in objects),
            "assigned_objects": assigned_objects,
            "assigned_materials": sorted(set(assigned_material_names)),
            "assign_errors": assign_errors,
            "status": "assigned" if assigned_objects else "assign_failed",
        }})
    return results

def map_identity(baker_map):
    parts = [type(baker_map).__name__]
    for attr in ("name", "suffix", "label"):
        try:
            value = getattr(baker_map, attr)
        except Exception:
            value = ""
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()

def configure_maps(baker):
    enabled_maps = set(CONFIG["map_keys"])
    all_maps = []
    try:
        all_maps = baker.getAllMaps()
    except Exception:
        all_maps = []

    configured = []
    for baker_map in all_maps:
        identity = map_identity(baker_map)
        try:
            force_png_output(baker_map)
            baker_map.enabled = False
            configured.append({{"identity": identity, "enabled": False, "matched_key": None}})
        except Exception as exc:
            configured.append({{"identity": identity, "error": str(exc)}})

    enabled_exact = []
    missing_exact = []
    for key in sorted(enabled_maps):
        aliases = STRICT_MAP_ALIASES.get(key, [])
        baker_map = get_first_map(baker, aliases)
        if not baker_map:
            missing_exact.append({{"key": key, "aliases": aliases}})
            continue
        try:
            force_png_output(baker_map)
            set_map_suffix(baker_map, key)
            baker_map.enabled = True
            enabled_exact.append({{"key": key, "identity": map_identity(baker_map), "aliases": aliases}})
        except Exception as exc:
            missing_exact.append({{"key": key, "aliases": aliases, "error": str(exc)}})

    return {{"configured": configured, "enabled_exact": enabled_exact, "missing_exact": missing_exact}}

def main():
    write_status("starting", "Toolbag script started")
    mset.newScene()
    try:
        prefs = mset.getPreferences()
        prefs.importFbxWithMaterials = True
    except Exception as exc:
        write_status("preference_warning", "Could not enable FBX material import", {{"preference_error": str(exc)}})
    baker = mset.BakerObject()
    force_png_output(baker)
    baker.name = CONFIG["project_name"]
    write_status("importing", "Importing bake model")
    baker.importModel(CONFIG["fbx_path"])
    albedo_material_results = apply_high_albedo_materials()
    write_status("materials", "Applied high-poly albedo materials", {{"albedo_materials": albedo_material_results, "scene_objects_after_import": list_scene_object_names()}})
    baker.outputPath = CONFIG["output_file"]
    baker.outputBits = CONFIG["output_bits"]
    baker.outputSamples = CONFIG["output_samples"]
    baker.edgePadding = CONFIG["edge_padding"]
    baker.outputWidth = CONFIG["resolution"]
    baker.outputHeight = CONFIG["resolution"]

    configured_maps = configure_maps(baker)
    write_status("baking", "Bake started", {{"configured_maps": configured_maps, "albedo_materials": albedo_material_results, "output_path": baker.outputPath}})
    baker.bake()
    moved_files = move_baked_files_to_output_dir()
    write_status("complete", "Bake finished", {{"moved_files": moved_files, "output_files": list_output_files()}})

    if CONFIG["close_toolbag_when_done"]:
        mset.quit()

try:
    main()
except Exception as exc:
    write_status("failed", str(exc), {{"traceback": traceback.format_exc()}})
    raise
'''
    with open(script_path, "w", encoding="utf-8", newline="\n") as script_file:
        script_file.write(script)


def find_map_file(output_dir, low_obj_name, map_key, allow_fallback=False):
    definition = MAP_DEFINITIONS[map_key]
    image_extensions = {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd"}
    low_base = clean_base_name(low_obj_name).lower()
    candidates = []

    if not os.path.isdir(output_dir):
        return None

    for filename in os.listdir(output_dir):
        stem, extension = os.path.splitext(filename)
        if extension.lower() not in image_extensions:
            continue

        normalized_stem = stem.lower().replace(" ", "_").replace("-", "_")
        if not any(suffix in normalized_stem for suffix in definition["suffixes"]):
            continue
        if map_key == "normal" and ("bent" in normalized_stem or "object" in normalized_stem):
            continue

        if low_base and low_base in normalized_stem:
            score = 10
        elif allow_fallback:
            score = 1
        else:
            continue
        if extension.lower() == ".png":
            score += 2
        candidates.append((score, os.path.join(output_dir, filename)))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def ensure_material(obj):
    if obj.data.materials:
        material = obj.data.materials[0]
    else:
        material = bpy.data.materials.new(f"{clean_base_name(obj.name)}_mat")
        obj.data.materials.append(material)

    material.use_nodes = True
    return material


def get_principled_node(material):
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def get_input(node, names):
    for name in names:
        socket = node.inputs.get(name)
        if socket:
            return socket
    return None


def apply_image_to_material(obj, map_key, image_path):
    material = ensure_material(obj)
    principled = get_principled_node(material)
    if not principled:
        return False

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    image = bpy.data.images.load(image_path, check_existing=True)
    texture_node = nodes.new(type="ShaderNodeTexImage")
    texture_node.name = f"PopTools {map_key}"
    texture_node.label = f"PopTools {map_key}"
    texture_node.image = image

    material_kind = MAP_DEFINITIONS[map_key]["material_kind"]
    if material_kind == "NORMAL":
        image.colorspace_settings.name = "Non-Color"
        normal_node = nodes.new(type="ShaderNodeNormalMap")
        normal_node.name = "PopTools Normal Map"
        normal_node.label = "PopTools Normal Map"
        links.new(texture_node.outputs["Color"], normal_node.inputs["Color"])
        normal_input = get_input(principled, ["Normal"])
        if normal_input:
            links.new(normal_node.outputs["Normal"], normal_input)
            return True

    if material_kind == "AO":
        image.colorspace_settings.name = "Non-Color"
        texture_node.location.x -= 300
        texture_node.location.y -= 250
        return True

    if material_kind == "ALBEDO":
        color_input = get_input(principled, ["Base Color"])
        if color_input:
            links.new(texture_node.outputs["Color"], color_input)
            return True

    return False


def apply_maps_to_low_materials(lows, output_dir, map_keys):
    applied_count = 0
    missing = []
    allow_fallback = len(lows) == 1

    for low_obj in lows:
        for map_key in map_keys:
            image_path = find_map_file(output_dir, low_obj.name, map_key, allow_fallback)
            if not image_path:
                missing.append(f"{low_obj.name}:{map_key}")
                continue

            if apply_image_to_material(low_obj, map_key, image_path):
                applied_count += 1

    return applied_count, missing


def move_root_baked_files_to_textures(work_dir, output_dir):
    ensure_directory(output_dir)
    moved = []
    image_extensions = {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".exr", ".psd"}
    for filename in os.listdir(work_dir):
        source_path = os.path.join(work_dir, filename)
        if not os.path.isfile(source_path):
            continue
        if os.path.splitext(filename)[1].lower() not in image_extensions:
            continue
        target_path = os.path.join(output_dir, filename)
        try:
            shutil.move(source_path, target_path)
            moved.append(filename)
        except Exception as exc:
            print(f"PopTools Marmoset Baker failed to move {filename}: {exc}")
    return moved


def cleanup_bake_temp_files(job):
    temp_paths = [
        job.get("fbx_path"),
        job.get("script_path"),
        job.get("status_path"),
        job.get("log_path"),
    ]
    removed = []
    for path in temp_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            os.remove(path)
            removed.append(path)
        except Exception as exc:
            print(f"PopTools Marmoset Baker failed to remove temp file {path}: {exc}")

    source_texture_dir = os.path.join(job.get("work_dir", ""), "source_textures")
    if os.path.isdir(source_texture_dir):
        try:
            shutil.rmtree(source_texture_dir)
            removed.append(source_texture_dir)
        except Exception as exc:
            print(f"PopTools Marmoset Baker failed to remove temp dir {source_texture_dir}: {exc}")

    return removed


def notify_user(title, message, icon="INFO"):
    def draw(self, context):
        self.layout.label(text=message)

    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception:
        print(f"{title}: {message}")


def read_status_file(status_path):
    if not os.path.exists(status_path):
        return None
    try:
        with open(status_path, "r", encoding="utf-8") as status_file:
            return json.load(status_file)
    except Exception:
        return None


def poll_active_bake_job():
    global ACTIVE_BAKE_JOB

    job = ACTIVE_BAKE_JOB
    if not job:
        return None

    status = read_status_file(job["status_path"])
    process = job["process"]
    process_returned = process.poll()

    if status and status.get("state") == "complete":
        moved = move_root_baked_files_to_textures(job["work_dir"], job["output_dir"])
        if moved:
            print("PopTools Marmoset Baker moved root output files: " + ", ".join(moved))
        applied_count = 0
        missing = []
        if job["apply_to_low_material"]:
            applied_count, missing = apply_maps_to_low_materials(
                job["lows"],
                job["output_dir"],
                job["map_keys"],
            )
        if missing:
            print("PopTools Marmoset Baker missing maps: " + ", ".join(missing))

        duration = time.time() - job["start_time"]
        message = f"烘焙完成，耗时 {duration:.1f}s"
        if job["apply_to_low_material"]:
            message += f"，已回填 {applied_count} 张贴图"
        if job.get("cleanup_when_done"):
            removed = cleanup_bake_temp_files(job)
            if removed:
                print("PopTools Marmoset Baker cleaned temp files: " + ", ".join(removed))
        notify_user("Marmoset烘焙", message, "INFO")
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    if status and status.get("state") == "failed":
        notify_user("Marmoset烘焙失败", status.get("message", "未知错误"), "ERROR")
        print(status.get("traceback", ""))
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    if process_returned is not None and process_returned != 0:
        notify_user("Marmoset烘焙失败", f"Toolbag进程退出码: {process_returned}", "ERROR")
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    if process_returned == 0:
        notify_user("Marmoset烘焙失败", "Toolbag已退出，但没有写入完成状态文件", "ERROR")
        job["log_file"].close()
        ACTIVE_BAKE_JOB = None
        return None

    return 1.0


class POPTOOLS_OT_marmoset_mark_low(Operator):
    """给选中网格添加_low后缀"""
    bl_idname = "poptools.marmoset_mark_low"
    bl_label = "标记为_low"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            obj.name = f"{clean_base_name(obj.name)}{LOW_SUFFIX}"
            count += 1

        self.report({"INFO"}, f"已标记 {count} 个低模对象")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_mark_high(Operator):
    """给选中网格添加_high后缀"""
    bl_idname = "poptools.marmoset_mark_high"
    bl_label = "标记为_high"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            obj.name = f"{clean_base_name(obj.name)}{HIGH_SUFFIX}"
            count += 1

        self.report({"INFO"}, f"已标记 {count} 个高模对象")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_auto_mark_high_low(Operator):
    """自动识别并标记选中对象的高低模后缀"""
    bl_idname = "poptools.marmoset_auto_mark_high_low"
    bl_label = "自动标记高低模"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        objects = get_candidate_meshes(context, settings)
        pairs, leftovers = infer_high_low_pairs(objects, settings.model_name_prefix.strip())

        if leftovers:
            self.report({"ERROR"}, "存在无法自动配对的对象，请选择成对的高低模")
            return {"CANCELLED"}

        if not pairs:
            self.report({"ERROR"}, "需要至少两个网格对象才能自动标记")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已自动标记 {len(pairs)} 组高低模")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_generate_lowpoly(Operator):
    """复制选中高模并使用Decimate与智能UV生成低模"""
    bl_idname = "poptools.marmoset_generate_lowpoly"
    bl_label = "一键生成低模"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        high_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not high_objects:
            self.report({"ERROR"}, "请先选择需要生成低模的高模对象")
            return {"CANCELLED"}

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        ratio = max(0.0001, min(1.0, float(settings.lowpoly_decimate_ratio)))
        prefix = settings.model_name_prefix.strip()
        generated_lows = []
        original_selection = list(context.selected_objects)
        original_active = context.view_layer.objects.active
        pair_count = len(high_objects)

        try:
            for index, high_obj in enumerate(high_objects):
                base_name = build_pair_base_name(prefix, high_obj.name, index, pair_count)
                high_obj.name = f"{base_name}{HIGH_SUFFIX}"
                rename_mesh_data(high_obj)

                low_obj = high_obj.copy()
                low_obj.data = high_obj.data.copy()
                low_obj.animation_data_clear()
                low_obj.name = f"{base_name}{LOW_SUFFIX}"
                rename_mesh_data(low_obj)
                low_obj.data.materials.clear()
                context.collection.objects.link(low_obj)

                for selected in context.selected_objects:
                    selected.select_set(False)
                low_obj.select_set(True)
                context.view_layer.objects.active = low_obj

                decimate = low_obj.modifiers.new(name="Generate Low Decimate", type="DECIMATE")
                decimate.decimate_type = "COLLAPSE"
                decimate.ratio = ratio
                bpy.ops.object.modifier_apply(modifier=decimate.name)

                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project()
                bpy.ops.object.mode_set(mode="OBJECT")

                bpy.ops.object.shade_smooth()
                generated_lows.append(low_obj)
        except Exception as exc:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            self.report({"ERROR"}, f"生成低模失败: {exc}")
            return {"CANCELLED"}
        finally:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for obj in context.scene.objects:
                obj.select_set(False)
            for obj in generated_lows:
                obj.select_set(True)
            context.view_layer.objects.active = generated_lows[0] if generated_lows else original_active
            if not generated_lows:
                for obj in original_selection:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)

        self.report({"INFO"}, f"已生成 {len(generated_lows)} 个低模，减面比例 {ratio:g}")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_ai_translate_model_name(Operator):
    """将模型名称输入框内容进行AI翻译"""
    bl_idname = "poptools.marmoset_ai_translate_model_name"
    bl_label = "AI翻译"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        raw_name = (settings.model_name_prefix or "").strip()
        if not raw_name:
            self.report({"WARNING"}, "请先输入需要翻译的模型名称")
            return {"CANCELLED"}

        translated = ai_translate_text_tool(raw_name, MARMORSET_MODEL_TRANSLATE_PROMPT)
        translated = normalize_identifier(translated)
        if not translated:
            self.report({"ERROR"}, "AI翻译结果为空")
            return {"CANCELLED"}

        settings.model_name_prefix = translated
        self.report({"INFO"}, "模型名称AI翻译完成")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_auto_detect_toolbag(Operator):
    """自动查找Marmoset Toolbag路径"""
    bl_idname = "poptools.marmoset_auto_detect_toolbag"
    bl_label = "自动导入八猴路径"
    bl_options = {"REGISTER"}

    save_to_preferences: bpy.props.BoolProperty(
        name="保存到首选项",
        description="查找到路径后保存为插件默认路径",
        default=True
    )

    def execute(self, context):
        toolbag_path = find_toolbag_executable()
        if not toolbag_path:
            self.report({"WARNING"}, "未自动找到Marmoset Toolbag，请手动选择路径")
            return {"CANCELLED"}

        if self.save_to_preferences:
            save_marmoset_path_to_preferences(context, toolbag_path)

        self.report({"INFO"}, f"已找到Toolbag: {toolbag_path}")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_open_addon_preferences(Operator):
    """打开PopTools插件首选项"""
    bl_idname = "poptools.marmoset_open_addon_preferences"
    bl_label = "设置"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        context.preferences.active_section = 'ADDONS'
        bpy.ops.preferences.addon_show(module=__package__)
        return {"FINISHED"}


class POPTOOLS_OT_high_asset_one_click_process(Operator):
    """对选中高模资产进行减面和Base Color调色节点插入"""
    bl_idname = "poptools.high_asset_one_click_process"
    bl_label = "高模资产一键处理"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and bool(selected_meshes(context))

    def execute(self, context):
        objects = selected_meshes(context)
        if not objects:
            self.report({"ERROR"}, "请先选择需要处理的高模资产")
            return {"CANCELLED"}

        try:
            decimated_count = apply_decimate_to_objects(context, objects, 0.1)
            material_count = insert_base_color_adjustments(objects)
        except Exception as exc:
            self.report({"ERROR"}, f"高模资产处理失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已处理 {decimated_count} 个模型，插入 {material_count} 个材质节点链")
        return {"FINISHED"}


class POPTOOLS_OT_high_asset_quick_decimate(Operator):
    """按指定比例对选中模型添加并应用Decimate修改器"""
    bl_idname = "poptools.high_asset_quick_decimate"
    bl_label = "快捷减面"
    bl_options = {"REGISTER", "UNDO"}

    ratio: bpy.props.FloatProperty(
        name="Ratio",
        description="Decimate Collapse比例",
        default=0.1,
        min=0.0001,
        max=1.0,
    )

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and bool(selected_meshes(context))

    def execute(self, context):
        objects = selected_meshes(context)
        if not objects:
            self.report({"ERROR"}, "请先选择需要减面的模型")
            return {"CANCELLED"}

        try:
            count = apply_decimate_to_objects(context, objects, self.ratio)
        except Exception as exc:
            self.report({"ERROR"}, f"快捷减面失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已按 {self.ratio:g} 减面并应用 {count} 个模型")
        return {"FINISHED"}


class POPTOOLS_OT_high_asset_optimize_material_color(Operator):
    """给选中模型材质插入颜色优化节点并设置Roughness"""
    bl_idname = "poptools.high_asset_optimize_material_color"
    bl_label = "材质颜色优化"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props") and bool(selected_meshes(context))

    def execute(self, context):
        objects = selected_meshes(context)
        if not objects:
            self.report({"ERROR"}, "请先选择需要优化材质的模型")
            return {"CANCELLED"}

        try:
            material_count = insert_base_color_adjustments(objects)
        except Exception as exc:
            self.report({"ERROR"}, f"材质颜色优化失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已优化 {material_count} 个材质")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_one_click_bake(Operator):
    """导出高低模并调用Marmoset Toolbag烘焙"""
    bl_idname = "poptools.marmoset_one_click_bake"
    bl_label = "一键Marmoset烘焙"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "poptools_props")

    def execute(self, context):
        global ACTIVE_BAKE_JOB

        if ACTIVE_BAKE_JOB:
            self.report({"WARNING"}, "已有Marmoset烘焙任务正在运行")
            return {"CANCELLED"}

        settings = context.scene.poptools_props.marmoset_baker_settings
        toolbag_path = resolve_toolbag_path(settings)
        if not toolbag_path:
            toolbag_path = find_toolbag_executable()
            if toolbag_path:
                save_marmoset_path_to_preferences(context, toolbag_path)
        if not toolbag_path or not os.path.isfile(toolbag_path):
            self.report({"ERROR"}, "请先设置有效的Marmoset Toolbag可执行文件路径")
            return {"CANCELLED"}

        map_keys = selected_map_keys(settings)
        if not map_keys:
            self.report({"ERROR"}, "至少需要选择一个烘焙通道")
            return {"CANCELLED"}

        objects = get_candidate_meshes(context, settings)
        pairs, leftovers = infer_high_low_pairs(objects, settings.model_name_prefix.strip())
        if leftovers:
            self.report({"ERROR"}, "存在无法自动配对的对象，请选择成对的高低模")
            return {"CANCELLED"}
        if not pairs:
            self.report({"ERROR"}, "需要至少一个_low低模和一个_high高模")
            return {"CANCELLED"}
        lows = [pair["low"] for pair in pairs]
        highs = [pair["high"] for pair in pairs]

        work_dir = ensure_directory(resolve_work_dir(settings))
        output_dir = ensure_directory(os.path.join(work_dir, "textures"))
        project_name = pairs[0]["base_name"] if len(pairs) == 1 else normalize_identifier(settings.model_name_prefix.strip() or pairs[0]["base_name"])
        fbx_path = os.path.join(work_dir, f"{project_name}_bake.fbx")
        script_path = os.path.join(work_dir, f"{project_name}_marmoset_bake.py")
        status_path = os.path.join(work_dir, f"{project_name}_marmoset_status.json")
        log_path = os.path.join(work_dir, f"{project_name}_marmoset_process.log")
        output_file = os.path.join(output_dir, f"{project_name}.png")

        if os.path.exists(status_path):
            os.remove(status_path)

        try:
            high_albedo_textures = export_bake_fbx(
                context,
                lows + highs,
                fbx_path,
                high_objects=highs,
                include_material_textures="albedo" in map_keys,
            )
            config = {
                "project_name": project_name,
                "fbx_path": fbx_path.replace("\\", "/"),
                "output_dir": output_dir.replace("\\", "/"),
                "output_file": output_file.replace("\\", "/"),
                "work_dir": work_dir.replace("\\", "/"),
                "high_albedo_textures": high_albedo_textures,
                "resolution": int(settings.resolution),
                "output_bits": int(settings.output_bits),
                "output_samples": int(settings.output_samples),
                "edge_padding": settings.edge_padding,
                "map_keys": map_keys,
                "close_toolbag_when_done": bool(settings.close_toolbag_when_done),
                "status_path": status_path.replace("\\", "/"),
            }
            write_toolbag_script(script_path, config)
        except Exception as exc:
            self.report({"ERROR"}, f"准备烘焙数据失败: {exc}")
            return {"CANCELLED"}

        try:
            log_file = open(log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                [toolbag_path, script_path],
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except Exception as exc:
            self.report({"ERROR"}, f"启动Toolbag失败: {exc}")
            return {"CANCELLED"}

        ACTIVE_BAKE_JOB = {
            "process": process,
            "lows": list(lows),
            "output_dir": output_dir,
            "work_dir": work_dir,
            "map_keys": list(map_keys),
            "apply_to_low_material": bool(settings.apply_to_low_material),
            "cleanup_when_done": bool(settings.close_toolbag_when_done),
            "fbx_path": fbx_path,
            "script_path": script_path,
            "status_path": status_path,
            "log_path": log_path,
            "start_time": time.time(),
            "log_file": log_file,
        }
        bpy.app.timers.register(poll_active_bake_job, first_interval=1.0)
        self.report({"INFO"}, f"已启动Marmoset异步烘焙，状态文件: {status_path}")
        return {"FINISHED"}


class POPTOOLS_OT_marmoset_open_work_dir(Operator):
    """打开Marmoset烘焙工作目录"""
    bl_idname = "poptools.marmoset_open_work_dir"
    bl_label = "打开烘焙目录"
    bl_options = {"REGISTER"}

    def execute(self, context):
        settings = context.scene.poptools_props.marmoset_baker_settings
        work_dir = ensure_directory(resolve_work_dir(settings))
        os.startfile(work_dir)
        return {"FINISHED"}


class POPTOOLS_PT_marmoset_baker(Panel):
    """Marmoset一键烘焙面板"""
    bl_label = "AI资产处理工具"
    bl_idname = "POPTOOLS_PT_marmoset_baker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PopTools"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_marmoset_baker_tools

    def draw(self, context):
        layout = self.layout
        settings = context.scene.poptools_props.marmoset_baker_settings
        objects = get_candidate_meshes(context, settings)
        lows, highs, untagged = split_high_low(objects)

        layout.use_property_split = True
        layout.use_property_decorate = False

        prefs = get_addon_preferences()
        asset_button = layout.row()
        asset_button.scale_y = 1.35
        asset_button.operator("poptools.high_asset_one_click_process", icon="MOD_DECIM")

        material_button = layout.row()
        material_button.scale_y = 1.2
        material_button.operator("poptools.high_asset_optimize_material_color", icon="MATERIAL")

        layout.label(text="快速减面", icon="MOD_DECIM")
        decimate_row = layout.row(align=True)
        for ratio in (0.8, 0.5, 0.3, 0.1):
            operator = decimate_row.operator(
                "poptools.high_asset_quick_decimate",
                text=f"{ratio:g}",
            )
            operator.ratio = ratio

        layout.separator()
        layout.label(text="Marmoset一键烘焙", icon="RENDER_STILL")
        layout.prop(prefs, "marmoset_toolbag_path", text="Toolbag路径")
        layout.prop(prefs, "marmoset_bake_work_dir", text="工作目录")
        path_row = layout.row(align=True)
        path_row.operator("poptools.marmoset_auto_detect_toolbag", icon="VIEWZOOM")
        path_row.operator("poptools.marmoset_open_addon_preferences", text="", icon="PREFERENCES")
        layout.prop(settings, "bake_scope")
        layout.prop(settings, "resolution")
        layout.prop(settings, "output_bits")
        layout.prop(settings, "output_samples")
        layout.prop(settings, "edge_padding")

        map_box = layout.box()
        map_box.label(text="烘焙通道", icon="TEXTURE")
        map_col = map_box.column(align=True)
        map_col.prop(settings, "bake_normal")
        map_col.prop(settings, "bake_ao")
        map_col.prop(settings, "bake_albedo")
        map_col.prop(settings, "bake_curvature")

        role_box = layout.box()
        role_box.label(text="高低模识别", icon="OUTLINER_OB_MESH")
        name_row = role_box.row(align=True)
        name_row.prop(settings, "model_name_prefix")
        name_row.operator("poptools.marmoset_ai_translate_model_name", text="AI翻译", icon="OUTLINER_OB_LIGHT")
        role_box.label(text=f"低模: {len(lows)}  高模: {len(highs)}  未标记: {len(untagged)}")
        role_box.operator("poptools.marmoset_auto_mark_high_low", icon="SORTSIZE")
        row = role_box.row(align=True)
        row.operator("poptools.marmoset_mark_low", icon="IMPORT")
        row.operator("poptools.marmoset_mark_high", icon="EXPORT")

        layout.separator()
        lowpoly_box = layout.box()
        lowpoly_box.prop(settings, "lowpoly_decimate_ratio")
        lowpoly_button = lowpoly_box.row()
        lowpoly_button.scale_y = 1.2
        lowpoly_button.operator("poptools.marmoset_generate_lowpoly", icon="MOD_DECIM")
        layout.separator()
        bake_row = layout.row()
        bake_row.scale_y = 1.4
        bake_row.operator("poptools.marmoset_one_click_bake", icon="RENDER_STILL")
        layout.prop(settings, "apply_to_low_material")
        layout.prop(settings, "close_toolbag_when_done")
        layout.operator("poptools.marmoset_open_work_dir", icon="FILE_FOLDER")


classes = (
    POPTOOLS_OT_marmoset_mark_low,
    POPTOOLS_OT_marmoset_mark_high,
    POPTOOLS_OT_marmoset_auto_mark_high_low,
    POPTOOLS_OT_marmoset_generate_lowpoly,
    POPTOOLS_OT_marmoset_ai_translate_model_name,
    POPTOOLS_OT_marmoset_auto_detect_toolbag,
    POPTOOLS_OT_marmoset_open_addon_preferences,
    POPTOOLS_OT_high_asset_one_click_process,
    POPTOOLS_OT_high_asset_quick_decimate,
    POPTOOLS_OT_high_asset_optimize_material_color,
    POPTOOLS_OT_marmoset_one_click_bake,
    POPTOOLS_OT_marmoset_open_work_dir,
    POPTOOLS_PT_marmoset_baker,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
