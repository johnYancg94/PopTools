# -*- coding: utf-8 -*-
import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty, EnumProperty
import re
from .translation_tools import translate_text_tool, ai_translate_text_tool

# 全局变量存储键盘映射
addon_keymaps = []

# ============================================================================
# 共享UI绘制函数 / Shared UI Drawing Functions
# ============================================================================

def draw_action_naming_ui(layout, context, show_help_section=True):
    """共享的动作命名UI绘制函数
    
    Args:
        layout: Blender UI布局对象
        context: Blender上下文
        show_help_section: 是否显示帮助说明部分（弹出面板不显示）
    """
    props = context.scene.poptools_props
    
    # 创建说明框体（仅在固定面板中显示）
    if show_help_section:
        help_box = layout.box()
        help_row = help_box.row()
        help_row.label(text="使用说明:", icon='HELP')
        
        # 添加隐藏/显示按钮
        if props.show_action_naming_help:
            help_row.operator("poptools.toggle_action_naming_help", text="隐藏说明", icon='HIDE_ON')
            help_box.label(text="① 选择动画类型")
            help_box.label(text="② 如果是海岛NPC专属动画需要输入海岛名,例如\"loveisland\"")
            help_box.label(text="③ 输入动作名称,点击翻译,自动翻译为英文")
            help_box.label(text="④ 可选输入中文备注,也可以直接使用当前动作名称")
            help_box.label(text="⑤ 点击一键自动动作重命名")
        else:
            help_row.operator("poptools.toggle_action_naming_help", text="显示说明", icon='HIDE_OFF')
    
    # 动作命名工具箱
    action_box = layout.box()
    action_box.label(text="角色动作命名工具", icon='ACTION')
    
    # 当前动作显示
    current_box = action_box.box()
    current_box.label(text="当前动作:", icon='ACTION')
    if context.active_object and context.active_object.animation_data and context.active_object.animation_data.action:
        current_action = context.active_object.animation_data.action.name
        current_box.label(text=current_action, icon='RADIOBUT_ON')
    else:
        current_box.label(text="无动作", icon='RADIOBUT_OFF')
    
    # 动画类型选择
    type_box = action_box.box()
    type_box.label(text="动画类型:", icon='PRESET')
    
    # 动画类型按钮 - 每行3个
    for i in range(0, len(ANIMATION_TYPES), 3):
        row = type_box.row(align=True)
        for j in range(3):
            if i + j < len(ANIMATION_TYPES):
                anim_type, display_name, description = ANIMATION_TYPES[i + j]
                
                # 高亮当前选中的类型
                if props.action_animation_type == anim_type:
                    op = row.operator("poptools.set_animation_type", text=display_name, depress=True)
                else:
                    op = row.operator("poptools.set_animation_type", text=display_name)
                op.animation_type = anim_type
            else:
                row.label(text="")
    
    # 海岛动画专用面板
    if props.action_animation_type == "npc_island":
        island_box = action_box.box()
        island_box.label(text="海岛动画设置:", icon='WORLD') 
        island_box.label(text="请使用[海岛任务数值表]的海岛命名", icon='INFO')
        island_box.operator("wm.url_open", text="点击打开海岛任务数值表", icon='URL').url = "https://inspire.sg.larksuite.com/sheets/OKiTsUOiPhC9HQtnqsOuILKas8e?from=from_copylink"
        island_box.prop(props, "island_name", text="海岛名")
    
    # 动画名称输入
    name_box = action_box.box()
    name_box.label(text="动画名称:", icon='SORTALPHA')
    
    name_row = name_box.row(align=True)
    name_row.prop(props, "action_animation_name", text="")
    name_row.operator("poptools.translate_action_name", text="翻译", icon='FILE_REFRESH')
    name_row.operator("poptools.ai_translate_action_name", text="AI翻译", icon='OUTLINER_OB_LIGHT')
    
    # 序号调整按钮
    number_row = name_box.row(align=True)
    number_row.operator("poptools.decrease_action_number", text="序号-1", icon='REMOVE')
    number_row.operator("poptools.increase_action_number", text="序号+1", icon='ADD')
    
    # 中文备注输入框
    comment_box = action_box.box()
    comment_box.label(text="中文备注:", icon='TEXT')
    
    # 显示当前动作名称作为提示
    if context.active_object and context.active_object.animation_data and context.active_object.animation_data.action:
        current_action = context.active_object.animation_data.action.name
        info_row = comment_box.row(align=True)
        info_row.label(text=f"当前动作: {current_action}")
        info_row.operator("poptools.set_default_comment", text="使用", icon='IMPORT')
    
    comment_box.prop(props, "action_chinese_comment", text="")
    
    # 预览最终名称（移动到重命名按钮上方）
    action_box.separator()
    if props.action_animation_type and props.action_animation_name:
        if props.action_animation_type == "npc_island" and props.island_name.strip():
            preview_name = f"ani_npc_{props.island_name}_{props.action_animation_name}"
        elif props.action_animation_type != "npc_island":
            preview_name = f"ani_{props.action_animation_type}_{props.action_animation_name}"
        else:
            preview_name = "需要输入海岛名"
        
        preview_box = action_box.box()
        preview_box.label(text=f"命名预览: {preview_name}", icon='HIDE_OFF')
    
    # 重命名按钮
    rename_row = action_box.row()
    rename_row.scale_y = 1.8
    rename_row.operator("poptools.rename_action", text="一键动作重命名", icon='FILE_REFRESH')
    # 创建一个单独的按钮行
    url_row = action_box.row()
    url_row.scale_y = 1.2
    url_row.operator("wm.url_open", text="点击打开蜂鸟动作资产表", icon='URL').url = "https://inspire.sg.larksuite.com/docx/SWvoduj8SoIpxqxuBd9uplEtssg?from=from_copylink"
    
    # 当前对象信息
    if context.active_object:
        info_box = action_box.box()
        info_box.label(text="当前对象信息:", icon='INFO')
        info_box.label(text=f"对象: {context.active_object.name}")

