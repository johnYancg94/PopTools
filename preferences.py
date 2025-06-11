# -*- coding: utf-8 -*-
"""
PopTools Preferences
插件首选项设置
"""

import bpy
import subprocess
import sys
import os
from bpy.types import AddonPreferences, Operator, Menu
from bpy.props import BoolProperty, StringProperty, EnumProperty

# 导入快捷键UI模块
try:
    import rna_keymap_ui
except ImportError:
    rna_keymap_ui = None

class POPTOOLS_MT_reset_hotkey(bpy.types.Menu):
    """重置快捷键菜单"""
    bl_label = "重置快捷键"
    bl_idname = "POPTOOLS_MT_reset_hotkey"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("poptools.reset_hotkey", text="重置为默认 (Ctrl+D)")

class POPTOOLS_OT_reset_hotkey(Operator):
    """重置快捷键为默认值"""
    bl_idname = "poptools.reset_hotkey"
    bl_label = "重置快捷键"
    bl_description = "重置动作命名快捷键为默认值"
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        prefs.action_naming_hotkey = "CTRL+D"
        self.report({'INFO'}, "快捷键已重置为默认值")
        return {'FINISHED'}

class POPTOOLS_OT_unlock_api_keys(Operator):
    """解锁API密钥"""
    bl_idname = "poptools.unlock_api_keys"
    bl_label = "解锁API密钥"
    bl_description = "使用密码解锁并自动填入API密钥"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        if not prefs.api_password:
            self.report({'ERROR'}, "请先输入API密钥解锁密码")
            return {'CANCELLED'}
        
        try:
            # 尝试解密并自动填入密钥
            secret_id = prefs.get_decrypted_secret_id()
            secret_key = prefs.get_decrypted_secret_key()
            
            if secret_id and secret_key:
                self.report({'INFO'}, "API密钥解锁成功并已自动填入")
                print(f"[解锁成功] Secret ID: {secret_id[:8]}..., Secret Key: {secret_key[:8]}...")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "密码错误或密钥未配置，请检查密码或联系插件作者")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"解锁失败: {str(e)}")
            return {'CANCELLED'}

class POPTOOLS_OT_install_tencent_sdk(Operator):
    """安装腾讯云SDK"""
    bl_idname = "poptools.install_tencent_sdk"
    bl_label = "安装腾讯云SDK"
    bl_description = "自动安装腾讯云Python SDK"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            # 获取Python可执行文件路径
            python_exe = sys.executable
            
            # 安装腾讯云SDK
            self.report({'INFO'}, "正在安装腾讯云SDK，请稍候...")
            
            # 使用subprocess运行pip install命令
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "tencentcloud-sdk-python"],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.report({'INFO'}, "腾讯云SDK安装成功！请重启Blender以使用翻译功能。")
                # 设置安装成功标志
                context.preferences.addons[__package__].preferences.sdk_install_success = True
                # 强制刷新UI以显示重启提示
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                # 强制更新首选项面板
                for area in context.screen.areas:
                    if area.type == 'PREFERENCES':
                        area.tag_redraw()
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                self.report({'ERROR'}, f"SDK安装失败: {error_msg}")
                
        except subprocess.TimeoutExpired:
            self.report({'ERROR'}, "安装超时，请检查网络连接后重试")
        except Exception as e:
            self.report({'ERROR'}, f"安装过程中发生错误: {str(e)}")
            
        return {'FINISHED'}

class POPTOOLS_OT_restart_blender(Operator):
    """重启Blender"""
    bl_idname = "poptools.restart_blender"
    bl_label = "重启Blender"
    bl_description = "保存首选项配置并关闭Blender"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        # 保存首选项
        bpy.ops.wm.save_userpref()
        self.report({'INFO'}, "首选项已保存，Blender即将关闭")
        
        # 关闭Blender
        bpy.ops.wm.quit_blender()
        
        return {'FINISHED'}

class POPTOOLS_OT_skip_restart_reminder(Operator):
    """跳过重启提醒"""
    bl_idname = "poptools.skip_restart_reminder"
    bl_label = "跳过重启提醒"
    bl_description = "跳过重启提醒，用户可以手动重启Blender"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        prefs.mark_restart_reminder_shown()
        prefs.sdk_install_success = False  # 重置安装成功标志
        self.report({'INFO'}, "已跳过重启提醒，请手动重启Blender以使用翻译功能")
        return {'FINISHED'}

