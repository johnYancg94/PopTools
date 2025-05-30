# -*- coding: utf-8 -*-
"""
PopTools Addon: A collection of useful tools for Blender.

This addon combines multiple tools including:
- Mesh Exporter: Batch export meshes with LOD generation
- ReTex: Texture management tools (placeholder for future integration)
"""

bl_info = {
    "name": "PopTools",
    "author": "JhonYan & Claude & Gemini",
    "version": (2, 3, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > PopTools Tab",
    "description": "A collection of useful tools including Batch Mesh Exporter and ReTex.",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
import importlib
import os
import sys
from bpy.types import AddonPreferences
from bpy.props import BoolProperty

# 插件首选项设置
class PopToolsPreferences(AddonPreferences):
    # 这必须与插件名称匹配
    bl_idname = __name__
    
    # 导出/导入工具启用选项
    export_import_enable: BoolProperty(
        name="启用导出/导入工具",
        description="启用或禁用导出/导入工具面板",
        default=True,
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_import_enable")

# 确保必要的导出器插件已启用
def ensure_exporters_enabled():
    """确保必要的导出器插件已启用"""
    required_addons = ['io_scene_obj', 'io_scene_fbx']
    for addon in required_addons:
        try:
            # 检查插件是否已启用
            if not addon in bpy.context.preferences.addons:
                # 尝试启用插件
                bpy.ops.preferences.addon_enable(module=addon)
                print(f"已启用 {addon} 插件")
        except Exception as e:
            print(f"无法启用 {addon} 插件: {e}")
            # 继续执行，不中断加载过程

# Add modules directory to path for imports
modules_dir = os.path.join(os.path.dirname(__file__), "modules")
if modules_dir not in sys.path:
    sys.path.append(modules_dir)

# --- Module Imports will be handled dynamically in register/unregister ---
from .modules import easymesh_batch_exporter # Ensure exporter module is imported
from .modules import export_fbx # Ensure export_fbx module is imported

def register():
    """Registers all addon classes and properties."""
    # 注册插件首选项
    bpy.utils.register_class(PopToolsPreferences)
    
    # Create modules directory if it doesn't exist
    os.makedirs(modules_dir, exist_ok=True)
    os.makedirs(os.path.join(modules_dir, "easymesh_batch_exporter"), exist_ok=True)
    os.makedirs(os.path.join(modules_dir, "retex"), exist_ok=True)
    os.makedirs(os.path.join(modules_dir, "vertex_to_bone_baker"), exist_ok=True)
    
    # 确保必要的导出器插件已启用
    ensure_exporters_enabled()

    # --- Dynamic Module Imports and Reloading ---
    # ReTex module
    try:
        if ".modules.retex" in sys.modules and "bpy" in locals():
            importlib.reload(sys.modules[".modules.retex"])
            if ".modules.retex.properties" in sys.modules: importlib.reload(sys.modules[".modules.retex.properties"])
            if ".modules.retex.operators" in sys.modules: importlib.reload(sys.modules[".modules.retex.operators"])
            if ".modules.retex.panels" in sys.modules: importlib.reload(sys.modules[".modules.retex.panels"])

        from .modules.retex import register as register_retex_func
        register_retex_func()
    except ImportError as e:
        print(f"ReTex module not found or could not be imported during register: {e}")
    except Exception as e:
        print(f"Error registering ReTex module: {e}")

    # Exporter module
    try:
        if ".modules.easymesh_batch_exporter" in sys.modules and "bpy" in locals():
            importlib.reload(sys.modules[".modules.easymesh_batch_exporter"])
            if ".modules.easymesh_batch_exporter.properties" in sys.modules: importlib.reload(sys.modules[".modules.easymesh_batch_exporter.properties"])
            if ".modules.easymesh_batch_exporter.operators" in sys.modules: importlib.reload(sys.modules[".modules.easymesh_batch_exporter.operators"])
            if ".modules.easymesh_batch_exporter.panels" in sys.modules: importlib.reload(sys.modules[".modules.easymesh_batch_exporter.panels"])
            if ".modules.easymesh_batch_exporter.indicators" in sys.modules: importlib.reload(sys.modules[".modules.easymesh_batch_exporter.indicators"])

        # 确保导出器模块被正确导入和注册
        from .modules.easymesh_batch_exporter import register as register_exporter_func
        register_exporter_func()
        # 确保panels模块被正确导入和注册
        try:
            from .modules.easymesh_batch_exporter import panels
            if hasattr(panels, 'register'):
                panels.register()
        except Exception as e:
            print(f"Error registering exporter panels: {e}")
    except ImportError as e:
        print(f"Exporter module not found or could not be imported during register: {e}")
    except Exception as e:
        print(f"Error registering exporter module: {e}")
    
    # Vertex to Bone Baker module
    try:
        if ".modules.vertex_to_bone_baker" in sys.modules and "bpy" in locals():
            importlib.reload(sys.modules[".modules.vertex_to_bone_baker"])

        from .modules.vertex_to_bone_baker import register as register_vtbb_func
        register_vtbb_func()
    except ImportError as e:
        print(f"Vertex to Bone Baker module not found or could not be imported during register: {e}")
    except Exception as e:
        print(f"Error registering Vertex to Bone Baker module: {e}")

    # export_fbx module
    try:
        if ".modules.export_fbx" in sys.modules and "bpy" in locals():
            importlib.reload(sys.modules[".modules.export_fbx"])
            if ".modules.export_fbx.panels" in sys.modules: importlib.reload(sys.modules[".modules.export_fbx.panels"])
            if ".modules.export_fbx.utils" in sys.modules: importlib.reload(sys.modules[".modules.export_fbx.utils"])
            if ".modules.export_fbx.import_export_tools" in sys.modules: importlib.reload(sys.modules[".modules.export_fbx.import_export_tools"])

        from .modules.export_fbx import register as register_export_fbx_func
        register_export_fbx_func()
    except ImportError as e:
        print(f"export_fbx module not found or could not be imported during register: {e}")
    except Exception as e:
        print(f"Error registering export_fbx module: {e}")

    print(f"Registered {bl_info['name']} Addon")

def unregister():
    """Unregisters all addon classes and properties."""
    # Unregister in reverse order

    # export_fbx module
    try:
        from .modules.export_fbx import unregister as unregister_export_fbx_func
        unregister_export_fbx_func()
    except ImportError:
        print("export_fbx module (or its unregister function) not found during unregister.")
    except Exception as e:
        print(f"Error unregistering export_fbx module: {e}")

    # Vertex to Bone Baker module
    try:
        from .modules.vertex_to_bone_baker import unregister as unregister_vtbb_func
        unregister_vtbb_func()
    except ImportError:
        print("Vertex to Bone Baker module (or its unregister function) not found during unregister.")
    except Exception as e:
        print(f"Error unregistering Vertex to Bone Baker module: {e}")

    # Exporter module
    try:
        # from .modules.easymesh_batch_exporter import unregister as unregister_exporter_func # Old way
        # unregister_exporter_func()
        if 'easymesh_batch_exporter' in locals() and hasattr(easymesh_batch_exporter, 'unregister'):
            easymesh_batch_exporter.unregister()
        else:
            print(f"PopTools: Exporter module not loaded or has no unregister function.")
    except ImportError:
        print("Exporter module (or its unregister function) not found during unregister.")
    except Exception as e:
        print(f"Error unregistering exporter module: {e}")

    # ReTex module
    try:
        from .modules.retex import unregister as unregister_retex_func
        unregister_retex_func()
    except ImportError:
        print("ReTex module (or its unregister function) not found during unregister.")
    except Exception as e:
        print(f"Error unregistering ReTex module: {e}")
        
    # 注销插件首选项
    bpy.utils.unregister_class(PopToolsPreferences)

    print(f"Unregistered {bl_info['name']} Addon")

# For running the script directly
if __name__ == "__main__":
    register()