# ============================================================================
# 操作符定义 / Operator Definitions
# ============================================================================

# 动画类型预设
ANIMATION_TYPES = [
    ("idle_stand", "站立待机", "站立待机动画"),
    ("idle_sit", "坐待机", "坐待机动画"),
    ("celebrate_clap", "庆祝", "庆祝动画"),
    ("move_walk", "走路", "走路动画"),
    ("move_run", "跑", "跑步动画"),
    ("play_chat", "人物交互", "人物交互动画"),
    ("play_control", "物件交互", "物件交互动画"),
    ("npc_island", "海岛NPC动画", "海岛NPC动画"),
]

class POPTOOLS_OT_set_animation_type(Operator):
    """设置动画类型"""
    bl_idname = "poptools.set_animation_type"
    bl_label = "设置动画类型"
    bl_description = "设置当前选择的动画类型"
    
    animation_type: StringProperty(
        name="动画类型",
        description="动画类型标识符",
        default=""
    )
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.action_animation_type = self.animation_type
        return {'FINISHED'}

class POPTOOLS_OT_translate_action_name(Operator):
    """翻译动作名称"""
    bl_idname = "poptools.translate_action_name"
    bl_label = "翻译动作名称"
    bl_description = "翻译输入的动作名称"
    
    def execute(self, context):
        props = context.scene.poptools_props
        
        if not props.action_animation_name.strip():
            self.report({'WARNING'}, "请先输入动作名称")
            return {'CANCELLED'}
        
        try:
            # 获取插件首选项
            addon_prefs = context.preferences.addons[__package__].preferences
            
            # 翻译文本
            translated_text = translate_text_tool(
                props.action_animation_name,
                "auto",  # 自动检测源语言
                "en",    # 翻译为英文
                addon_prefs.tencent_secret_id,
                addon_prefs.tencent_secret_key,
                addon_prefs.tencent_region
            )
            
            if translated_text:
                # 使用AI翻译的原始内容，仅添加01后缀
                base_name = translated_text + "01"
                
                # 检查场景中是否有重复的动作名称，如果有则自动增量
                final_name = self.get_unique_action_name(base_name)
                
                props.action_animation_name = final_name
                self.report({'INFO'}, f"翻译完成: {translated_text} -> {final_name}")
            else:
                self.report({'ERROR'}, "翻译失败，请检查网络连接和API配置")
                
        except Exception as e:
            self.report({'ERROR'}, f"翻译出错: {str(e)}")
            
        return {'FINISHED'}
    
    def get_unique_action_name(self, base_name):
        """获取唯一的动作名称，如果重复则自动增量"""
        # 获取所有现有的动作名称
        existing_actions = set()
        for action in bpy.data.actions:
            existing_actions.add(action.name)
        
        # 如果基础名称不重复，直接返回
        if base_name not in existing_actions:
            return base_name
        
        # 如果重复，则增量处理
        # 提取基础名称（去掉数字后缀）
        import re
        match = re.match(r'(.+?)(\d+)$', base_name)
        if match:
            name_part = match.group(1)
            start_num = int(match.group(2))
        else:
            name_part = base_name
            start_num = 1
        
        # 寻找可用的数字后缀
        counter = start_num
        while True:
            test_name = f"{name_part}{counter:02d}"
            if test_name not in existing_actions:
                return test_name
            counter += 1

