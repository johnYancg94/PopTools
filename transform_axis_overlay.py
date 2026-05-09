# -*- coding: utf-8 -*-
"""Temporary axis overlay while using G/R/S transforms in the 3D View."""

import time

import bpy
import bmesh
import blf
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector


AXIS_COLORS = {
    "X": (1.0, 0.12, 0.08, 1.0),
    "Y": (0.18, 0.85, 0.16, 1.0),
    "Z": (0.20, 0.45, 1.0, 1.0),
}

TRANSFORM_KEYS = {"G": "MOVE", "R": "ROTATE", "S": "SCALE"}
FINISH_KEYS = {"LEFTMOUSE", "RET", "NUMPAD_ENTER", "SPACE"}
CANCEL_KEYS = {"RIGHTMOUSE", "ESC"}
END_EVENT_VALUES = {"PRESS", "RELEASE", "CLICK"}
AXIS_LINE_ALPHA = 0.5
AXIS_LENGTH_FACTOR = 0.04
AXIS_LINE_WIDTH = 1.25
AXIS_ENDPOINT_SIZE = 2.5
LABEL_SIZE = 21
MAX_TARGETS = 64

_draw_handler = None
_monitor_windows = set()
_shutting_down = False

_state = {
    "active": False,
    "area": None,
    "region": None,
    "operation": None,
    "started_at": 0.0,
}


def _set_active(context, operation):
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if not area or area.type != "VIEW_3D":
        return

    _state["active"] = True
    _state["area"] = area.as_pointer()
    _state["region"] = region.as_pointer() if region else None
    _state["operation"] = operation
    _state["started_at"] = time.monotonic()
    _tag_view3d_redraw(context)


def _clear_active(context=None):
    _state["active"] = False
    _state["area"] = None
    _state["region"] = None
    _state["operation"] = None
    _state["started_at"] = 0.0
    if context:
        _tag_view3d_redraw(context)


def _tag_view3d_redraw(context):
    screen = getattr(context, "screen", None)
    if not screen:
        return

    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def _orientation_slot(context):
    slots = getattr(context.scene, "transform_orientation_slots", None)
    if not slots:
        return None

    try:
        return slots[0]
    except Exception:
        return None


def _normalized_matrix(matrix):
    if not matrix:
        return Matrix.Identity(3)

    result = matrix.to_3x3() if hasattr(matrix, "to_3x3") else Matrix(matrix)
    result.normalize()
    return result


def _matrix_from_axes(x_axis, z_axis):
    z_axis = z_axis.normalized()
    x_axis = x_axis - z_axis * x_axis.dot(z_axis)

    if x_axis.length_squared < 0.000001:
        x_axis = _fallback_axis(z_axis)
    else:
        x_axis.normalize()

    y_axis = z_axis.cross(x_axis).normalized()
    return Matrix((
        (x_axis.x, y_axis.x, z_axis.x),
        (x_axis.y, y_axis.y, z_axis.y),
        (x_axis.z, y_axis.z, z_axis.z),
    ))


def _fallback_axis(z_axis):
    reference = Vector((1.0, 0.0, 0.0))
    if abs(reference.dot(z_axis)) > 0.95:
        reference = Vector((0.0, 1.0, 0.0))
    return (reference - z_axis * reference.dot(z_axis)).normalized()


def _longest_edge_direction(edges):
    best_direction = None
    best_length = 0.0

    for edge in edges:
        direction = edge.verts[1].co - edge.verts[0].co
        length = direction.length
        if length > best_length:
            best_direction = direction
            best_length = length

    return best_direction


def _face_edge_direction(faces):
    best_edges = []
    for face in faces:
        best_edges.extend(face.edges)
    return _longest_edge_direction(best_edges)


def _selected_edge_direction(verts):
    edges = []
    for vert in verts:
        for edge in vert.link_edges:
            other_vert = edge.other_vert(vert)
            if other_vert.select:
                edges.append(edge)
    return _longest_edge_direction(edges)


def _normal_from_faces(faces):
    normal = Vector((0.0, 0.0, 0.0))
    for face in faces:
        normal += face.normal * max(face.calc_area(), 0.000001)
    return normal


def _normal_from_edges(edges):
    normal = Vector((0.0, 0.0, 0.0))
    for edge in edges:
        linked_faces = edge.link_faces
        if linked_faces:
            for face in linked_faces:
                normal += face.normal * max(face.calc_area(), 0.000001)
        else:
            for vert in edge.verts:
                normal += vert.normal
    return normal


def _normal_from_verts(verts):
    normal = Vector((0.0, 0.0, 0.0))
    for vert in verts:
        normal += vert.normal
    return normal


