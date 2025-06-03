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

# ============================================================================
# 操作符定义 / Operator Definitions
# ============================================================================

class RT_OT_ShowSmartRenameHelp(Operator):
    """智能重命名帮助提示 / Smart Rename Help"""
    bl_idname = "rt.show_smart_rename_help"
    bl_label = ""
    bl_description = """说明：
    1. 命名前标注:
       - b1,b2... 为气球
       - h1,h2... 为手持
       以此内推
       
    2. 同一个海岛的序号不能重复
       正确排序方式如: b1,h2,h3,p4
       
    3. 标注完成后选择该海岛所有道具,
       点击【智能重命名】即可"""

    def execute(self, context):
        return {'CANCELLED'}  # 不执行任何操作

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
        props = context.scene.poptools.retex_settings
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
            
            # 使用正则表达式匹配模式：字母+数字
            match = re.match(r'^([a-zA-Z]+)(\d+)$', old_name)
            
            if match:
                type_prefix = match.group(1).lower()
                number = match.group(2)
                
                # 检查是否为已知类型
                if type_prefix in type_mapping:
                    type_name = type_mapping[type_prefix]
                    new_name = f"{item_land}_{type_name}_{number:0>2}"
                    
                    # 检查新名称是否已存在
                    if new_name in bpy.data.objects:
                        errors.append(f"对象 '{old_name}' 重命名失败：名称 '{new_name}' 已存在")
                        continue
                    
                    obj.name = new_name
                    total_renamed += 1
                else:
                    errors.append(f"对象 '{old_name}' 重命名失败：未知类型前缀 '{type_prefix}'")
            else:
                errors.append(f"对象 '{old_name}' 重命名失败：名称格式不正确（应为字母+数字）")
        
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
        props = context.scene.poptools.retex_settings
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
    bl_description = "批量调整选中对象的纹理大小"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.poptools.retex_settings
        selected_objects = context.selected_objects
        
        if not selected_objects:
            show_message_box("请先选择要处理的对象", "警告", 'ERROR')
            return {'CANCELLED'}
        
        target_size = int(props.resolution_preset)
        resized_count = 0
        
        for obj in selected_objects:
            if obj.type == 'MESH' and obj.data.materials:
                for material in obj.data.materials:
                    if material and material.use_nodes:
                        for node in material.node_tree.nodes:
                            if node.type == 'TEX_IMAGE' and node.image:
                                image = node.image
                                if image.size[0] != target_size or image.size[1] != target_size:
                                    image.scale(target_size, target_size)
                                    resized_count += 1
        
        show_message_box(f"成功调整 {resized_count} 个纹理大小到 {target_size}x{target_size}", "调整完成", 'INFO')
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
        props = context.scene.poptools.retex_settings
        
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
        props = context.scene.poptools.retex_settings
        
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
            props = context.scene.poptools.retex_settings
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
        props = context.scene.poptools.retex_settings
        
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
        props = context.scene.poptools.retex_settings
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
        props = context.scene.poptools.retex_settings
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
        props = context.scene.poptools.retex_settings
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

class RT_OT_RenameBuildingObjects(Operator):
    """建筑重命名 / Rename Building Objects"""
    bl_idname = "rt.rename_building_objects"
    bl_label = "建筑重命名"
    bl_description = "使用建筑命名规则重命名选定的对象"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        props = context.scene.poptools.retex_settings
        
        # 获取用户输入
        building_type = props.building_type
        island_name = props.building_island_name.strip()
        building_name = props.building_name.strip()
        serial_number = props.building_serial_number
        
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
        
        total_renamed = 0
        errors = []
        
        for obj in selected_objects:
            if obj.type != 'MESH':
                errors.append(f"对象 '{obj.name}' 不是网格对象，跳过")
                continue
            
            # 生成新名称：mesh_[建筑类型]_[海岛名]_[建筑名][序号]
            new_name = f"mesh_{building_type}_{island_name}_{building_name}{serial_number}"
            
            # 检查新名称是否已存在
            if new_name in bpy.data.objects:
                errors.append(f"对象 '{obj.name}' 重命名失败：名称 '{new_name}' 已存在")
                continue
            
            try:
                # 重命名对象
                old_name = obj.name
                obj.name = new_name
                
                # 同时重命名对象数据（网格数据）
                if obj.data:
                    obj.data.name = new_name
                
                total_renamed += 1
                
            except Exception as e:
                errors.append(f"对象 '{obj.name}' 重命名失败：{str(e)}")
        
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
        props = context.scene.poptools.retex_settings
        props.building_type = self.building_type
        return {'FINISHED'}

class RT_OT_SetBuildingSerial(Operator):
    """设置建筑序号 / Set Building Serial Number"""
    bl_idname = "rt.set_building_serial"
    bl_label = "设置建筑序号"
    bl_description = "设置当前选择的建筑序号"
    bl_options = {'REGISTER', 'UNDO'}
    
    serial_number: StringProperty(
        name="序号",
        description="要设置的序号",
        default="01"
    )
    
    def execute(self, context):
        props = context.scene.poptools.retex_settings
        props.building_serial_number = self.serial_number
        return {'FINISHED'}

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
        props = context.scene.poptools.retex_settings
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