class POPTOOLS_OT_decrease_action_number(Operator):
    """减少动作名称中的序号"""
    bl_idname = "poptools.decrease_action_number"
    bl_label = "序号-1"
    bl_description = "将动作名称中的序号减1（不会减为00）"
    
    def execute(self, context):
        props = context.scene.poptools_props
        current_name = props.action_animation_name.strip()
        
        if not current_name:
            self.report({'WARNING'}, "动画名称为空")
            return {'CANCELLED'}
        
        import re
        # 匹配末尾的数字
        match = re.search(r'(.+?)(\d+)$', current_name)
        
        if match:
            name_part = match.group(1)
            current_num = int(match.group(2))
            
            # 不允许减为00或更小
            if current_num > 1:
                new_num = current_num - 1
                new_name = f"{name_part}{new_num:02d}"
                props.action_animation_name = new_name
                self.report({'INFO'}, f"序号已减少为: {new_num:02d}")
            else:
                self.report({'WARNING'}, "序号不能减少到00或更小")
        else:
            self.report({'WARNING'}, "动画名称末尾没有找到数字序号")
        
        return {'FINISHED'}

class POPTOOLS_OT_increase_action_number(Operator):
    """增加动作名称中的序号"""
    bl_idname = "poptools.increase_action_number"
    bl_label = "序号+1"
    bl_description = "将动作名称中的序号加1"
    
    def execute(self, context):
        props = context.scene.poptools_props
        current_name = props.action_animation_name.strip()
        
        if not current_name:
            self.report({'WARNING'}, "动画名称为空")
            return {'CANCELLED'}
        
        import re
        # 匹配末尾的数字
        match = re.search(r'(.+?)(\d+)$', current_name)
        
        if match:
            name_part = match.group(1)
            current_num = int(match.group(2))
            new_num = current_num + 1
            new_name = f"{name_part}{new_num:02d}"
            props.action_animation_name = new_name
            self.report({'INFO'}, f"序号已增加为: {new_num:02d}")
        else:
            # 如果没有数字，则添加01
            new_name = current_name + "01"
            props.action_animation_name = new_name
            self.report({'INFO'}, "已添加序号: 01")
        
        return {'FINISHED'}