def _edit_normal_orientation_matrix(obj):
    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except Exception:
        return _normalized_matrix(obj.matrix_world)

    bm.normal_update()

    selected_faces = [face for face in bm.faces if face.select]
    selected_edges = [edge for edge in bm.edges if edge.select]
    selected_verts = [vert for vert in bm.verts if vert.select]

    if selected_faces:
        normal_local = _normal_from_faces(selected_faces)
        tangent_local = _face_edge_direction(selected_faces)
    elif selected_edges:
        normal_local = _normal_from_edges(selected_edges)
        tangent_local = _longest_edge_direction(selected_edges)
    elif selected_verts:
        normal_local = _normal_from_verts(selected_verts)
        tangent_local = _selected_edge_direction(selected_verts)
    else:
        return _normalized_matrix(obj.matrix_world)

    world_matrix = obj.matrix_world.to_3x3()
    if normal_local.length_squared < 0.000001:
        normal_world = world_matrix @ Vector((0.0, 0.0, 1.0))
    else:
        normal_world = world_matrix.inverted().transposed() @ normal_local

    if normal_world.length_squared < 0.000001:
        normal_world = Vector((0.0, 0.0, 1.0))
    normal_world.normalize()

    if tangent_local is not None and tangent_local.length_squared >= 0.000001:
        tangent_world = world_matrix @ tangent_local
    else:
        tangent_world = world_matrix @ Vector((1.0, 0.0, 0.0))

    return _matrix_from_axes(tangent_world, normal_world)


def _orientation_matrix(context, obj):
    slot = _orientation_slot(context)
    orientation_type = getattr(slot, "type", "GLOBAL") if slot else "GLOBAL"

    if orientation_type == "GLOBAL":
        return Matrix.Identity(3)

    if orientation_type == "LOCAL" and obj:
        return _normalized_matrix(obj.matrix_world)

    if orientation_type == "NORMAL" and obj:
        if context.mode == "EDIT_MESH" and obj.type == "MESH":
            return _edit_normal_orientation_matrix(obj)
        return _normalized_matrix(obj.matrix_world)

    if orientation_type == "GIMBAL" and obj:
        try:
            return obj.rotation_euler.to_matrix()
        except Exception:
            return _normalized_matrix(obj.matrix_world)

    if orientation_type == "VIEW":
        region_data = getattr(context.space_data, "region_3d", None)
        if region_data:
            return _normalized_matrix(region_data.view_matrix.inverted())
        return Matrix.Identity(3)

    if orientation_type == "CURSOR":
        return _normalized_matrix(context.scene.cursor.matrix)

    if orientation_type == "PARENT" and obj and obj.parent:
        return _normalized_matrix(obj.parent.matrix_world)

    custom_orientation = getattr(slot, "custom_orientation", None) if slot else None
    custom_matrix = getattr(custom_orientation, "matrix", None)
    if custom_matrix:
        return _normalized_matrix(custom_matrix)

    if obj:
        return _normalized_matrix(obj.matrix_world)

    return Matrix.Identity(3)


def _selected_edit_targets(context):
    objects = getattr(context, "objects_in_mode", None) or [context.object]
    targets = []

    for obj in objects:
        if not obj or obj.type != "MESH":
            continue

        center = obj.matrix_world.translation
        try:
            bm = bmesh.from_edit_mesh(obj.data)
            selected_verts = [vert for vert in bm.verts if vert.select]
            if selected_verts:
                local_center = Vector((0.0, 0.0, 0.0))
                for vert in selected_verts:
                    local_center += vert.co
                local_center /= len(selected_verts)
                center = obj.matrix_world @ local_center
        except Exception:
            pass

        targets.append((obj, center))
        if len(targets) >= MAX_TARGETS:
            break

    return targets


def _selected_object_targets(context):
    targets = []
    for obj in context.selected_objects:
        targets.append((obj, obj.matrix_world.translation))
        if len(targets) >= MAX_TARGETS:
            break
    return targets


def _axis_targets(context):
    if context.mode == "EDIT_MESH":
        return _selected_edit_targets(context)
    return _selected_object_targets(context)


def _axis_world_length(context, origin):
    region_data = getattr(context.space_data, "region_3d", None)
    if not region_data:
        return 1.0

    if region_data.is_perspective:
        view_origin = region_data.view_matrix.inverted().translation
        return max((view_origin - origin).length * AXIS_LENGTH_FACTOR, 0.025)

    return max(region_data.view_distance * AXIS_LENGTH_FACTOR, 0.025)


def _project(context, coord):
    return view3d_utils.location_3d_to_region_2d(
        context.region,
        context.space_data.region_3d,
        coord,
    )


def _draw_line(start, end, color):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": [start, end]})
    shader.bind()
    shader.uniform_float("color", (color[0], color[1], color[2], AXIS_LINE_ALPHA))
    batch.draw(shader)


