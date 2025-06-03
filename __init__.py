# -*- coding: utf-8 -*-
import bpy
import importlib
import sys
from bpy.props import PointerProperty

# 插件信息 / Addon Information
bl_info = {
    "name": "PopTools",
    "author": "PopTools Team",
    "version": (3, 1, 0),
    "blender": (4, 2, 0),
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
    "export_tools",
    "retex_tools",
    "obj_export_tools",
    "vertex_baker_tools",
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

def ensure_exporters_enabled():
    """确保必要的导出插件已启用 / Ensure required export addons are enabled"""
    required_addons = [
        'io_scene_fbx',  # FBX导出
        'io_scene_obj',  # OBJ导出
        'io_scene_gltf2' # GLTF导出
    ]
    
    for addon_name in required_addons:
        if addon_name not in bpy.context.preferences.addons:
            try:
                bpy.ops.preferences.addon_enable(module=addon_name)
                print(f"Enabled addon: {addon_name}")
            except Exception as e:
                print(f"Failed to enable addon {addon_name}: {e}")

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
        bpy.types.Scene.poptools = PointerProperty(type=modules['props'].PopToolsProperties)
    
    print("PopTools registered successfully!")

def unregister():
    """注销插件 / Unregister addon"""
    print("Unregistering PopTools...")
    
    # 删除场景属性
    if hasattr(bpy.types.Scene, 'poptools'):
        del bpy.types.Scene.poptools
    
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