class POPTOOLS_OT_ai_translate_action_name(Operator):
    """AI翻译动作名称"""
    bl_idname = "poptools.ai_translate_action_name"
    bl_label = "AI翻译动作名称"
    bl_description = "使用AI翻译当前动画名称为英文格式"
    
    def execute(self, context):
        props = context.scene.poptools_props
        
        # 检查是否有动画名称
        if not props.action_animation_name.strip():
            self.report({'WARNING'}, "请先输入动画名称")
            return {'CANCELLED'}
        
        try:
            # 使用AI翻译工具
            translated_text = ai_translate_text_tool(props.action_animation_name)
            
            if translated_text:
                # 使用AI翻译的原始内容，仅添加01后缀
                base_name = translated_text + "01"
                
                # 检查场景中是否有重复的动作名称，如果有则自动增量
                final_name = self.get_unique_action_name(base_name)
                
                props.action_animation_name = final_name
                self.report({'INFO'}, f"AI翻译完成: {translated_text} -> {final_name}")
            else:
                self.report({'ERROR'}, "AI翻译失败，请检查网络连接和API配置")
                
        except Exception as e:
            self.report({'ERROR'}, f"AI翻译出错: {str(e)}")
            
        return {'FINISHED'}
    
    def get_unique_action_name(self, base_name):
        """获取唯一的动作名称，如果重复则自动增量"""
        # 获取所有现有的动作名称
        existing_actions = set()
        for action in bpy.data.actions:
            existing_actions.add(action.name)
        
        # 如果基础名称不重复，直接返回
        if base_name not in existing_actions:
            return base_name
        
        # 如果重复，则增量处理
        # 提取基础名称（去掉数字后缀）
        import re
        match = re.match(r'(.+?)(\d+)$', base_name)
        if match:
            name_part = match.group(1)
            start_num = int(match.group(2))
        else:
            name_part = base_name
            start_num = 1
        
        # 寻找可用的数字后缀
        counter = start_num
        while True:
            test_name = f"{name_part}{counter:02d}"
            if test_name not in existing_actions:
                return test_name
            counter += 1

class POPTOOLS_OT_set_default_comment(Operator):
    """设置默认中文备注为当前动作名称"""
    bl_idname = "poptools.set_default_comment"
    bl_label = "使用当前动作名称"
    bl_description = "将当前动作名称设置为中文备注的默认值"
    
    def execute(self, context):
        props = context.scene.poptools_props
        
        if context.active_object and context.active_object.animation_data and context.active_object.animation_data.action:
            current_action = context.active_object.animation_data.action.name
            props.action_chinese_comment = current_action
            self.report({'INFO'}, f"已设置中文备注为: {current_action}")
        else:
            self.report({'WARNING'}, "没有找到当前动作")
            
        return {'FINISHED'}

class POPTOOLS_OT_action_naming_popup(Operator):
    """弹出动作命名工具面板"""
    bl_idname = "poptools.action_naming_popup"
    bl_label = "角色动作命名工具"
    bl_description = "弹出动作命名工具面板"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # 检查是否有活动对象
        if not context.active_object:
            self.report({'WARNING'}, "请先选择一个对象")
            return {'CANCELLED'}
        
        # 在鼠标位置弹出面板
        return context.window_manager.invoke_popup(self, width=450)
    
    def draw(self, context):
        layout = self.layout
        # 使用共享的UI绘制函数，弹出面板不显示帮助说明
        draw_action_naming_ui(layout, context, show_help_section=False)

