# -*- coding: utf-8 -*-
"""
PopTools Utils
通用工具函数
"""

import bpy
import os
import sys
import subprocess
import bmesh
import re
from datetime import datetime
from mathutils import Vector

def show_message_box(message="", title="Message", icon='INFO'):
    """显示消息框"""
    def draw(self, context):
        self.layout.label(text=message)
    
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)

def get_addon_preferences():
    """获取插件首选项"""
    return bpy.context.preferences.addons[__package__].preferences

def ensure_directory_exists(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)
        return True
    return False

def open_directory(path):
    """在操作系统中打开目录"""
    try:
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
    except Exception as e:
        print(f"Failed to open directory {path}: {e}")

def get_safe_filename(filename):
    """获取安全的文件名（移除非法字符）"""
    # 移除或替换非法字符
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return safe_name

def prefilter_export_name(name):
    """过滤导出名称中的非法字符"""
    result = re.sub("[#%&{}<>\\\*?/'\":`|]", "_", name)
    return result

def print_execution_time(operation_name, start_time):
    """打印操作执行时间"""
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"PopTools: {operation_name} completed in {duration.total_seconds():.2f} seconds")

def get_selected_objects():
    """获取选中的对象列表"""
    return [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

def get_all_mesh_objects():
    """获取场景中所有网格对象"""
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

def export_model(path, name):
    """导出模型到指定路径"""
    act = bpy.context.scene.poptools_props.export_tools_settings

    if act.export_custom_options:
        # Scale Defaults
        apply_scale_options_value = 'FBX_SCALE_NONE'
        global_scale_value = 1.0
        if act.export_format == 'FBX' and act.export_target_engine == 'UNITY':
            apply_scale_options_value = 'FBX_SCALE_ALL'
        if act.export_format == 'FBX' and act.export_target_engine == 'UNITY2023':
            global_scale_value = 0.01

        # Custom Scale Option
        if act.use_custom_export_scale:
            apply_scale_options_value = 'FBX_SCALE_CUSTOM'
            global_scale_value = act.custom_export_scale_value

        # Axes Defaults
        forward_axis = '-Z'
        up_axis = 'Y'
        use_transform = True
        if act.export_format == 'FBX' and act.export_target_engine == 'UNITY2023':
            forward_axis = '-Y'
            up_axis = 'Z'
            use_transform = False
        if act.export_format == 'OBJ':
            forward_axis = 'NEGATIVE_Z'

        # Custom Axes Option
        if act.use_custom_export_axes:
            forward_axis = act.custom_export_forward_axis
            up_axis = act.custom_export_up_axis
            use_transform = False
            if act.export_format == 'OBJ':
                forward_axis = forward_axis.replace('-', 'NEGATIVE_')
                up_axis = up_axis.replace('-', 'NEGATIVE_')

        if act.export_format == 'FBX':
            if act.export_target_engine == 'UNITY':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options=apply_scale_options_value,
                    use_mesh_modifiers=True, mesh_smooth_type=act.export_smoothing,
                    use_mesh_edges=act.export_loose_edges, use_tspace=act.export_tangent_space,
                    add_leaf_bones=act.export_add_leaf_bones,
                    use_armature_deform_only=act.export_only_deform_bones,
                    colors_type=act.export_vc_color_space, use_custom_props=act.export_custom_props,
                    global_scale=global_scale_value, axis_forward=forward_axis, axis_up=up_axis,
                    use_space_transform=use_transform)
            elif act.export_target_engine == 'UNREAL':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options=apply_scale_options_value,
                    use_mesh_modifiers=True, mesh_smooth_type=act.export_smoothing,
                    use_mesh_edges=act.export_loose_edges, use_tspace=act.export_tangent_space,
                    add_leaf_bones=act.export_add_leaf_bones,
                    use_armature_deform_only=act.export_only_deform_bones,
                    colors_type=act.export_vc_color_space, use_custom_props=act.export_custom_props,
                    global_scale=global_scale_value, axis_forward=forward_axis, axis_up=up_axis,
                    use_space_transform=use_transform)
            elif act.export_target_engine == 'UNITY2023':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options=apply_scale_options_value,
                    use_mesh_modifiers=True, mesh_smooth_type=act.export_smoothing,
                    use_mesh_edges=act.export_loose_edges, use_tspace=act.export_tangent_space,
                    global_scale=global_scale_value, axis_forward=forward_axis, axis_up=up_axis,
                    add_leaf_bones=act.export_add_leaf_bones,
                    use_armature_deform_only=act.export_only_deform_bones,
                    colors_type=act.export_vc_color_space, use_custom_props=act.export_custom_props,
                    use_space_transform=use_transform)
            elif act.export_target_engine == '3DCOAT':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options=apply_scale_options_value,
                    use_mesh_modifiers=True, mesh_smooth_type=act.export_smoothing,
                    use_mesh_edges=act.export_loose_edges, use_tspace=act.export_tangent_space,
                    add_leaf_bones=act.export_add_leaf_bones,
                    use_armature_deform_only=act.export_only_deform_bones,
                    colors_type=act.export_vc_color_space, use_custom_props=act.export_custom_props,
                    global_scale=global_scale_value, axis_forward=forward_axis, axis_up=up_axis,
                    use_space_transform=use_transform)

        if act.export_format == 'OBJ':
            bpy.ops.wm.obj_export(
                filepath=str(path + name + '.obj'), export_selected_objects=True, apply_modifiers=True,
                export_smooth_groups=act.obj_export_smooth_groups, export_normals=True, export_uv=True,
                export_materials=True, export_triangulated_mesh=act.triangulate_before_export,
                export_object_groups=True, export_material_groups=act.obj_separate_by_materials,
                global_scale=global_scale_value, path_mode='AUTO', forward_axis=forward_axis, up_axis=up_axis)

        if act.export_format == 'GLTF':
            bpy.ops.export_scene.gltf(
                filepath=str(path + name + '.glb'), check_existing=False,
                export_image_format=act.gltf_export_image_format,
                export_tangents=act.gltf_export_tangents, export_attributes=act.gltf_export_attributes,
                use_selection=True, export_extras=act.gltf_export_custom_properties,
                export_def_bones=act.gltf_export_deform_bones_only)
    else:
        if act.export_format == 'FBX':
            if act.export_target_engine == 'UNITY':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options='FBX_SCALE_ALL', add_leaf_bones=False, colors_type='LINEAR',
                    use_custom_props=True)
            elif act.export_target_engine == 'UNREAL':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options='FBX_SCALE_NONE', mesh_smooth_type='FACE', use_tspace=True,
                    add_leaf_bones=False, colors_type='LINEAR', use_custom_props=True)
            elif act.export_target_engine == 'UNITY2023':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True, apply_scale_options='FBX_SCALE_NONE',
                    global_scale=0.01, colors_type='LINEAR', axis_forward='-Y', axis_up='Z',
                    add_leaf_bones=False,
                    use_custom_props=True, use_space_transform=False)
            elif act.export_target_engine == '3DCOAT':
                bpy.ops.export_scene.fbx(
                    filepath=str(path + name + '.fbx'), use_selection=True,
                    apply_scale_options='FBX_SCALE_ALL', add_leaf_bones=False, colors_type='LINEAR',
                    use_custom_props=True)

        if act.export_format == 'OBJ':
            bpy.ops.wm.obj_export(
                filepath=str(path + name + '.obj'), export_selected_objects=True, apply_modifiers=True,
                export_smooth_groups=True, export_normals=True, export_uv=True,
                export_materials=True, export_triangulated_mesh=act.triangulate_before_export,
                export_object_groups=True, export_material_groups=True,
                global_scale=1, path_mode='AUTO', forward_axis='NEGATIVE_Z', up_axis='Y')

        if act.export_format == 'GLTF':
            bpy.ops.export_scene.gltf(
                filepath=str(path + name + '.glb'), check_existing=False, export_image_format='AUTO',
                export_tangents=False, export_attributes=False,
                use_selection=True, export_extras=False,
                export_def_bones=False)

