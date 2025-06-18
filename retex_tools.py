# -*- coding: utf-8 -*-
"""
ReTex Tools - 纹理管理和重命名工具
Texture Management and Renaming Tools

提供纹理重命名、调整大小和智能对象重命名功能。
Provides texture renaming, resizing and smart object renaming functionality.
"""

import bpy
import os
import re
import math
from bpy.types import Operator, Panel
from bpy.props import BoolProperty, EnumProperty, StringProperty

# 导入工具函数
from .utils import show_message_box, get_addon_preferences
from .translation_tools import translate_text_tool, ai_translate_text_tool

# ============================================================================
# 共享UI绘制函数 / Shared UI Drawing Functions
# ============================================================================

def draw_texture_manager_ui(layout, context, show_help_section=True, show_extended_features=False):
    """共享的纹理管理UI绘制函数
    
    Args:
        layout: Blender UI布局对象
        context: Blender上下文
        show_help_section: 是否显示帮助说明部分（弹出面板可能不显示某些部分）
        show_extended_features: 是否显示扩展功能（分辨率设置和角色重命名，仅弹出面板显示）
    """
    props = context.scene.poptools_props.retex_settings
    props_main = context.scene.poptools_props
    
    # 翻译工具部分
    translate_box = layout.box()
    translate_box.label(text="翻译工具：", icon='FILE_TEXT')
    
    # 语言选择行
    lang_row = translate_box.row(align=True)
    
    # 源语言 - 占1/3
    source_col = lang_row.column()
    source_col.scale_x = 1.0
    source_col.prop(props, "translate_source_lang", text="")
    
    # 箭头标识 - 占1/3
    arrow_col = lang_row.column()
    arrow_col.scale_x = 1.0
    arrow_col.label(text="to:", icon='FORWARD')
    
    # 目标语言 - 占1/3
    target_col = lang_row.column()
    target_col.scale_x = 1.0
    target_col.prop(props, "translate_target_lang", text="")
    
    # 输入文本框
    input_row = translate_box.row()
    input_row.prop(props, "translate_input_text", text="输入内容")
    
    # 翻译按钮
    translate_row = translate_box.row()
    translate_row.operator("rt.translate_text", text="翻译", icon='ARROW_LEFTRIGHT')
    translate_row.operator("rt.ai_translate_text", text="AI翻译", icon='OUTLINER_OB_LIGHT')
    
    # 输出文本框（只有在有翻译结果时才显示）
    if props.translate_output_text:
        output_row = translate_box.row()
        output_row.prop(props, "translate_output_text", text="翻译结果")
        
        # 应用翻译结果按钮
        apply_row = translate_box.row()
        apply_row.operator("rt.apply_translation_to_objects", text="命名应用到选中物体", icon='OBJECT_DATA')
    
    # 分隔线
    layout.separator()
    
    # 打包贴图部分
    pack_box = layout.box()
    row = pack_box.row()
    row.operator("file.pack_all", text="打包贴图", icon='PACKAGE')
    row.operator("rt.unpack_textures", text="解包贴图", icon='IMPORT')
    
    # 分隔线
    layout.separator()
    
    # 获取当前勾选框的状态
    replace_prefix = props.replace_prefix
    
    # 创建行布局
    row = layout.row()
    
    # 动态设置图标
    if replace_prefix:
        icon = 'CHECKBOX_HLT'
    else:
        icon = 'CHECKBOX_DEHLT'
    
    # 添加勾选框
    row.prop(props, "replace_prefix", text="替换为'tex'前缀", icon=icon)
    
    # 添加操作按钮
    row = layout.row()
    row.operator("rt.set_texname_of_object", text="设置对象的纹理名称", icon='OBJECT_DATA')
    row = layout.row()
    row.scale_y = 1.5
    row.operator("rt.replace_textures", text="同步所有纹理", icon='FILE_REFRESH')
    
    # 扩展功能（仅在弹出面板中显示）
    if show_extended_features:
        # 添加分辨率设置
        layout.separator()
        box = layout.box()
        box.label(text="纹理分辨率：")
        row = box.row()
        row.prop(props, "resolution_preset", text="大小")
        row = layout.row()
        row.operator("rt.resize_textures", text="调整纹理大小", icon='IMAGE_DATA')
        
        # 添加海岛配方道具智能重命名部分 - 可折叠
        layout.separator()
        island_box = layout.box()
        # 标题行，包含折叠按钮
        header_row = island_box.row(align=True)
        if props_main.show_island_rename_box:
            header_row.operator("rt.toggle_island_rename_box", text="", icon='TRIA_DOWN', emboss=False)
        else:
            header_row.operator("rt.toggle_island_rename_box", text="", icon='TRIA_RIGHT', emboss=False)
        header_row.label(text="海岛配方道具智能重命名")
        
        # 只有在展开状态下才显示内容
        if props_main.show_island_rename_box:
            row = island_box.row()
            row.prop(props, "item_land", text="海岛名")
            
            # 类型标识符说明
            note_box = island_box.box()
            note_box.label(text="类型标识符说明：")
            note_box.label(text="b：气球 h：手持 p：堂食 c：头戴")
            
            # 重命名按钮
            row = island_box.row(align=True)
            row.operator("rt.smart_rename_objects", text="智能重命名选中物体", icon='OUTLINER_OB_MESH')

        # 添加角色重命名部分 - 可折叠
        layout.separator()
        char_box = layout.box()
        # 标题行，包含折叠按钮
        header_row = char_box.row(align=True)
        if props_main.show_character_rename_box:
            header_row.operator("rt.toggle_character_rename_box", text="", icon='TRIA_DOWN', emboss=False)
        else:
            header_row.operator("rt.toggle_character_rename_box", text="", icon='TRIA_RIGHT', emboss=False)
        header_row.label(text="角色重命名")

        # 添加资产表链接框
        link_box = char_box.box()
        row = link_box.row(align=True)
        row.operator("wm.url_open", text="蜂鸟角色模型资产表", icon='URL').url = "https://inspire.sg.larksuite.com/sheets/NevZs68dQhvPF4t1mQGlk77Tgrb?from=from_copylink"
        
        # 只有在展开状态下才显示内容
        if props_main.show_character_rename_box:
            # 体型控件放在单独的行
            row = char_box.row(align=True)
            row.prop(props, "character_body_type", text="体型")
            
            # 序号控件放在新的行，增加间距
            row = char_box.row(align=True)
            # 使用split创建一个更紧凑的布局
            split = row.split(factor=0.3)
            split.label(text="序号:")
            split.prop(props, "character_serial_number", text="")
            
            op_decrease = row.operator("rt.adjust_serial_number", text="", icon='TRIA_LEFT')
            op_decrease.target_property = "character_serial_number"
            op_decrease.delta = -1
            op_decrease.min_value = 1
            op_increase = row.operator("rt.adjust_serial_number", text="", icon='TRIA_RIGHT')
            op_increase.target_property = "character_serial_number"
            op_increase.delta = 1
            op_increase.min_value = 1
            
            # 添加后缀输入框
            row = char_box.row(align=True)
            split = row.split(factor=0.3)
            split.label(text="后缀:")
            split.prop(props, "character_suffix", text="")
            
            row = char_box.row(align=True)
            row.scale_y = 1.5
            row.operator("rt.rename_character_body", text="命名选中体型", icon='OBJECT_DATA')
            row.operator("rt.rename_character_hair", text="命名选中发型", icon='OBJECT_DATA')
            
            # 添加道具命名按钮
            row = char_box.row(align=True)
            row.scale_y = 1.1
            row.operator("rt.rename_character_tool", text="命名选中道具", icon='TOOL_SETTINGS')
            
            # 添加贴图后缀输入框
            row = char_box.row(align=True)
            split = row.split(factor=0.3)
            split.label(text="贴图后缀:")
            split.prop(props, "texture_suffix", text="")
            
            # 添加同步纹理命名按钮
            row = char_box.row(align=True)
            row.operator("rt.sync_texture_names", text="同步选中纹理的命名", icon='FILE_REFRESH')
            
            # 添加一键标注和清理标注按钮
            row = char_box.row(align=True)
            row.operator("rt.create_annotations", text="一键标注", icon='TEXT')
            row.operator("rt.clear_annotations", text="清理标注", icon='TRASH')
            # 添加资产表链接框
            link_box = char_box.box()
            row = link_box.row(align=True)
            row.operator("wm.url_open", text="标注提交表格", icon='URL').url = "https://inspire.sg.larksuite.com/sheets/Dim7sadLEhXobbtBoX9uFvw4s9d?from=from_copylink"
        
        # 添加动物重命名部分 - 可折叠
        layout.separator()
        animal_box = layout.box()
        # 标题行，包含折叠按钮
        header_row = animal_box.row(align=True)
        if props_main.show_animal_rename_box:
            header_row.operator("rt.toggle_animal_rename_box", text="", icon='TRIA_DOWN', emboss=False)
        else:
            header_row.operator("rt.toggle_animal_rename_box", text="", icon='TRIA_RIGHT', emboss=False)
        header_row.label(text="动物重命名")
        
        # 只有在展开状态下才显示内容
        if props_main.show_animal_rename_box:
            # 体型控件放在单独的行
            row = animal_box.row(align=True)
            row.prop(props, "animal_body_type", text="体型")
            
            # 序号控件放在新的行，增加间距
            row = animal_box.row(align=True)
            # 使用split创建一个更紧凑的布局
            split = row.split(factor=0.3)
            split.label(text="序号:")
            split.prop(props, "animal_serial_number", text="")
            op_decrease = row.operator("rt.adjust_serial_number", text="", icon='TRIA_LEFT')
            op_decrease.target_property = "animal_serial_number"
            op_decrease.delta = -1
            op_decrease.min_value = 1
            op_increase = row.operator("rt.adjust_serial_number", text="", icon='TRIA_RIGHT')
            op_increase.target_property = "animal_serial_number"
            op_increase.delta = 1
            op_increase.min_value = 1
            
            row = animal_box.row(align=True)
            row.scale_y = 1.5
            row.operator("rt.rename_animal", text="命名选中动物", icon='OBJECT_DATA')
        
        # 添加建筑重命名部分 - 可折叠
        layout.separator()
        building_box = layout.box()
        # 标题行，包含折叠按钮
        header_row = building_box.row(align=True)
        if props_main.show_building_rename_box:
            header_row.operator("rt.toggle_building_rename_box", text="", icon='TRIA_DOWN', emboss=False)
        else:
            header_row.operator("rt.toggle_building_rename_box", text="", icon='TRIA_RIGHT', emboss=False)
        header_row.label(text="建筑重命名")
        
        # 只有在展开状态下才显示内容
        if props_main.show_building_rename_box:
            # 建筑类型按钮组
            type_row = building_box.row(align=True)
            # 静态建筑按钮
            op_static = type_row.operator("rt.set_building_type", text="静态建筑", depress=(props.building_type == 'buildpart'))
            op_static.building_type = 'buildpart'
            # 动画建筑按钮
            op_anim = type_row.operator("rt.set_building_type", text="动画建筑", depress=(props.building_type == 'anibuild'))
            op_anim.building_type = 'anibuild'

            # 添加海岛数值表链接框
            link_box = building_box.box()
            row = link_box.row(align=True)
            row.operator("wm.url_open", text="海岛数值表", icon='URL').url = "https://inspire.sg.larksuite.com/sheets/OKiTsUOiPhC9HQtnqsOuILKas8e?from=from_copylink"
            
            # 海岛名输入框
            row = building_box.row(align=True)
            split = row.split(factor=0.3)
            split.label(text="海岛名:")
            split.prop(props, "building_island_name", text="")
            
            # 建筑名输入框
            row = building_box.row(align=True)
            split = row.split(factor=0.3)
            split.label(text="建筑名:")
            split.prop(props, "building_name", text="")
            
            # 重命名按钮
            row = building_box.row(align=True)
            row.scale_y = 1.5
            row.operator("rt.rename_building_objects", text="自动重命名选中建筑", icon='HOME')
            
            # 烘焙高低模自动命名
            row = building_box.row(align=True)
            row.separator()
            row = building_box.row(align=True)
            row.scale_y = 1.5
            row.operator("rt.auto_name_bake_models", text="烘焙高低模自动命名", icon='MESH_DATA')
