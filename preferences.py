# -*- coding: utf-8 -*-
"""
PopTools Preferences
插件首选项设置
"""

import bpy
from bpy.types import AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty

class PopToolsPreferences(AddonPreferences):
    """PopTools插件首选项"""
    bl_idname = __package__
    
    # 模块启用设置 / Module Enable Settings
    enable_export_tools: BoolProperty(
        name="启用导出工具",
        description="启用/禁用多格式导出工具",
        default=True
    )
    
    enable_retex_tools: BoolProperty(
        name="启用ReTex工具",
        description="启用/禁用纹理管理和重命名工具",
        default=True
    )
    
    enable_obj_export_tools: BoolProperty(
        name="启用OBJ导出工具",
        description="启用/禁用OBJ批量导出工具",
        default=True
    )
    
    enable_vertex_baker_tools: BoolProperty(
        name="启用顶点烘焙工具",
        description="启用/禁用顶点到骨骼烘焙工具",
        default=True
    )
    
    # 导出/导入工具启用选项 (兼容性)
    export_import_enable: BoolProperty(
        name="启用导出/导入工具",
        description="启用或禁用导出/导入工具面板",
        default=True,
    )
    
    # Global settings
    default_export_path: StringProperty(
        name="默认导出路径",
        description="默认的导出文件路径",
        default="",
        subtype='DIR_PATH'
    )
    
    auto_save_before_export: BoolProperty(
        name="导出前自动保存",
        description="导出前自动保存当前文件",
        default=True,
    )
    
    show_export_notifications: BoolProperty(
        name="显示导出通知",
        description="导出完成后显示通知消息",
        default=True,
    )
    
    
    def draw(self, context):
        layout = self.layout
        
        # 模块启用设置
        box = layout.box()
        box.label(text="模块设置 / Module Settings:", icon='PREFERENCES')
        
        col = box.column(align=True)
        col.prop(self, "enable_export_tools", icon='PACKAGE')
        col.prop(self, "enable_retex_tools", icon='TEXTURE')
        col.prop(self, "enable_obj_export_tools", icon='MESH_CUBE')
        col.prop(self, "enable_vertex_baker_tools", icon='MOD_VERTEX_WEIGHT')
        col.prop(self, "export_import_enable", icon='IMPORT')
        
        # Global settings section
        box = layout.box()
        box.label(text="全局设置:", icon='WORLD')
        
        col = box.column()
        col.prop(self, "default_export_path")
        col.prop(self, "auto_save_before_export")
        col.prop(self, "show_export_notifications")
        
        # UI settings section
        box = layout.box()
        box.label(text="界面设置:", icon='PREFERENCES')
        
        col = box.column()
        col.prop(self, "panel_location")
        col.prop(self, "compact_ui")
        
        # Info section
        box = layout.box()
        box.label(text="关于:", icon='INFO')
        col = box.column()
        col.label(text="PopTools - Blender工具集合")
        col.label(text="版本: 3.0.0")
        col.label(text="作者: JhonYan & Claude & Gemini")

# Registration
classes = (
    PopToolsPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)