def duplicate_object(obj, name_suffix="_copy"):
    """复制对象"""
    # 复制对象数据
    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    new_obj.name = obj.name + name_suffix
    
    # 添加到场景
    bpy.context.collection.objects.link(new_obj)
    return new_obj

def apply_all_modifiers(obj):
    """应用对象的所有修改器"""
    bpy.context.view_layer.objects.active = obj
    
    # 应用所有修改器
    for modifier in obj.modifiers:
        try:
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except RuntimeError as e:
            print(f"Warning: Could not apply modifier {modifier.name}: {e}")

def create_lod_mesh(obj, reduction_ratio=0.5):
    """创建LOD网格"""
    # 复制对象
    lod_obj = duplicate_object(obj, f"_LOD_{int(reduction_ratio*100)}")
    
    # 进入编辑模式
    bpy.context.view_layer.objects.active = lod_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 使用bmesh进行网格简化
    bm = bmesh.from_mesh(lod_obj.data)
    
    # 计算要删除的面数
    target_faces = int(len(bm.faces) * reduction_ratio)
    faces_to_remove = len(bm.faces) - target_faces
    
    if faces_to_remove > 0:
        # 简单的面删除策略（可以改进）
        bmesh.ops.decimate(bm, 
                          geom=bm.faces[:], 
                          ratio=reduction_ratio)
    
    # 更新网格
    bm.to_mesh(lod_obj.data)
    bm.free()
    
    # 返回对象模式
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return lod_obj