# ============================================================================
# 操作符定义 / Operator Definitions
# ============================================================================

class RT_OT_ToggleRetexHelp(Operator):
    """切换纹理管理工具说明的显示/隐藏"""
    bl_idname = "rt.toggle_retex_help"
    bl_label = "切换说明显示"
    bl_description = "切换纹理管理工具智能重命名说明的显示/隐藏状态"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.show_retex_help = not props.show_retex_help
        return {'FINISHED'}

class RT_OT_ToggleIslandRenameBox(Operator):
    """切换海岛配方道具智能重命名框的显示/隐藏"""
    bl_idname = "rt.toggle_island_rename_box"
    bl_label = "切换海岛重命名框"
    bl_description = "切换海岛配方道具智能重命名框的展开/收起状态"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.show_island_rename_box = not props.show_island_rename_box
        return {'FINISHED'}

class RT_OT_ToggleCharacterRenameBox(Operator):
    """切换角色重命名框的显示/隐藏"""
    bl_idname = "rt.toggle_character_rename_box"
    bl_label = "切换角色重命名框"
    bl_description = "切换角色重命名框的展开/收起状态"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.show_character_rename_box = not props.show_character_rename_box
        return {'FINISHED'}

class RT_OT_ToggleAnimalRenameBox(Operator):
    """切换动物重命名框的显示/隐藏"""
    bl_idname = "rt.toggle_animal_rename_box"
    bl_label = "切换动物重命名框"
    bl_description = "切换动物重命名框的展开/收起状态"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.show_animal_rename_box = not props.show_animal_rename_box
        return {'FINISHED'}

class RT_OT_ToggleBuildingRenameBox(Operator):
    """切换建筑重命名框的显示/隐藏"""
    bl_idname = "rt.toggle_building_rename_box"
    bl_label = "切换建筑重命名框"
    bl_description = "切换建筑重命名框的展开/收起状态"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.show_building_rename_box = not props.show_building_rename_box
        return {'FINISHED'}

