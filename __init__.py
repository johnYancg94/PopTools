# -*- coding: utf-8 -*-
import bpy
import importlib
import sys
from bpy.props import PointerProperty

# 插件信息 / Addon Information
bl_info = {
    "name": "PopTools",
    "author": "jhonyan & Claude",
    "version": (4, 1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > PopTools",
    "description": " 蜂鸟三消项目专用Blender工具箱 ",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

# 模块列表 / Module List
module_names = (
    "props",
    "preferences", 
    "utils",
    "generic_model_naming",
    "obj_export_naming",
    "doubao_responses",
    "export_tools",
    "retex_tools",
    "obj_export_tools",
    "vertex_baker_tools",
    "marmoset_baker_tools",
    "translation_tools",
    "action_naming_tools",
    "transform_axis_overlay",
)

# 存储已导入的模块 / Store imported modules
modules = {}

def reload_modules():
    """重新加载所有模块 / Reload all modules"""
    global modules
    
    for module_name in module_names:
        if module_name in modules:
            importlib.reload(modules[module_name])
        else:
            try:
                modules[module_name] = importlib.import_module(f".{module_name}", __package__)
            except ImportError as e:
                print(f"Failed to import {module_name}: {e}")

def _operator_exists(operator_group, operator_name):
    """检查Blender operator是否可用 / Check whether a Blender operator exists."""
    return hasattr(operator_group, operator_name)


def _enable_addon_if_operator_missing(addon_name, operator_group, operator_name):
    """仅在对应operator缺失时尝试启用插件 / Enable addon only if its operator is missing."""
    if _operator_exists(operator_group, operator_name):
        return

    if addon_name not in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_enable(module=addon_name)
            print(f"Enabled addon: {addon_name}")
        except Exception as e:
            print(f"Failed to enable addon {addon_name}: {e}")


def ensure_exporters_enabled():
    """确保必要导出operator可用 / Ensure required export operators are available."""
    _enable_addon_if_operator_missing('io_scene_fbx', bpy.ops.export_scene, 'fbx')
    _enable_addon_if_operator_missing('io_scene_gltf2', bpy.ops.export_scene, 'gltf')

    # Blender 4.0+ moved OBJ import/export to bpy.ops.wm.obj_import/obj_export.
    # Do not require the legacy io_scene_obj add-on when the built-in operator exists.
    _enable_addon_if_operator_missing('io_scene_obj', bpy.ops.wm, 'obj_export')

def register():
    """注册插件 / Register addon"""
    print("Registering PopTools...")
    
    # 重新加载模块
    reload_modules()
    
    # 确保导出插件已启用
    ensure_exporters_enabled()
    
    # 注册所有模块
    for module_name in module_names:
        if module_name in modules:
            try:
                if hasattr(modules[module_name], 'register'):
                    modules[module_name].register()
                    print(f"Registered module: {module_name}")
            except Exception as e:
                print(f"Failed to register module {module_name}: {e}")
    
    # 注册主属性到场景
    if 'props' in modules:
        bpy.types.Scene.poptools_props = PointerProperty(type=modules['props'].PopToolsProperties)
    
    print("PopTools registered successfully!")

def unregister():
    """注销插件 / Unregister addon"""
    print("Unregistering PopTools...")
    
    # 删除场景属性
    if hasattr(bpy.types.Scene, 'poptools_props'):
        del bpy.types.Scene.poptools_props
    

    
    # 注销所有模块（逆序）
    for module_name in reversed(module_names):
        if module_name in modules:
            try:
                if hasattr(modules[module_name], 'unregister'):
                    modules[module_name].unregister()
                    print(f"Unregistered module: {module_name}")
            except Exception as e:
                print(f"Failed to unregister module {module_name}: {e}")
    
    # 清理模块缓存
    modules.clear()
    
    print("PopTools unregistered successfully!")

if __name__ == "__main__":
    register()