class POPTOOLS_OT_reset_verification(Operator):
    """重置验证状态"""
    bl_idname = "poptools.reset_verification"
    bl_label = "重置验证状态"
    bl_description = "重置SDK和API验证状态，强制重新检测"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        prefs.reset_verification_status()
        prefs.sdk_check_enabled = True  # 重新启用检测
        self.report({'INFO'}, "验证状态已重置，将重新进行检测")
        return {'FINISHED'}

class POPTOOLS_OT_verify_api_config(Operator):
    """验证API配置"""
    bl_idname = "poptools.verify_api_config"
    bl_label = "验证API配置"
    bl_description = "手动验证腾讯云API配置是否正确"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        # 首先检查SDK
        if not prefs.verify_sdk_installation():
            self.report({'ERROR'}, "腾讯云SDK未安装，请先安装SDK")
            return {'CANCELLED'}
        
        # 然后验证API配置
        if prefs.verify_api_config():
            self.report({'INFO'}, "API配置验证成功！")
            # 验证成功后建议关闭自动检测以提高性能
            if prefs.sdk_check_enabled:
                self.report({'INFO'}, "建议在性能优化选项中关闭SDK检测以提高性能")
        else:
            self.report({'ERROR'}, "API配置验证失败，请检查Secret ID和Secret Key")
        
        return {'FINISHED'}

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
        default=False
    )
    
    enable_translation_tools: BoolProperty(
        name="启用翻译工具",
        description="启用/禁用纹理名称翻译工具",
        default=True
    )
    
    enable_action_naming_tools: BoolProperty(
        name="启用动作命名工具",
        description="启用/禁用动作命名和重命名工具",
        default=True
    )
    
    # 快捷键设置
    action_naming_hotkey: StringProperty(
        name="动作命名工具快捷键",
        description="动作命名工具的快捷键设置",
        default="CTRL+D"
    )
    
    retex_hotkey: StringProperty(
        name="纹理管理工具快捷键",
        description="纹理管理工具弹出面板的快捷键设置",
        default="CTRL+T"
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
    
    # 腾讯云翻译API配置
    api_password: StringProperty(
        name="API密钥解锁密码",
        description="输入正确的密码来解锁API密钥",
        default="",
        subtype='PASSWORD'
    )
    
    tencent_secret_id: StringProperty(
        name="腾讯云Secret ID",
        description="腾讯云API Secret ID，用于翻译功能（已加密存储）",
        default="",
        subtype='PASSWORD'
    )
    
    tencent_secret_key: StringProperty(
        name="腾讯云Secret Key",
        description="腾讯云API Secret Key，用于翻译功能（已加密存储）",
        default="",
        subtype='PASSWORD'
    )
    
    def get_decrypted_secret_id(self):
        """获取解密后的Secret ID"""
        from .crypto_utils import get_decrypted_api_key
        if self.api_password:
            decrypted = get_decrypted_api_key("tencent_secret_id", self.api_password)
            print(f"[调试] 解密Secret ID: 密码='{self.api_password}', 解密结果='{decrypted}'")
            if decrypted:
                # 解密成功，自动填入手动配置字段
                if self.tencent_secret_id != decrypted:
                    self.tencent_secret_id = decrypted
                    print(f"[调试] 自动更新手动配置的Secret ID: '{decrypted}'")
                return decrypted
        # 如果解密失败，尝试返回手动配置的密钥
        manual_key = self.tencent_secret_id
        print(f"[调试] 使用手动配置的Secret ID: '{manual_key}'")
        return manual_key
    
    def get_decrypted_secret_key(self):
        """获取解密后的Secret Key"""
        from .crypto_utils import get_decrypted_api_key
        if self.api_password:
            decrypted = get_decrypted_api_key("tencent_secret_key", self.api_password)
            print(f"[调试] 解密Secret Key: 密码='{self.api_password}', 解密结果='{decrypted}'")
            if decrypted:
                # 解密成功，自动填入手动配置字段
                if self.tencent_secret_key != decrypted:
                    self.tencent_secret_key = decrypted
                    print(f"[调试] 自动更新手动配置的Secret Key: '{decrypted}'")
                return decrypted
        # 如果解密失败，尝试返回手动配置的密钥
        manual_key = self.tencent_secret_key
        print(f"[调试] 使用手动配置的Secret Key: '{manual_key}'")
        return manual_key
    
    tencent_region: EnumProperty(
        name="腾讯云地域",
        description="腾讯云服务地域",
        items=[
            ('ap-beijing', '北京', '华北地区(北京)'),
            ('ap-shanghai', '上海', '华东地区(上海)'),
            ('ap-guangzhou', '广州', '华南地区(广州)'),
            ('ap-chengdu', '成都', '西南地区(成都)'),
            ('ap-singapore', '新加坡', '亚太地区(新加坡)'),
            ('ap-hongkong', '香港', '港澳台地区(中国香港)'),
            ('na-toronto', '多伦多', '北美地区(多伦多)'),
            ('eu-frankfurt', '法兰克福', '欧洲地区(法兰克福)')
        ],
        default='ap-hongkong'
    )
    
    # SDK安装成功标志
    sdk_install_success: BoolProperty(
        name="SDK安装成功",
        description="标记SDK是否安装成功",
        default=False
    )
    
    # 新增：智能检测和性能优化相关属性
    sdk_installation_verified: BoolProperty(
        name="SDK安装已验证",
        description="标记SDK安装状态已验证，避免重复检测",
        default=False
    )
    
    api_config_verified: BoolProperty(
        name="API配置已验证",
        description="标记API配置已验证成功，避免重复检测",
        default=False
    )
    
    sdk_check_enabled: BoolProperty(
        name="启用SDK检测",
        description="是否启用腾讯云SDK检测（成功配置后可关闭以提高性能）",
        default=False
    )
    
    restart_reminder_shown: BoolProperty(
        name="重启提醒已显示",
        description="标记重启提醒是否已显示过",
        default=False
    )
    
    def verify_sdk_installation(self):
        """验证SDK安装状态"""
        if not self.sdk_check_enabled:
            return self.sdk_installation_verified
        
        try:
            import tencentcloud
            self.sdk_installation_verified = True
            print("[PopTools] 腾讯云SDK验证成功")
            return True
        except ImportError:
            self.sdk_installation_verified = False
            print("[PopTools] 腾讯云SDK未安装")
            return False
    
    def verify_api_config(self):
        """验证API配置"""
        if not self.sdk_check_enabled:
            return self.api_config_verified
        
        # 检查解锁密码方式的API配置
        if self.api_password:
            try:
                from .crypto_utils import get_decrypted_api_key
                secret_id = get_decrypted_api_key("tencent_secret_id", self.api_password)
                secret_key = get_decrypted_api_key("tencent_secret_key", self.api_password)
                
                if secret_id and secret_key and len(secret_id) > 10 and len(secret_key) > 10:
                    self.api_config_verified = True
                    print("[PopTools] API配置验证成功（解锁方式）")
                    return True
            except Exception as e:
                print(f"[PopTools] 解锁方式API验证失败: {e}")
        
        # 检查手动配置的API
        secret_id = self.tencent_secret_id
        secret_key = self.tencent_secret_key
        
        if secret_id and secret_key and len(secret_id) > 10 and len(secret_key) > 10:
            self.api_config_verified = True
            print("[PopTools] API配置验证成功（手动方式）")
            return True
        
        self.api_config_verified = False
        return False
    
    def should_show_restart_reminder(self):
        """判断是否应该显示重启提醒"""
        # 如果SDK安装成功但还没有验证过安装状态，且没有显示过重启提醒
        if self.sdk_install_success and not self.sdk_installation_verified and not self.restart_reminder_shown:
            return True
        return False
    
    def should_check_sdk(self):
        """判断是否需要检测SDK"""
        # 如果用户禁用了检测，则不检测
        if not self.sdk_check_enabled:
            return False
        
        # 如果已经验证过且API配置也验证过，则不需要重复检测
        if self.sdk_installation_verified and self.api_config_verified:
            return False
        
        return True
    
    def reset_verification_status(self):
        """重置验证状态（用于强制重新检测）"""
        self.sdk_installation_verified = False
        self.api_config_verified = False
        self.restart_reminder_shown = False
        print("[PopTools] 验证状态已重置")
    
    def mark_restart_reminder_shown(self):
        """标记重启提醒已显示"""
        self.restart_reminder_shown = True
    
    def draw(self, context):
        layout = self.layout
        
        # 翻译工具配置 - 移到最上方
        if self.enable_translation_tools:
            box = layout.box()
            box.label(text="翻译工具配置:", icon='FILE_TEXT')
            
            # 使用智能检测机制
            sdk_available = self.verify_sdk_installation()
            api_configured = self.verify_api_config()
            
            # SDK状态显示
            col = box.column()
            
            # 性能优化选项（放在顶部）
            if sdk_available and api_configured:
                perf_box = col.box()
                perf_col = perf_box.column()
                perf_col.label(text="性能优化选项:", icon='PREFERENCES')
                perf_col.prop(self, "sdk_check_enabled", text="启用SDK检测（已配置成功，可关闭以提高性能）")
                
                if not self.sdk_check_enabled:
                    row = perf_col.row()
                    row.operator("poptools.reset_verification", text="重新启用检测", icon='FILE_REFRESH')
                
                col.separator()
            
            if sdk_available and not self.should_show_restart_reminder():
                row = col.row()
                row.label(text="✓ 腾讯云SDK已安装", icon='CHECKMARK')
                
                # API密钥解锁密码
                col.separator()
                col.label(text="API密钥配置:", icon='KEY_HLT')
                col.prop(self, "api_password")
                
                # 解锁按钮
                if self.api_password:
                    row = col.row()
                    row.scale_y = 1.2
                    row.operator("poptools.unlock_api_keys", text="解锁API密钥", icon='UNLOCKED')
                
                # API配置状态检查
                if self.api_password:
                    from .crypto_utils import get_decrypted_api_key
                    secret_id = get_decrypted_api_key("tencent_secret_id", self.api_password)
                    secret_key = get_decrypted_api_key("tencent_secret_key", self.api_password)
                    
                    if secret_id and secret_key:
                        row = col.row()
                        row.label(text="✓ API密钥解锁成功,请记得保存首选项", icon='CHECKMARK')
                    else:
                        row = col.row()
                        row.alert = True
                        row.label(text="⚠ 密码错误或密钥未配置", icon='ERROR')
                        
                        # 显示帮助信息
                        help_box = col.box()
                        help_col = help_box.column(align=True)
                        help_col.label(text="使用说明:", icon='INFO')
                        help_col.label(text="• 请联系插件作者获取正确的解锁密码")
                        help_col.label(text="• 或在下方手动配置API密钥")
                else:
                    row = col.row()
                    row.alert = True
                    row.label(text="请输入API密钥解锁密码", icon='KEY_DEHLT')
                
                # 手动配置选项
                col.separator()
                manual_box = col.box()
                manual_col = manual_box.column()
                manual_col.label(text="手动配置API密钥（可选）:", icon='TOOL_SETTINGS')
                manual_col.prop(self, "tencent_secret_id")
                manual_col.prop(self, "tencent_secret_key")
                
                # 地域设置
                col.separator()
                col.prop(self, "tencent_region")
                
                # 验证按钮
                col.separator()
                verify_row = col.row()
                verify_row.scale_y = 1.2
                verify_row.operator("poptools.verify_api_config", text="验证API配置", icon='CHECKMARK')
                
            elif self.should_show_restart_reminder():
                # SDK安装成功，显示重启按钮（智能判断）
                row = col.row()
                row.label(text="✓ 腾讯云SDK安装成功", icon='CHECKMARK')
                
                row = col.row()
                row.alert = True
                row.label(text="请重启Blender以使用翻译功能", icon='INFO')
                
                # 重启按钮
                restart_row = col.row()
                restart_row.scale_y = 1.5
                restart_op = restart_row.operator("poptools.restart_blender", text="保存配置并重启Blender", icon='FILE_REFRESH')
                
                # 跳过重启按钮（用于测试或用户不想立即重启）
                skip_row = col.row()
                skip_row.operator("poptools.skip_restart_reminder", text="跳过重启提醒（手动重启后生效）", icon='CANCEL')
                
                # 标记重启提醒已显示
                self.mark_restart_reminder_shown()
                 
            else:
                # SDK未安装
                row = col.row()
                row.alert = True
                row.label(text="⚠ 腾讯云SDK未安装", icon='ERROR')
                
                # 安装按钮
                row = col.row()
                row.scale_y = 1.2
                row.operator("poptools.install_tencent_sdk", text="自动安装腾讯云SDK", icon='IMPORT')
                
                # 手动安装提示
                row = col.row()
                row.label(text="或手动运行: pip install tencentcloud-sdk-python")
        
        # 模块启用设置
        box = layout.box()
        box.label(text="模块设置 / Module Settings:", icon='PREFERENCES')
        
        col = box.column(align=True)
        col.prop(self, "enable_export_tools", icon='PACKAGE')
        col.prop(self, "enable_retex_tools", icon='TEXTURE')
        col.prop(self, "enable_obj_export_tools", icon='MESH_CUBE')
        col.prop(self, "enable_vertex_baker_tools", icon='MOD_VERTEX_WEIGHT')
        col.prop(self, "enable_translation_tools", icon='FILE_TEXT')
        col.prop(self, "enable_action_naming_tools", icon='ACTION')
        
        # 快捷键设置
        box = layout.box()
        box.label(text="快捷键设置:", icon='KEYINGSET')
        
        # 动作命名工具快捷键设置
        if self.enable_action_naming_tools:
            action_box = box.box()
            action_box.label(text="动作命名工具:", icon='ACTION')
            
            # 使用官方快捷键UI模块显示可编辑的快捷键
            if rna_keymap_ui:
                wm = bpy.context.window_manager
                kc = wm.keyconfigs.addon
                
                # 获取插件的快捷键映射
                from . import action_naming_tools
                if hasattr(action_naming_tools, 'addon_keymaps'):
                    for km, kmi in action_naming_tools.addon_keymaps:
                        if kmi.idname == 'poptools.action_naming_popup':
                            # 设置上下文指针
                            action_box.context_pointer_set("keymap", km.active())
                            # 使用官方UI绘制快捷键项
                            rna_keymap_ui.draw_kmi([], kc, km.active(), kmi, action_box, 0)
                            break
                    else:
                        action_box.label(text="未找到快捷键映射", icon='ERROR')
                else:
                    action_box.label(text="快捷键模块未正确加载", icon='ERROR')
            else:
                # 备用显示方式（如果rna_keymap_ui不可用）
                wm = bpy.context.window_manager
                kc = wm.keyconfigs.addon
                if kc:
                    km = kc.keymaps.get('3D View')
                    if km:
                        for kmi in km.keymap_items:
                            if kmi.idname == 'poptools.action_naming_popup':
                                row = action_box.row()
                                row.label(text="动作命名弹出面板:")
                                
                                # 显示快捷键组合
                                key_text = ""
                                if kmi.ctrl:
                                    key_text += "Ctrl+"
                                if kmi.shift:
                                    key_text += "Shift+"
                                if kmi.alt:
                                    key_text += "Alt+"
                                key_text += kmi.type
                                
                                row.label(text=key_text, icon='EVENT_D')
        
        # 纹理管理工具快捷键设置
        if self.enable_retex_tools:
            retex_box = box.box()
            retex_box.label(text="纹理管理工具:", icon='TEXTURE')
            
            # 使用官方快捷键UI模块显示可编辑的快捷键
            if rna_keymap_ui:
                wm = bpy.context.window_manager
                kc = wm.keyconfigs.addon
                
                # 获取插件的快捷键映射
                from . import retex_tools
                if hasattr(retex_tools, 'addon_keymaps'):
                    for km, kmi in retex_tools.addon_keymaps:
                        if kmi.idname == 'rt.texture_manager_popup':
                            # 设置上下文指针
                            retex_box.context_pointer_set("keymap", km.active())
                            # 使用官方UI绘制快捷键项
                            rna_keymap_ui.draw_kmi([], kc, km.active(), kmi, retex_box, 0)
                            break
                    else:
                        retex_box.label(text="未找到快捷键映射", icon='ERROR')
                else:
                    retex_box.label(text="快捷键模块未正确加载", icon='ERROR')
            else:
                # 备用显示方式（如果rna_keymap_ui不可用）
                wm = bpy.context.window_manager
                kc = wm.keyconfigs.addon
                if kc:
                    km = kc.keymaps.get('3D View')
                    if km:
                        for kmi in km.keymap_items:
                            if kmi.idname == 'rt.texture_manager_popup':
                                row = retex_box.row()
                                row.label(text="纹理管理弹出面板:")
                                
                                # 显示快捷键组合
                                key_text = ""
                                if kmi.ctrl:
                                    key_text += "Ctrl+"
                                if kmi.shift:
                                    key_text += "Shift+"
                                if kmi.alt:
                                    key_text += "Alt+"
                                key_text += kmi.type
                                
                                row.label(text=key_text, icon='EVENT_T')
                                break
                        else:
                            box.label(text="未找到快捷键映射", icon='ERROR')
                    else:
                        box.label(text="未找到3D视图键映射", icon='ERROR')
                
                # 显示提示信息
                row = box.row()
                row.label(text="请在 编辑 > 偏好设置 > 快捷键 中搜索 'poptools' 来修改快捷键", icon='INFO')
        
        col.prop(self, "export_import_enable", icon='IMPORT')
        
        # Global settings section
        box = layout.box()
        box.label(text="全局设置:", icon='WORLD')
        
        col = box.column()
        col.prop(self, "default_export_path")
        col.prop(self, "auto_save_before_export")
        col.prop(self, "show_export_notifications")

# Registration
classes = (
    POPTOOLS_MT_reset_hotkey,
    POPTOOLS_OT_reset_hotkey,
    POPTOOLS_OT_unlock_api_keys,
    POPTOOLS_OT_install_tencent_sdk,
    POPTOOLS_OT_restart_blender,
    POPTOOLS_OT_skip_restart_reminder,
    POPTOOLS_OT_reset_verification,
    POPTOOLS_OT_verify_api_config,
    PopToolsPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)