def get_export_path(base_path, export_format, custom_path=None):
    """获取导出路径"""
    if custom_path:
        return custom_path
    
    if not base_path:
        base_path = bpy.path.abspath("//")
    
    format_folders = {
        'FBX': 'FBXs',
        'OBJ': 'OBJs', 
        'GLTF': 'GLTFs'
    }
    
    folder_name = format_folders.get(export_format, 'Exports')
    export_path = os.path.join(base_path, folder_name)
    
    ensure_directory_exists(export_path)
    return export_path

def validate_export_settings(settings):
    """验证导出设置"""
    errors = []
    
    # 检查自定义名称
    if hasattr(settings, 'set_custom_fbx_name') and settings.set_custom_fbx_name:
        if hasattr(settings, 'custom_fbx_name') and not settings.custom_fbx_name.strip():
            errors.append("自定义名称不能为空")
    
    # 检查文件是否已保存
    if not bpy.data.filepath and not getattr(settings, 'custom_export_path', False):
        errors.append("文件未保存，请先保存文件或使用自定义导出路径")
    
    # 检查是否有选中的对象
    if not get_selected_objects() and getattr(settings, 'export_mode', 'SELECTED') == 'SELECTED':
        errors.append("没有选中的网格对象")
    
    return errors

def setup_export_scene(obj, apply_modifiers=True):
    """设置导出场景"""
    # 清除选择
    bpy.ops.object.select_all(action='DESELECT')
    
    # 选择并激活对象
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # 应用修改器（如果需要）
    if apply_modifiers and obj.modifiers:
        apply_all_modifiers(obj)

def cleanup_temp_objects(temp_objects):
    """清理临时对象"""
    for obj in temp_objects:
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

def get_object_bounds(obj):
    """获取对象边界框"""
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    min_x = min(corner.x for corner in bbox_corners)
    max_x = max(corner.x for corner in bbox_corners)
    min_y = min(corner.y for corner in bbox_corners)
    max_y = max(corner.y for corner in bbox_corners)
    min_z = min(corner.z for corner in bbox_corners)
    max_z = max(corner.z for corner in bbox_corners)
    
    return {
        'min': Vector((min_x, min_y, min_z)),
        'max': Vector((max_x, max_y, max_z)),
        'size': Vector((max_x - min_x, max_y - min_y, max_z - min_z))
    }

def center_object_origin(obj):
    """将对象原点居中"""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

def reset_object_transforms(obj):
    """重置对象变换"""
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)

def ensure_exporters_enabled():
    """确保必要的导出器插件已启用"""
    required_addons = ['io_scene_obj', 'io_scene_fbx']
    
    for addon in required_addons:
        try:
            if addon not in bpy.context.preferences.addons:
                bpy.ops.preferences.addon_enable(module=addon)
                print(f"PopTools: Enabled {addon} addon")
        except Exception as e:
            print(f"PopTools: Warning - Could not enable {addon}: {e}")

def log_export_info(obj_name, export_path, export_format, duration=None):
    """记录导出信息"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"[{timestamp}] Exported '{obj_name}' as {export_format} to '{export_path}'"
    
    if duration:
        message += f" (took {duration:.2f}s)"
    
    print(f"PopTools: {message}")

# Registration (utils通常不需要注册类)
def register():
    pass

def unregister():
    pass