class RT_PT_TextureRenamerPanel(Panel):
    """纹理管理面板 / Texture Management Panel"""
    bl_label = "纹理管理"
    bl_idname = "RT_PT_TextureRenamerPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PopTools'
    bl_order = 0

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_retex_tools

    def draw(self, context):
        layout = self.layout
        props = context.scene.poptools.retex_settings
        
        # 智能重命名部分
        box = layout.box()
        box.label(text="海岛配方道具智能重命名：")
        row = box.row()
        row.prop(props, "item_land", text="海岛名")
        
        # 类型标识符说明
        note_box = box.box()
        note_box.label(text="类型标识符说明：")
        note_box.label(text="b：气球 h：手持 p：堂食 c：头戴")
        
        # 帮助按钮和重命名按钮
        row = box.row(align=True)
        row.operator("rt.show_smart_rename_help", text="", icon='QUESTION')
        row.operator("rt.smart_rename_objects", text="智能重命名选中物体", icon='OUTLINER_OB_MESH')
        
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
        row.operator("rt.replace_textures", text="同步所有纹理", icon='FILE_REFRESH')
        
        # 分隔线
        layout.separator()
        
        # 添加分辨率设置
        box = layout.box()
        box.label(text="纹理分辨率：")
        row = box.row()
        row.prop(props, "resolution_preset", text="大小")
        row = layout.row()
        row.operator("rt.resize_textures", text="调整纹理大小", icon='IMAGE_DATA')
        
        # 添加角色重命名部分
        layout.separator()
        char_box = layout.box()
        char_box.label(text="角色重命名：")
        
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
        row.operator("rt.rename_character_body", text="命名选中体型")
        row.operator("rt.rename_character_hair", text="命名选中发型")
        
        # 添加同步纹理命名按钮
        row = char_box.row(align=True)
        row.operator("rt.sync_texture_names", text="同步选中模型纹理命名", icon='FILE_REFRESH')
        
        # 添加一键标注和清理标注按钮
        row = char_box.row(align=True)
        row.operator("rt.create_annotations", text="一键标注", icon='TEXT')
        row.operator("rt.clear_annotations", text="清理标注", icon='TRASH')
        
        # 添加动物重命名部分
        layout.separator()
        animal_box = layout.box()
        animal_box.label(text="动物重命名：")
        
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
        row.operator("rt.rename_animal", text="命名选中动物")
        
        # 添加建筑重命名部分
        layout.separator()
        building_box = layout.box()
        building_box.label(text="建筑重命名：")
        
        # 建筑类型按钮组
        type_row = building_box.row(align=True)
        # 静态建筑按钮
        op_static = type_row.operator("rt.set_building_type", text="静态建筑", depress=(props.building_type == 'buildpart'))
        op_static.building_type = 'buildpart'
        # 动画建筑按钮
        op_anim = type_row.operator("rt.set_building_type", text="动画建筑", depress=(props.building_type == 'anibuild'))
        op_anim.building_type = 'anibuild'
        
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
        
        # 序号按钮组
        serial_row = building_box.row(align=True)
        # 序号01-05按钮
        for i in range(1, 6):
            serial_num = f"{i:02d}"
            op_serial = serial_row.operator("rt.set_building_serial", text=serial_num, depress=(props.building_serial_number == serial_num))
            op_serial.serial_number = serial_num
        
        # 重命名按钮
        row = building_box.row(align=True)
        row.operator("rt.rename_building_objects", text="重命名选中建筑", icon='HOME')
        
        # 烘焙高低模自动命名
        row = building_box.row(align=True)
        row.separator()
        row = building_box.row(align=True)
        row.operator("rt.auto_name_bake_models", text="烘焙高低模自动命名", icon='MESH_DATA')

class RT_PT_3DCoatPanel(Panel):
    """导出3DCoat前整理面板 / 3DCoat Export Preparation Panel"""
    bl_label = "导出3DCoat前整理"
    bl_idname = "RT_PT_3DCoatPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PopTools'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_retex_tools

    def draw(self, context):
        layout = self.layout
        props = context.scene.poptools.retex_settings

        # 添加材质整理部分
        mat_box = layout.box()
        mat_box.label(text="材质整理：")
        row = mat_box.row()
        row.operator("rt.organize_selected_materials", text="一键整理选中模型材质", icon='MATERIAL')

        # 添加UV检查部分
        uv_box = layout.box()
        uv_box.label(text="UV检查：")
        row = uv_box.row()
        row.operator("rt.check_uvs", text="一键检查UV", icon='UV_DATA')

        # 显示UV检查结果
        if props.uv_check_results:
            results_box = uv_box.box()
            if props.uv_check_results == "所有模型UV正常，无重复UV Map":
                row = results_box.row()
                row.label(text="无重复UV模型", icon='CHECKMARK')
            else:
                results_box.label(text="存在多个UV Map的模型：")
                # 创建一个水平布局来显示模型名称
                flow = results_box.column_flow(columns=4, align=True)
                # 将结果字符串拆分为列表
                items = props.uv_check_results.split('\n')
                for item in items:
                    if item.strip():
                        # 每个模型名称占据单独一行
                        flow.label(text=item)
        elif props.uv_check_triggered:
            results_box = uv_box.box()
            # 如果检查已触发但结果为空（可能在操作符中被清空表示无问题）
            row = results_box.row()
            row.label(text="无重复UV模型", icon='CHECKMARK')

# ============================================================================
# 注册和注销 / Registration and Unregistration
# ============================================================================

classes = [
    RT_OT_ShowSmartRenameHelp,
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
    RT_OT_RenameBuildingObjects,
    RT_OT_SetBuildingType,
    RT_OT_SetBuildingSerial,
    RT_OT_AutoNameBakeModels,
    RT_OT_OrganizeSelectedMaterials,
    RT_OT_CheckUVs,
    RT_OT_CreateAnnotations,
    RT_OT_ClearAnnotations,
    RT_PT_TextureRenamerPanel,
    RT_PT_3DCoatPanel,
]

def register():
    """注册所有类 / Register all classes"""
    for cls in classes:
        bpy.utils.register_class(cls)
    print("ReTex Tools registered successfully")

def unregister():
    """注销所有类 / Unregister all classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")
    print("ReTex Tools unregistered successfully")

if __name__ == "__main__":
    register()