class POPTOOLS_OT_rename_action(Operator):
    """一键动作重命名"""
    bl_idname = "poptools.rename_action"
    bl_label = "一键动作重命名"
    bl_description = "按照命名规则重命名选中对象的动作"
    
    def execute(self, context):
        props = context.scene.poptools_props
        
        # 检查是否有选中的对象
        if not context.selected_objects:
            self.report({'WARNING'}, "请先选择一个对象")
            return {'CANCELLED'}
        
        # 检查是否设置了动画类型
        if not props.action_animation_type:
            self.report({'WARNING'}, "请先选择动画类型")
            return {'CANCELLED'}
        
        # 检查是否输入了动画名称
        if not props.action_animation_name.strip():
            self.report({'WARNING'}, "请先输入动画名称")
            return {'CANCELLED'}
        
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "没有活动对象")
            return {'CANCELLED'}
        
        # 检查对象是否有动画数据
        if not obj.animation_data or not obj.animation_data.action:
            self.report({'WARNING'}, "选中的对象没有动作数据")
            return {'CANCELLED'}
        
        # 生成新的动作名称
        if props.action_animation_type == "npc_island":
            # 海岛动画特殊命名规则: ani_npc_海岛名_名称
            if not props.island_name.strip():
                self.report({'ERROR'}, "海岛动画类型需要输入海岛名")
                return {'CANCELLED'}
            new_name = f"ani_npc_{props.island_name}_{props.action_animation_name}"
        else:
            new_name = f"ani_{props.action_animation_type}_{props.action_animation_name}"
        
        # 重命名动作
        old_name = obj.animation_data.action.name
        obj.animation_data.action.name = new_name
        
        # 尝试修改AC_Settings.tags（参考AC插件逻辑）
        if props.action_chinese_comment.strip():
            try:
                # 获取重命名后的动作
                renamed_action = bpy.data.actions.get(new_name)
                if renamed_action and hasattr(renamed_action, 'AC_Settings'):
                    renamed_action.AC_Settings.tags = props.action_chinese_comment.strip()
                    self.report({'INFO'}, f"动作重命名成功: {old_name} -> {new_name}，标签已更新: {props.action_chinese_comment}")
                else:
                    self.report({'INFO'}, f"动作重命名成功: {old_name} -> {new_name}，未找到AC_Settings.tags属性")
            except Exception as e:
                self.report({'INFO'}, f"动作重命名成功: {old_name} -> {new_name}，标签更新失败: {str(e)}")
        else:
            self.report({'INFO'}, f"动作重命名成功: {old_name} -> {new_name}")
        
        # 清空输入框
        props.action_animation_name = ""
        props.action_chinese_comment = ""
        props.island_name = ""
        
        return {'FINISHED'}

class POPTOOLS_PT_action_naming(Panel):
    """动作命名面板"""
    bl_label = "角色动作命名"
    bl_idname = "POPTOOLS_PT_action_naming"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PopTools'
    bl_order = 6
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get(__package__)
        if addon_prefs:
            return addon_prefs.preferences.enable_action_naming_tools
        return False
    
    def draw(self, context):
        layout = self.layout
        # 使用共享的UI绘制函数，固定面板显示帮助说明
        draw_action_naming_ui(layout, context, show_help_section=True)
            
            

class POPTOOLS_OT_toggle_action_naming_help(Operator):
    """切换动作命名工具说明的显示/隐藏"""
    bl_idname = "poptools.toggle_action_naming_help"
    bl_label = "切换说明显示"
    bl_description = "切换动作命名工具说明的显示/隐藏状态"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.poptools_props
        props.show_action_naming_help = not props.show_action_naming_help
        return {'FINISHED'}

# 注册的类列表
classes = (
    POPTOOLS_OT_set_animation_type,
    POPTOOLS_OT_translate_action_name,
    POPTOOLS_OT_ai_translate_action_name,
    POPTOOLS_OT_decrease_action_number,
    POPTOOLS_OT_increase_action_number,
    POPTOOLS_OT_set_default_comment,
    POPTOOLS_OT_action_naming_popup,
    POPTOOLS_OT_rename_action,
    POPTOOLS_OT_toggle_action_naming_help,
    POPTOOLS_PT_action_naming,
)

def register_keymaps():
    """注册快捷键"""
    global addon_keymaps
    
    # 创建键盘映射
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        
        # 使用默认快捷键设置 - 可以在偏好设置中通过UI修改
        kmi = km.keymap_items.new(
            'poptools.action_naming_popup',
            'D', 'PRESS',
            ctrl=True, shift=False, alt=False
        )
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    """注销快捷键"""
    global addon_keymaps
    
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # 延迟注册快捷键，确保首选项已加载
    bpy.app.timers.register(register_keymaps, first_interval=0.1)

def unregister():
    unregister_keymaps()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)