def _draw_point(pos, color):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "POINTS", {"pos": [pos]})
    shader.bind()
    shader.uniform_float("color", (color[0], color[1], color[2], AXIS_LINE_ALPHA))
    batch.draw(shader)


def _draw_label(label, pos, color):
    font_id = 0
    blf.size(font_id, LABEL_SIZE)
    blf.color(font_id, color[0], color[1], color[2], color[3])
    blf.position(font_id, pos.x + 5.0, pos.y + 5.0, 0)
    blf.draw(font_id, label)


def _is_transform_end_event(event):
    if event.type not in FINISH_KEYS | CANCEL_KEYS:
        return False
    return event.value in END_EVENT_VALUES


def _draw_axes():
    context = bpy.context
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)

    if not _state["active"] or not area or area.type != "VIEW_3D":
        return
    if area.as_pointer() != _state["area"]:
        return
    if _state["region"] and region and region.as_pointer() != _state["region"]:
        return
    if not getattr(context.space_data, "region_3d", None):
        return

    targets = _axis_targets(context)
    if not targets:
        return

    try:
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(AXIS_LINE_WIDTH)
        gpu.state.point_size_set(AXIS_ENDPOINT_SIZE)

        for obj, origin in targets:
            origin_2d = _project(context, origin)
            if origin_2d is None:
                continue

            matrix = _orientation_matrix(context, obj)
            length = _axis_world_length(context, origin)
            axes = (
                ("X", matrix @ Vector((1.0, 0.0, 0.0))),
                ("Y", matrix @ Vector((0.0, 1.0, 0.0))),
                ("Z", matrix @ Vector((0.0, 0.0, 1.0))),
            )

            for label, direction in axes:
                end_2d = _project(context, origin + direction.normalized() * length)
                if end_2d is None:
                    continue
                color = AXIS_COLORS[label]
                _draw_line(origin_2d, end_2d, color)
                _draw_point(end_2d, color)
                _draw_label(label, end_2d, color)
    finally:
        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set("NONE")


class VIEW3D_OT_poptools_transform_axis_monitor(bpy.types.Operator):
    """Monitor G/R/S transforms and enable the temporary axis overlay."""

    bl_idname = "view3d.poptools_transform_axis_monitor"
    bl_label = "PopTools Transform Axis Monitor"
    bl_options = {"INTERNAL"}

    _timer = None
    _window_ptr = None

    def invoke(self, context, event):
        if not context.window:
            return {"CANCELLED"}

        self._window_ptr = context.window.as_pointer()
        if self._window_ptr in _monitor_windows:
            return {"CANCELLED"}

        _monitor_windows.add(self._window_ptr)
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if _shutting_down:
            self._finish(context)
            return {"CANCELLED"}

        if event.type == "TIMER":
            if _state["active"]:
                if time.monotonic() - _state["started_at"] > 120.0:
                    _clear_active(context)
                else:
                    _tag_view3d_redraw(context)
            return {"PASS_THROUGH"}

        if event.value == "PRESS" and event.type in TRANSFORM_KEYS:
            _set_active(context, TRANSFORM_KEYS[event.type])
            return {"PASS_THROUGH"}

        if _state["active"] and _is_transform_end_event(event):
            _clear_active(context)
            return {"PASS_THROUGH"}

        return {"PASS_THROUGH"}

    def _finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if self._window_ptr:
            _monitor_windows.discard(self._window_ptr)
            self._window_ptr = None


classes = (
    VIEW3D_OT_poptools_transform_axis_monitor,
)


def _start_monitor_for_window(window):
    screen = window.screen
    area = next((area for area in screen.areas if area.type == "VIEW_3D"), None)
    if not area:
        return False

    region = next((region for region in area.regions if region.type == "WINDOW"), None)
    if not region:
        return False

    if window.as_pointer() in _monitor_windows:
        return True

    with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
        bpy.ops.view3d.poptools_transform_axis_monitor("INVOKE_DEFAULT")
    return True


def _start_monitors():
    if _shutting_down:
        return None
    if bpy.app.background:
        return None

    windows = list(getattr(bpy.context.window_manager, "windows", []))
    started = False
    for window in windows:
        try:
            started = _start_monitor_for_window(window) or started
        except Exception as exc:
            print(f"PopTools transform axis monitor failed to start: {exc}")

    return None if started else 1.0


def register():
    global _draw_handler, _shutting_down

    _shutting_down = False
    for cls in classes:
        bpy.utils.register_class(cls)

    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_axes,
            (),
            "WINDOW",
            "POST_PIXEL",
        )

    bpy.app.timers.register(_start_monitors, first_interval=0.1)


def unregister():
    global _draw_handler, _shutting_down

    _shutting_down = True
    _clear_active()

    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, "WINDOW")
        _draw_handler = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