class RT_OT_SmartRenameObjects(Operator):
    """智能重命名物体 / Smart Rename Objects"""
    bl_idname = "rt.smart_rename_objects"
    bl_label = "智能重命名选中物体"
    bl_description = "使用智能命名模式重命名选定的对象"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        total_renamed = 0
        errors = []
        
        # 获取用户输入的ItemLand值
        props = context.scene.poptools_props.retex_settings
        item_land = props.item_land
        
        # 定义类型映射字典
        type_mapping = {
            'b': 'balloon',
            'h': 'hand',
            'p': 'prop',
            'c': 'cap',
        }
        
        if not selected_objects:
            show_message_box("请先选择要重命名的对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        for obj in selected_objects:
            old_name = obj.name
            
            # 使用更智能的正则表达式匹配模式：提取任何包含字母和数字的关键参数
            # 支持字母+数字或数字+字母的灵活格式
            match_letter_first = re.search(r'([a-zA-Z]+).*?(\d+)', old_name)
            match_number_first = re.search(r'(\d+).*?([a-zA-Z]+)', old_name)
            
            type_prefix = None
            number = None
            
            if match_letter_first:
                type_prefix = match_letter_first.group(1).lower()
                number = match_letter_first.group(2)
            elif match_number_first:
                type_prefix = match_number_first.group(2).lower()
                number = match_number_first.group(1)
            
            if type_prefix and number:
                
                # 检查是否为已知类型
                if type_prefix in type_mapping:
                    type_name = type_mapping[type_prefix]
                    new_name = f"mesh_item_{item_land}_{type_name}_{number:0>2}"
                    
                    # 检查新名称是否已存在
                    if new_name in bpy.data.objects:
                        errors.append(f"对象 '{old_name}' 重命名失败：名称 '{new_name}' 已存在")
                        continue
                    
                    obj.name = new_name
                    total_renamed += 1
                else:
                    errors.append(f"对象 '{old_name}' 重命名失败：未知类型前缀 '{type_prefix}'")
            else:
                errors.append(f"对象 '{old_name}' 重命名失败：名称中未找到有效的字母和数字组合")
        
        # 显示结果
        if total_renamed > 0:
            message = f"成功重命名 {total_renamed} 个对象"
            if errors:
                message += f"\n\n错误：\n" + "\n".join(errors)
            show_message_box(message, "重命名完成", 'INFO')
        else:
            message = "没有对象被重命名"
            if errors:
                message += f"\n\n错误：\n" + "\n".join(errors)
            show_message_box(message, "重命名失败", 'ERROR')
        
        return {'FINISHED'}

class RT_OT_RenameTextures(Operator):
    """重命名纹理 / Rename Textures"""
    bl_idname = "rt.rename_textures"
    bl_label = "重命名纹理"
    bl_description = "批量重命名选中对象的纹理"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = context.selected_objects
        
        if not selected_objects:
            show_message_box("请先选择要处理的对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        renamed_count = 0
        
        for obj in selected_objects:
            if obj.type == 'MESH' and obj.data.materials:
                for material in obj.data.materials:
                    if material and material.use_nodes:
                        for node in material.node_tree.nodes:
                            if node.type == 'TEX_IMAGE' and node.image:
                                old_name = node.image.name
                                
                                if props.replace_prefix:
                                    # 替换为tex前缀
                                    new_name = re.sub(r'^[^_]*_', 'tex_', old_name)
                                else:
                                    # 保持原有前缀
                                    new_name = old_name
                                
                                if new_name != old_name:
                                    node.image.name = new_name
                                    renamed_count += 1
        
        show_message_box(f"成功重命名 {renamed_count} 个纹理", "重命名完成", 'INFO')
        return {'FINISHED'}

class RT_OT_ResizeTextures(Operator):
    """调整纹理大小 / Resize Textures"""
    bl_idname = "rt.resize_textures"
    bl_label = "调整纹理大小"
    bl_description = "将选定的纹理调整为指定的分辨率并自动保存到Small文件夹"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = bpy.context.selected_objects
        total_resized = 0
        total_skipped = 0
        total_saved = 0
        errors = []
        
        if not selected_objects:
            show_message_box("请先选择要处理的对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        # 获取目标分辨率
        target_size = int(props.resolution_preset)

        # 处理的图像列表，用于避免重复处理同一图像
        processed_images = set()

        # 收集所有需要处理的图像
        images_to_process = []
        for obj in selected_objects:
            if obj.material_slots:
                material_slot = obj.material_slots[0]
                material = material_slot.material
                if material and material.node_tree:
                    for node in material.node_tree.nodes:
                        if node.type == 'TEX_IMAGE':
                            image = node.image
                            if image and image.name not in processed_images:
                                # 记录已处理的图像
                                processed_images.add(image.name)
                                # 添加到待处理列表
                                images_to_process.append(image)
        
        # 如果没有找到任何图像，提前返回
        if not images_to_process:
            show_message_box("未找到任何可处理的纹理！请确保选中的对象包含有效的纹理。", "警告", 'WARNING')
            return {'CANCELLED'}
        
        # 处理每个图像
        for image in images_to_process:
            try:
                # 检查图像是否有数据
                if not image.has_data:
                    # 尝试重新加载图像
                    try:
                        # 先卸载图像再重新加载
                        image.reload()
                    except:
                        pass
                    
                    # 再次检查图像是否有数据
                    if not image.has_data:
                        total_skipped += 1
                        continue
                
                # 调整图像分辨率
                image.scale(target_size, target_size)
                total_resized += 1
                
                # 自动保存到Small文件夹
                try:
                    # 获取原始图像路径
                    original_path = bpy.path.abspath(image.filepath)
                    if original_path:
                        # 获取文件名和扩展名
                        filename = os.path.basename(original_path)
                        directory = os.path.dirname(original_path)
                        
                        # 获取根目录
                        root_dir = directory

                        # 创建Small文件夹（如果不存在）
                        small_dir = os.path.join(root_dir, "Small")
                        if not os.path.exists(small_dir):
                            os.makedirs(small_dir)
                        
                        # 构建新的保存路径
                        save_path = os.path.join(small_dir, filename)
                        
                        # 保存图像
                        image.filepath_raw = save_path
                        image.save()
                        total_saved += 1
                except Exception as e:
                    errors.append(f"保存失败：{image.name}\n错误信息：{str(e)}")
                
            except Exception as e:
                # 提供更详细的错误信息
                error_msg = str(e)
                if "does not have any image data" in error_msg:
                    errors.append(f"处理失败：{image.name}\n错误信息：图像没有数据，请确保图像已正确加载。尝试在Blender中打开图像编辑器并手动加载该图像。")
                else:
                    errors.append(f"处理失败：{image.name}\n错误信息：{error_msg}")

        # 操作完成后显示结果
        if total_resized > 0:
            success_msg = f"成功调整 {total_resized} 个纹理的分辨率到 {target_size}x{target_size}！"
            if total_saved > 0:
                success_msg += f"并保存 {total_saved} 个纹理到Small文件夹。"
            if total_skipped > 0:
                success_msg += f"跳过 {total_skipped} 个没有图像数据的纹理。"
            show_message_box(success_msg, "调整完成", 'INFO')
        elif total_skipped > 0:
            show_message_box(f"没有纹理被调整，跳过了 {total_skipped} 个没有图像数据的纹理。", "警告", 'WARNING')
        else:
            show_message_box("未找到任何可处理的纹理！", "警告", 'WARNING')
            
        if errors:
            error_msg = "\n".join(errors)
            show_message_box(f"错误信息：\n{error_msg}", "处理错误", 'ERROR')

        return {'FINISHED'}

class RT_OT_AddCustomBodyType(Operator):
    """添加自定义体型 / Add Custom Body Type"""
    bl_idname = "rt.add_custom_body_type"
    bl_label = "添加自定义体型"
    bl_description = "添加新的自定义体型到列表中"
    bl_options = {'REGISTER', 'UNDO'}
    
    new_body_type: StringProperty(
        name="新体型名称",
        description="输入新的体型名称",
        default=""
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        
        if not self.new_body_type.strip():
            show_message_box("请输入有效的体型名称", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 获取现有的自定义体型
        existing_types = [t.strip() for t in props.custom_body_types.split(',') if t.strip()]
        
        # 检查是否已存在
        if self.new_body_type in existing_types:
            show_message_box(f"体型 '{self.new_body_type}' 已存在", "警告", 'WARNING')
            return {'CANCELLED'}
        
        # 添加新体型
        existing_types.append(self.new_body_type)
        props.custom_body_types = ','.join(existing_types)
        
        show_message_box(f"成功添加体型 '{self.new_body_type}'", "添加完成", 'INFO')
        return {'FINISHED'}

class RT_OT_SetTexnameOfObject(Operator):
    """设置对象的纹理名称 / Set Texture Name of Object"""
    bl_idname = "rt.set_texname_of_object"
    bl_label = "设置对象的纹理名称"
    bl_description = "根据选定对象的名称重命名纹理"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        total_renamed = 0
        errors = []
        props = context.scene.poptools_props.retex_settings
        
        for obj in selected_objects:
            if obj.material_slots:
                material_slot = obj.material_slots[0]
                material = material_slot.material
                if material and material.node_tree:
                    for node in material.node_tree.nodes:
                        if node.type == 'TEX_IMAGE':
                            image = node.image
                            if image:
                                try:
                                    # 获取图片文件路径
                                    filepath = bpy.path.abspath(image.filepath)
                                    if not filepath:
                                        continue
                                        
                                    # 获取目录和扩展名
                                    directory = os.path.dirname(filepath)
                                    extension = os.path.splitext(filepath)[1]
                                    
                                    # 构建新的文件名
                                    new_name = obj.name
                                    
                                    # 添加后缀（如果有的话）
                                    if hasattr(props, 'texture_suffix') and props.texture_suffix:
                                        new_name = f"{new_name}_{props.texture_suffix}"
                                    
                                    if props.replace_prefix:
                                        # 检查是否已有前缀，如果有则替换为tex_，否则添加tex_前缀
                                        prefix_match = re.match(r'^([a-zA-Z]+)_(.+)$', new_name)
                                        if prefix_match:
                                            # 替换现有前缀
                                            new_name = "tex_" + prefix_match.group(2)
                                        else:
                                            # 添加前缀
                                            new_name = "tex_" + new_name
                                        
                                    new_filepath = os.path.join(directory, new_name + extension)
                                    
                                    # 如果新文件名已存在，添加数字后缀
                                    counter = 1
                                    while os.path.exists(new_filepath) and new_filepath != filepath:
                                        base_name = obj.name
                                        new_name = f"{base_name}_{counter}"
                                        
                                        # 添加后缀（如果有的话）
                                        if hasattr(props, 'texture_suffix') and props.texture_suffix:
                                            new_name = f"{new_name}_{props.texture_suffix}"
                                        
                                        if props.replace_prefix:
                                            # 检查是否已有前缀，如果有则替换为tex_，否则添加tex_前缀
                                            prefix_match = re.match(r'^([a-zA-Z]+)_(.+)$', new_name)
                                            if prefix_match:
                                                # 替换现有前缀
                                                new_name = "tex_" + prefix_match.group(2)
                                            else:
                                                # 添加前缀
                                                new_name = "tex_" + new_name
                                        new_filepath = os.path.join(directory, new_name + extension)
                                        counter += 1
                                    
                                    # 重命名文件
                                    if filepath != new_filepath:
                                        os.rename(filepath, new_filepath)
                                        image.filepath = new_filepath
                                        image.name = new_name
                                        total_renamed += 1
                                        
                                except Exception as e:
                                    errors.append(f"重命名失败：{image.name}\n错误信息：{str(e)}")
        
        # 操作完成后显示结果
        if total_renamed > 0:
            show_message_box(f"成功重命名 {total_renamed} 个纹理！", "重命名完成", 'INFO')
        if errors:
            error_msg = "\n".join(errors)
            show_message_box(f"错误信息：\n{error_msg}", "重命名错误", 'ERROR')
            
        return {'FINISHED'}

class RT_OT_UnpackTextures(Operator):
    """解包所有贴图 / Unpack All Textures"""
    bl_idname = "rt.unpack_textures"
    bl_label = "解包所有贴图"
    bl_description = "将所有打包的贴图文件解包到当前目录（覆盖现有文件）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.file.unpack_all(method='WRITE_LOCAL')
        show_message_box("所有贴图已解包到当前目录", "解包完成", 'INFO')
        return {'FINISHED'}

class RT_OT_AdjustSerialNumber(Operator):
    """调整序号 / Adjust Serial Number"""
    bl_idname = "rt.adjust_serial_number"
    bl_label = "调整序号"
    bl_description = "增加或减少序号"
    bl_options = {'REGISTER', 'UNDO'}

    target_property: StringProperty(
        name="目标属性",
        description="要修改的场景属性的名称 (例如 'character_serial_number')"
    )

    delta: bpy.props.IntProperty(
        name="变化量",
        description="增加或减少的值 (例如 1 或 -1)",
        default=1
    )

    min_value: bpy.props.IntProperty(
        name="最小值",
        description="序号的最小值",
        default=1
    )

    def execute(self, context):
        if not self.target_property:
            show_message_box("未指定目标属性", "错误", 'ERROR')
            return {'CANCELLED'}

        try:
            props = context.scene.poptools_props.retex_settings
            current_value_str = getattr(props, self.target_property)
            try:
                current_value_int = int(current_value_str)
            except ValueError:
                show_message_box(f"当前序号 '{current_value_str}' 不是一个有效的数字。", "错误", 'ERROR')
                return {'CANCELLED'}

            new_value_int = current_value_int + self.delta
            new_value_int = max(new_value_int, self.min_value) # Apply min_value constraint

            # Properties like character_serial_number are expected to be strings like "01"
            if self.target_property in ["character_serial_number", "animal_serial_number"]:
                new_value_str = f"{new_value_int:02d}"
                setattr(props, self.target_property, new_value_str)
            else:
                # For other potential target_properties, assuming they should also be stored as strings.
                setattr(props, self.target_property, str(new_value_int))
        except AttributeError:
            show_message_box(f"属性 '{self.target_property}' 不存在", "错误", 'ERROR')
            return {'CANCELLED'}
        except Exception as e:
            show_message_box(f"调整序号时出错: {str(e)}", "错误", 'ERROR')
            return {'CANCELLED'}
        
        return {'FINISHED'}

class RT_OT_ReplaceTextures(Operator):
    """替换所有纹理 / Replace All Textures"""
    bl_idname = "rt.replace_textures"
    bl_label = "替换所有纹理"
    bl_description = "将所有外部文件夹内的纹理名称与blender内的名称同步"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        total_renamed = 0
        errors = []
        props = context.scene.poptools_props.retex_settings
        
        # 遍历所有图片
        for image in bpy.data.images:
            if image.filepath:
                try:
                    # 获取图片文件路径
                    filepath = bpy.path.abspath(image.filepath)
                    if not filepath or not os.path.exists(filepath):
                        continue
                        
                    # 获取目录和扩展名
                    directory = os.path.dirname(filepath)
                    extension = os.path.splitext(filepath)[1]
                    
                    # 构建新的文件名
                    new_name = image.name
                    if props.replace_prefix:
                        # 检查是否已有前缀，如果有则替换为tex_，否则添加tex_前缀
                        prefix_match = re.match(r'^([a-zA-Z]+)_(.+)$', new_name)
                        if prefix_match:
                            # 替换现有前缀
                            new_name = "tex_" + prefix_match.group(2)
                        elif not new_name.startswith("tex_"):
                            # 添加前缀
                            new_name = "tex_" + new_name
                            
                    new_filepath = os.path.join(directory, new_name + extension)
                    
                    # 如果新文件名已存在，添加数字后缀
                    counter = 1
                    while os.path.exists(new_filepath) and new_filepath != filepath:
                        base_name = new_name.rsplit('_', 1)[0] if '_' in new_name else new_name
                        new_name = f"{base_name}_{counter}"
                        new_filepath = os.path.join(directory, new_name + extension)
                        counter += 1
                    
                    # 重命名文件
                    if filepath != new_filepath:
                        os.rename(filepath, new_filepath)
                        image.filepath = new_filepath
                        total_renamed += 1
                        
                except Exception as e:
                    errors.append(f"重命名失败：{image.name}\n错误信息：{str(e)}")
        
        # 操作完成后显示结果
        if total_renamed > 0:
            show_message_box(f"成功重命名 {total_renamed} 个纹理！", "重命名完成", 'INFO')
        if errors:
            error_msg = "\n".join(errors)
            show_message_box(f"错误信息：\n{error_msg}", "重命名错误", 'ERROR')
            
        return {'FINISHED'}

class RT_OT_RenameCharacterBody(Operator):
    """命名选中体型 / Rename Character Body"""
    bl_idname = "rt.rename_character_body"
    bl_label = "命名选中体型"
    bl_description = "根据选择的体型和序号重命名选中的角色模型"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = bpy.context.selected_objects
        body_type = props.character_body_type
        serial_number = props.character_serial_number

        if not selected_objects:
            show_message_box("没有选中的模型", "警告", 'WARNING')
            return {'CANCELLED'}

        if not serial_number.isdigit():
            show_message_box("序号必须是数字", "错误", 'ERROR')
            return {'CANCELLED'}

        renamed_count = 0
        for obj in selected_objects:
            if obj.type == 'MESH':
                # 获取后缀
                suffix = props.character_suffix
                # 构建新名称
                base_name = f"mesh_characters_{body_type}_{serial_number}"
                new_name = f"{base_name}_{suffix}" if suffix else base_name
                obj.name = new_name
                # 同步设置物体的data name
                if obj.data:
                    obj.data.name = new_name
                renamed_count += 1
        
        if renamed_count > 0:
            show_message_box(f"成功重命名 {renamed_count} 个体型模型", "重命名完成", 'INFO')
        else:
            show_message_box("没有符合条件的模型被重命名", "重命名完成", 'INFO')
        return {'FINISHED'}

class RT_OT_RenameAnimal(Operator):
    """命名选中动物 / Rename Animal"""
    bl_idname = "rt.rename_animal"
    bl_label = "命名选中动物"
    bl_description = "根据选择的动物体型和序号重命名选中的动物模型"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = bpy.context.selected_objects
        body_type = props.animal_body_type
        serial_number = props.animal_serial_number

        if not selected_objects:
            show_message_box("没有选中的模型", "警告", 'WARNING')
            return {'CANCELLED'}

        if not serial_number.isdigit():
            show_message_box("序号必须是数字", "错误", 'ERROR')
            return {'CANCELLED'}

        renamed_count = 0
        for obj in selected_objects:
            if obj.type == 'MESH':
                # 获取后缀 (动物重命名也使用角色后缀，如果需要区分，可以添加新的动物后缀属性)
                suffix = props.character_suffix # 或者创建一个 animal_suffix
                # 构建新名称
                base_name = f"mesh_animals_{body_type}_{serial_number}"
                new_name = f"{base_name}_{suffix}" if suffix else base_name
                obj.name = new_name
                # 同步设置物体的data name
                if obj.data:
                    obj.data.name = new_name
                renamed_count += 1
        
        if renamed_count > 0:
            show_message_box(f"成功重命名 {renamed_count} 个动物模型", "重命名完成", 'INFO')
        else:
            show_message_box("没有符合条件的模型被重命名", "重命名完成", 'INFO')
        return {'FINISHED'}

class RT_OT_SyncTextureNames(Operator):
    """同步纹理命名 / Sync Texture Names"""
    bl_idname = "rt.sync_texture_names"
    bl_label = "同步纹理命名"
    bl_description = "设置对象的纹理名称并同步所有纹理"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # 首先执行设置对象的纹理名称功能
        bpy.ops.rt.set_texname_of_object('INVOKE_DEFAULT')
        
        # 然后执行同步所有纹理功能
        bpy.ops.rt.replace_textures('INVOKE_DEFAULT')
        
        return {'FINISHED'}

class RT_OT_RenameCharacterHair(Operator):
    """命名选中发型 / Rename Character Hair"""
    bl_idname = "rt.rename_character_hair"
    bl_label = "命名选中发型"
    bl_description = "根据选择的体型和序号重命名选中的发型模型"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = bpy.context.selected_objects
        body_type = props.character_body_type
        serial_number = props.character_serial_number

        if not selected_objects:
            show_message_box("没有选中的模型", "警告", 'WARNING')
            return {'CANCELLED'}

        if not serial_number.isdigit():
            show_message_box("序号必须是数字", "错误", 'ERROR')
            return {'CANCELLED'}

        renamed_count = 0
        for obj in selected_objects:
            if obj.type == 'MESH':
                # 获取后缀
                suffix = props.character_suffix
                # 构建新名称
                base_name = f"mesh_head_{body_type}_head{serial_number}"
                new_name = f"{base_name}_{suffix}" if suffix else base_name
                obj.name = new_name
                # 同步设置物体的data name
                if obj.data:
                    obj.data.name = new_name
                renamed_count += 1
        
        if renamed_count > 0:
            show_message_box(f"成功重命名 {renamed_count} 个发型模型", "重命名完成", 'INFO')
        else:
            show_message_box("没有符合条件的模型被重命名", "重命名完成", 'INFO')
        return {'FINISHED'}

class RT_OT_RenameCharacterTool(Operator):
    """命名选中道具 / Rename Character Tool"""
    bl_idname = "rt.rename_character_tool"
    bl_label = "命名选中道具"
    bl_description = "根据选择的体型和序号重命名选中的道具模型"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = bpy.context.selected_objects
        body_type = props.character_body_type
        serial_number = props.character_serial_number

        if not selected_objects:
            show_message_box("没有选中的模型", "警告", 'WARNING')
            return {'CANCELLED'}

        if not serial_number.isdigit():
            show_message_box("序号必须是数字", "错误", 'ERROR')
            return {'CANCELLED'}

        # 确定使用的后缀，优先使用贴图后缀
        texture_suffix = props.texture_suffix.strip()
        character_suffix = props.character_suffix.strip()
        
        if texture_suffix:
            suffix = texture_suffix
        elif character_suffix:
            suffix = character_suffix
        else:
            show_message_box("请输入角色序号后缀", "错误", 'ERROR')
            return {'CANCELLED'}

        renamed_count = 0
        for obj in selected_objects:
            if obj.type == 'MESH':
                # 构建新名称：mesh_tool_体型_序号后缀
                new_name = f"mesh_buildtools_{body_type}_{serial_number}{suffix}"
                obj.name = new_name
                # 同步设置物体的data name
                if obj.data:
                    obj.data.name = new_name
                renamed_count += 1
        
        if renamed_count > 0:
            show_message_box(f"成功重命名 {renamed_count} 个道具模型", "重命名完成", 'INFO')
        else:
            show_message_box("没有符合条件的模型被重命名", "重命名完成", 'INFO')
        return {'FINISHED'}

class RT_OT_RenameBuildingObjects(Operator):
    """建筑重命名 / Rename Building Objects"""
    bl_idname = "rt.rename_building_objects"
    bl_label = "建筑重命名"
    bl_description = "使用建筑命名规则重命名选定的对象"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        props = context.scene.poptools_props.retex_settings
        
        # 获取用户输入
        building_type = props.building_type
        island_name = props.building_island_name.strip()
        building_name = props.building_name.strip()
        
        # 验证输入
        if not island_name:
            show_message_box("请输入海岛名称", "输入错误", 'ERROR')
            return {'CANCELLED'}
        
        if not building_name:
            show_message_box("请输入建筑名称", "输入错误", 'ERROR')
            return {'CANCELLED'}
        
        if not selected_objects:
            show_message_box("请先选择要重命名的对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        # 过滤出网格对象
        mesh_objects = [obj for obj in selected_objects if obj.type == 'MESH']
        
        if not mesh_objects:
            show_message_box("选中的对象中没有网格对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        total_renamed = 0
        errors = []
        
        # 自动递增序号，从01开始
        serial_number = 1
        
        for obj in mesh_objects:
            # 生成基础名称模板
            base_name = f"mesh_{building_type}_{island_name}_{building_name}"
            
            # 查找可用的序号
            while True:
                serial_str = f"{serial_number:02d}"  # 格式化为两位数字，如01, 02
                new_name = f"{base_name}{serial_str}"
                
                # 检查新名称是否已存在
                if new_name not in bpy.data.objects:
                    break
                serial_number += 1
            
            try:
                # 重命名对象
                old_name = obj.name
                obj.name = new_name
                
                # 同时重命名对象数据（网格数据）
                if obj.data:
                    obj.data.name = new_name
                
                total_renamed += 1
                serial_number += 1  # 为下一个对象准备序号
                
            except Exception as e:
                errors.append(f"对象 '{obj.name}' 重命名失败：{str(e)}")
                serial_number += 1  # 即使失败也要递增序号
        
        # 显示结果
        if total_renamed > 0:
            message = f"成功重命名 {total_renamed} 个建筑对象"
            if errors:
                message += f"\n\n警告：\n" + "\n".join(errors)
            show_message_box(message, "重命名完成", 'INFO')
        else:
            message = "没有对象被重命名"
            if errors:
                message += f"\n\n错误：\n" + "\n".join(errors)
            show_message_box(message, "重命名失败", 'ERROR')
        
        return {'FINISHED'}

class RT_OT_SetBuildingType(Operator):
    """设置建筑类型 / Set Building Type"""
    bl_idname = "rt.set_building_type"
    bl_label = "设置建筑类型"
    bl_description = "设置当前选择的建筑类型"
    bl_options = {'REGISTER', 'UNDO'}
    
    building_type: StringProperty(
        name="建筑类型",
        description="要设置的建筑类型",
        default="buildpart"
    )
    
    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        props.building_type = self.building_type
        return {'FINISHED'}

# 移除RT_OT_SetBuildingSerial类，序号现在自动递增

class RT_OT_AutoNameBakeModels(Operator):
    """烘焙高低模自动命名 / Auto Name Bake Models"""
    bl_idname = "rt.auto_name_bake_models"
    bl_label = "烘焙高低模自动命名"
    bl_description = "自动识别高低模并按烘焙命名规则重命名"
    bl_options = {'REGISTER', 'UNDO'}
    
    def get_face_count(self, obj):
        """获取对象的面数"""
        if obj.type == 'MESH' and obj.data:
            return len(obj.data.polygons)
        return 0
    
    def has_subdivision_modifier(self, obj):
        """检查对象是否有细分修改器"""
        if obj.modifiers:
            for modifier in obj.modifiers:
                if modifier.type == 'SUBSURF':
                    return True
        return False
    
    def classify_models(self, objects):
        """分类高模和低模"""
        if not objects:
            return [], []
        
        # 计算所有对象的面数
        face_counts = [(obj, self.get_face_count(obj)) for obj in objects if obj.type == 'MESH']
        
        if not face_counts:
            return [], []
        
        # 计算平均面数作为分界线
        total_faces = sum(count for _, count in face_counts)
        avg_faces = total_faces / len(face_counts)
        
        high_poly = []
        low_poly = []
        
        for obj, face_count in face_counts:
            # 判断高模条件：面数高于平均值或有细分修改器
            if face_count > avg_faces or self.has_subdivision_modifier(obj):
                high_poly.append(obj)
            else:
                low_poly.append(obj)
        
        return high_poly, low_poly
    
    def get_next_bake_number(self):
        """获取下一个可用的Bake编号"""
        existing_names = [obj.name for obj in bpy.data.objects]
        bake_num = 1
        
        while True:
            bake_prefix = f"Bake{bake_num:02d}"
            # 检查是否存在以此前缀开头的对象
            if not any(name.startswith(bake_prefix) for name in existing_names):
                return bake_num
            bake_num += 1
    
    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        
        if not selected_objects:
            show_message_box("请先选择要重命名的对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        # 过滤出网格对象
        mesh_objects = [obj for obj in selected_objects if obj.type == 'MESH']
        
        if not mesh_objects:
            show_message_box("请选择至少一个网格对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        # 分类高模和低模
        high_poly, low_poly = self.classify_models(mesh_objects)
        
        if not high_poly and not low_poly:
            show_message_box("无法识别高模或低模", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 获取Bake编号
        bake_num = self.get_next_bake_number()
        bake_prefix = f"Bake{bake_num:02d}"
        
        total_renamed = 0
        errors = []
        
        # 重命名高模
        if high_poly:
            if len(high_poly) == 1 and len(low_poly) == 1:
                # 简单情况：一个高模一个低模
                new_name = f"{bake_prefix}_high"
                try:
                    high_poly[0].name = new_name
                    if high_poly[0].data:
                        high_poly[0].data.name = new_name
                    total_renamed += 1
                except Exception as e:
                    errors.append(f"高模重命名失败：{str(e)}")
            else:
                # 复杂情况：多个高模
                for i, obj in enumerate(high_poly):
                    suffix = chr(ord('a') + i)  # a, b, c, ...
                    new_name = f"{bake_prefix}_high_{suffix}"
                    try:
                        obj.name = new_name
                        if obj.data:
                            obj.data.name = new_name
                        total_renamed += 1
                    except Exception as e:
                        errors.append(f"高模 {obj.name} 重命名失败：{str(e)}")
        
        # 重命名低模
        if low_poly:
            if len(high_poly) == 1 and len(low_poly) == 1:
                # 简单情况：一个高模一个低模
                new_name = f"{bake_prefix}_low"
                try:
                    low_poly[0].name = new_name
                    if low_poly[0].data:
                        low_poly[0].data.name = new_name
                    total_renamed += 1
                except Exception as e:
                    errors.append(f"低模重命名失败：{str(e)}")
            else:
                # 复杂情况：多个低模
                for i, obj in enumerate(low_poly):
                    suffix = chr(ord('a') + i)  # a, b, c, ...
                    new_name = f"{bake_prefix}_low_{suffix}"
                    try:
                        obj.name = new_name
                        if obj.data:
                            obj.data.name = new_name
                        total_renamed += 1
                    except Exception as e:
                        errors.append(f"低模 {obj.name} 重命名失败：{str(e)}")
        
        # 显示结果
        if total_renamed > 0:
            message = f"成功重命名 {total_renamed} 个模型\n高模: {len(high_poly)} 个\n低模: {len(low_poly)} 个\n使用编号: {bake_prefix}"
            if errors:
                message += f"\n\n警告：\n" + "\n".join(errors)
            show_message_box(message, "重命名完成", 'INFO')
        else:
            message = "没有对象被重命名"
            if errors:
                message += f"\n\n错误：\n" + "\n".join(errors)
            show_message_box(message, "重命名失败", 'ERROR')
        
        return {'FINISHED'}

class RT_OT_OrganizeSelectedMaterials(Operator):
    """一键整理选中模型材质 / Organize Selected Materials"""
    bl_idname = "rt.organize_selected_materials"
    bl_label = "一键整理选中模型材质"
    bl_description = "删除选中模型所有材质并以模型名创建新材质"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        if not selected_objects:
            show_message_box("没有选中的模型", "警告", 'WARNING')
            return {'CANCELLED'}

        for obj in selected_objects:
            if obj.type == 'MESH':
                # 清空所有材质槽
                if obj.data.materials:
                    obj.data.materials.clear()
                else:
                    # 如果没有材质槽，确保对象数据存在
                    if not obj.data:
                        obj.data = bpy.data.meshes.new(obj.name + "_data")

                # 创建新材质
                new_mat_name = obj.name
                new_mat = bpy.data.materials.new(name=new_mat_name)
                new_mat.use_nodes = True  # 默认启用节点
                obj.data.materials.append(new_mat)
        
        show_message_box(f"成功为 {len(selected_objects)} 个选中模型整理了材质", "整理完成", 'INFO')
        return {'FINISHED'}

class RT_OT_CheckUVs(Operator):
    """一键检查UV / Check UVs"""
    bl_idname = "rt.check_uvs"
    bl_label = "一键检查UV"
    bl_description = "检查场景中所有模型，列出拥有多个UV Map的模型"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        objects_with_multiple_uvs = []

        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.data and hasattr(obj.data, 'uv_layers'):
                if len(obj.data.uv_layers) > 1:
                    objects_with_multiple_uvs.append(obj.name)
        
        props.uv_check_triggered = True # 标记检查已执行
        if objects_with_multiple_uvs:
            # uv_check_results 是一个 StringProperty，所以我们将列表转换为字符串
            # 在 panels.py 中，我们期望的是一个可以迭代的列表或一个特殊标记
            # 为了与 panels.py 中的逻辑兼容，如果存在多个UV的模型，我们将它们的名字用换行符连接成一个字符串
            # 如果没有，则使用特殊标记 "NO_DUPLICATES"
            props.uv_check_results = "\n".join(objects_with_multiple_uvs)
            show_message_box(f"发现 {len(objects_with_multiple_uvs)} 个模型有多个UV Map", "检查完成", 'WARNING')
        else:
            props.uv_check_results = "所有模型UV正常，无重复UV Map" # 特殊标记，表示没有问题
            show_message_box("所有模型UV正常，无重复UV Map", "检查完成", 'INFO')
            
        # 强制UI刷新以显示结果
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'UI':
                        region.tag_redraw()
                        break
                break
        return {'FINISHED'}

class RT_OT_CreateAnnotations(Operator):
    """一键标注 / Create Annotations"""
    bl_idname = "rt.create_annotations"
    bl_label = "一键标注"
    bl_description = "为选定模型创建文本标注"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        if not selected_objects:
            self.report({'WARNING'}, "没有选中的模型")
            return {'CANCELLED'}

        # 检查或创建Text合集
        text_collection_name = "Text"
        text_collection = bpy.data.collections.get(text_collection_name)
        if not text_collection:
            text_collection = bpy.data.collections.new(text_collection_name)
            bpy.context.scene.collection.children.link(text_collection)
            # 设置合集颜色为绿色 (COLOR_04)
            text_collection.color_tag = 'COLOR_04'

        # 加载字体
        try:
            font_curve = bpy.data.fonts.load("C:\\Windows\\Fonts\\ariblk.ttf") # Arial Black
        except RuntimeError:
            self.report({'WARNING'}, "无法加载 Arial Black 字体，请确保已安装。将使用默认字体。")
            try:
                font_curve = bpy.data.fonts.load("arial.ttf") # Fallback
            except RuntimeError:
                font_curve = bpy.data.fonts[0] if bpy.data.fonts else None # Last resort
                if not font_curve:
                    self.report({'ERROR'}, "无法加载任何字体")
                    return {'CANCELLED'}

        for obj in selected_objects:
            if obj.type != 'MESH': # 只处理网格物体
                continue

            # 创建文本对象
            text_data = bpy.data.curves.new(name=f"{obj.name}_label_data", type='FONT')
            text_data.body = obj.name
            text_data.font = font_curve
            text_data.align_x = 'CENTER'
            text_data.align_y = 'CENTER'

            text_object = bpy.data.objects.new(name=f"{obj.name}_label", object_data=text_data)
            
            # 将文本对象链接到Text合集
            # 首先从场景主合集中取消链接（如果存在）
            if text_object.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(text_object)
            # 链接到目标合集
            if text_object.name not in text_collection.objects:
                 text_collection.objects.link(text_object)

            # 设置变换
            name_parts = obj.name.lower().split('_')
            obj_type = ""
            if len(name_parts) > 1:
                obj_type = name_parts[1] # 例如 'mesh_character_body_01' -> 'character'

            if obj_type == "characters":
                text_object.location = (0, obj.location.y, obj.location.z + 0.006)
                text_object.rotation_euler = (math.radians(90), 0, 0)
                text_object.scale = (0.2, 0.2, 0.2)
            elif obj_type == "head":
                text_object.location = (0, obj.location.y, obj.location.z + 1.0)
                text_object.rotation_euler = (math.radians(90), 0, 0)
                text_object.scale = (0.2, 0.2, 0.2)
            else: # 默认变换或可以根据其他类型调整
                text_object.location = (0, obj.location.y, obj.location.z + 0.5) # 默认值
                text_object.rotation_euler = (math.radians(90), 0, 0)
                text_object.scale = (0.2, 0.2, 0.2)
            
            # 设置视图显示属性 In Front
            text_object.show_in_front = True

        self.report({'INFO'}, f"成功为 {len(selected_objects)} 个模型创建标注")
        return {'FINISHED'}

class RT_OT_ClearAnnotations(Operator):
    """清理标注 / Clear Annotations"""
    bl_idname = "rt.clear_annotations"
    bl_label = "清理标注"
    bl_description = "删除Text合集下的所有标注对象"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        text_collection_name = "Text"
        text_collection = bpy.data.collections.get(text_collection_name)

        if not text_collection:
            self.report({'INFO'}, "未找到 'Text' 合集，无需清理。")
            return {'CANCELLED'}

        objects_to_remove = [obj for obj in text_collection.objects]
        count = len(objects_to_remove)

        if not objects_to_remove:
            self.report({'INFO'}, "'Text' 合集为空，无需清理。")
            return {'FINISHED'}

        for obj in objects_to_remove:
            bpy.data.objects.remove(obj, do_unlink=True)
        
        self.report({'INFO'}, f"成功清理 {count} 个标注对象。")
        return {'FINISHED'}

# ============================================================================
# 面板定义 / Panel Definitions
# ============================================================================

class RT_OT_TextureManagerPopup(Operator):
    """纹理管理弹出面板 / Texture Manager Popup Panel"""
    bl_idname = "rt.texture_manager_popup"
    bl_label = "角色纹理重命名"
    bl_description = "打开纹理管理弹出面板"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        return context.window_manager.invoke_popup(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        # 调用共享的UI绘制函数，弹出面板不显示帮助说明但显示扩展功能
        draw_texture_manager_ui(layout, context, show_help_section=False, show_extended_features=True)

class RT_PT_TextureRenamerPanel(Panel):
    """纹理管理面板 / Texture Management Panel"""
    bl_label = "角色纹理重命名"
    bl_idname = "RT_PT_TextureRenamerPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PopTools'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_retex_tools

    def draw(self, context):
        layout = self.layout
        
        # 调用共享的UI绘制函数，固定面板显示帮助说明和所有扩展功能
        draw_texture_manager_ui(layout, context, show_help_section=True, show_extended_features=True)

# 3DCoat面板已移动到导出FBX面板中

class RT_OT_TranslateText(Operator):
    """翻译文本操作符 / Translate Text Operator"""
    bl_idname = "rt.translate_text"
    bl_label = "翻译"
    bl_description = "翻译输入的文本"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        
        if not props.translate_input_text.strip():
            show_message_box("请输入要翻译的文本", "警告", 'ERROR')
            return {'CANCELLED'}
        
        try:
            # 调用翻译工具函数
            result = translate_text_tool(
                props.translate_input_text,
                props.translate_source_lang,
                props.translate_target_lang
            )
            
            # 将翻译结果设置到输出文本框
            props.translate_output_text = result
            
            show_message_box("翻译完成", "信息", 'INFO')
            
        except Exception as e:
            show_message_box(f"翻译失败: {str(e)}", "错误", 'ERROR')
            return {'CANCELLED'}
        
        return {'FINISHED'}

class RT_OT_AITranslateText(Operator):
    """AI翻译文本操作符 / AI Translate Text Operator"""
    bl_idname = "rt.ai_translate_text"
    bl_label = "AI翻译"
    bl_description = "使用Doubao AI翻译输入的文本"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        
        if not props.translate_input_text.strip():
            show_message_box("请输入要翻译的文本", "警告", 'ERROR')
            return {'CANCELLED'}
        
        try:
            # 调用AI翻译工具函数
            result = ai_translate_text_tool(
                props.translate_input_text,
                "我现在需要为unity游戏角色动作进行英文命名,我输入中文,你回复我英文结果,请确保英文结果简洁准确干练,不要有太多的字数,尽量使用单个单词概括.结果不包含任何符号(包括_)和空格,首字母使用小写,后续驼峰可以大写开头"
            )
            
            # 将翻译结果设置到输出文本框
            props.translate_output_text = result
            
            show_message_box("AI翻译完成", "信息", 'INFO')
            
        except Exception as e:
            show_message_box(f"AI翻译失败: {str(e)}", "错误", 'ERROR')
            return {'CANCELLED'}
        
        return {'FINISHED'}

class RT_OT_ApplyTranslationToObjects(Operator):
    """将翻译结果应用到选中物体 / Apply Translation to Selected Objects"""
    bl_idname = "rt.apply_translation_to_objects"
    bl_label = "命名应用到选中物体"
    bl_description = "将翻译结果应用到选中物体，重命名物体的object和data name"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.poptools_props.retex_settings
        selected_objects = context.selected_objects
        
        if not selected_objects:
            show_message_box("请先选择要重命名的物体", "警告", 'ERROR')
            return {'CANCELLED'}
        
        if not props.translate_output_text.strip():
            show_message_box("请先进行翻译获取结果", "警告", 'ERROR')
            return {'CANCELLED'}
        
        # 清理翻译结果，移除特殊字符，转为小写，空格替换为下划线
        cleaned_text = props.translate_output_text.lower().replace(" ", "_")
        # 移除非字母数字和下划线的字符
        import re
        cleaned_text = re.sub(r'[^a-zA-Z0-9_]', '', cleaned_text)
        
        renamed_count = 0
        
        for i, obj in enumerate(selected_objects):
            # 为每个物体生成唯一名称（添加序号）
            if len(selected_objects) > 1:
                new_name = f"{cleaned_text}_{i+1:02d}"
            else:
                new_name = cleaned_text
            
            # 检查名称是否已存在，如果存在则添加后缀
            original_name = new_name
            counter = 1
            while new_name in bpy.data.objects:
                new_name = f"{original_name}_{counter}"
                counter += 1
            
            # 重命名物体
            obj.name = new_name
            
            # 重命名物体数据（如果是网格对象）
            if obj.type == 'MESH' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'CURVE' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'SURFACE' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'META' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'FONT' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'ARMATURE' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'LATTICE' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'EMPTY':
                pass  # Empty对象没有data
            elif obj.type == 'CAMERA' and obj.data:
                obj.data.name = new_name
            elif obj.type == 'LIGHT' and obj.data:
                obj.data.name = new_name
            
            renamed_count += 1
        
        show_message_box(f"成功重命名 {renamed_count} 个物体", "重命名完成", 'INFO')
        return {'FINISHED'}

# ============================================================================
# 快捷键管理 / Keymap Management
# ============================================================================

addon_keymaps = []

def register_keymaps():
    """注册快捷键 / Register keymaps"""
    global addon_keymaps
    
    # 获取快捷键配置
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if kc:
        # 创建3D视图快捷键映射
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        
        # 添加Ctrl+T快捷键用于打开纹理管理弹出面板
        kmi = km.keymap_items.new(
            "rt.texture_manager_popup",
            type='T',
            value='PRESS',
            ctrl=True
        )
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    """注销快捷键 / Unregister keymaps"""
    global addon_keymaps
    
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

# ============================================================================
# 注册和注销 / Registration and Unregistration
# ============================================================================

classes = [
    RT_OT_ToggleRetexHelp,
    RT_OT_ToggleIslandRenameBox,
    RT_OT_ToggleCharacterRenameBox,
    RT_OT_ToggleAnimalRenameBox,
    RT_OT_ToggleBuildingRenameBox,
    RT_OT_SmartRenameObjects,
    RT_OT_RenameTextures,
    RT_OT_ResizeTextures,
    RT_OT_AddCustomBodyType,
    RT_OT_SetTexnameOfObject,
    RT_OT_UnpackTextures,
    RT_OT_AdjustSerialNumber,
    RT_OT_ReplaceTextures,
    RT_OT_RenameCharacterBody,
    RT_OT_RenameAnimal,
    RT_OT_SyncTextureNames,
    RT_OT_RenameCharacterHair,
    RT_OT_RenameCharacterTool,
    RT_OT_RenameBuildingObjects,
    RT_OT_SetBuildingType,
    # RT_OT_SetBuildingSerial 已移除，序号现在自动递增
    RT_OT_AutoNameBakeModels,
    RT_OT_OrganizeSelectedMaterials,
    RT_OT_CheckUVs,
    RT_OT_CreateAnnotations,
    RT_OT_ClearAnnotations,
    RT_OT_TranslateText,
    RT_OT_AITranslateText,
    RT_OT_ApplyTranslationToObjects,
    RT_OT_TextureManagerPopup,
    RT_PT_TextureRenamerPanel,
]

def register():
    """注册所有类 / Register all classes"""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # 延迟注册快捷键，确保Blender完全初始化
    bpy.app.timers.register(register_keymaps, first_interval=0.1)
    print("ReTex Tools registered successfully")

def unregister():
    """注销所有类 / Unregister all classes"""
    # 注销快捷键
    unregister_keymaps()
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")
    print("ReTex Tools unregistered successfully")

if __name__ == "__main__":
    register()