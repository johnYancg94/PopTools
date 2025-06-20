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
            doubao_api_key = prefs.get_decrypted_doubao_api_key()
            
            success_count = 0
            if secret_id and secret_key:
                success_count += 1
                print(f"[解锁成功] 腾讯云 Secret ID: {secret_id[:8]}..., Secret Key: {secret_key[:8]}...")
            
            if doubao_api_key:
                success_count += 1
                print(f"[解锁成功] Doubao API Key: {doubao_api_key[:8]}...")
            
            if success_count > 0:
                if success_count == 2:
                    self.report({'INFO'}, "所有API密钥解锁成功并已自动填入")
                else:
                    self.report({'INFO'}, "部分API密钥解锁成功并已自动填入")
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

class POPTOOLS_OT_check_sdk_status(Operator):
    """手动检测SDK状态"""
    bl_idname = "poptools.check_sdk_status"
    bl_label = "检测SDK状态"
    bl_description = "手动检测腾讯云SDK是否已正确安装"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        try:
            # 尝试导入腾讯云SDK
            import tencentcloud
            from tencentcloud.common import credential
            from tencentcloud.tmt.v20180321 import tmt_client, models
            
            # SDK导入成功，重置安装标志
            prefs.sdk_install_success = False
            
            # 强制刷新UI
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            for area in context.screen.areas:
                if area.type == 'PREFERENCES':
                    area.tag_redraw()
            
            self.report({'INFO'}, "SDK检测成功！腾讯云SDK已正确安装并可以使用")
            
        except ImportError as e:
            self.report({'WARNING'}, f"SDK检测失败：腾讯云SDK未安装或安装不完整 - {str(e)}")
        except Exception as e:
            self.report({'ERROR'}, f"SDK检测过程中发生错误：{str(e)}")
            
        return {'FINISHED'}

class POPTOOLS_OT_install_openai_sdk(Operator):
    """安装OpenAI SDK"""
    bl_idname = "poptools.install_openai_sdk"
    bl_label = "安装OpenAI SDK"
    bl_description = "自动安装OpenAI Python SDK（用于Doubao AI翻译）"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            # 获取Python可执行文件路径
            python_exe = sys.executable
            
            # 安装OpenAI SDK
            self.report({'INFO'}, "正在安装OpenAI SDK，请稍候...")
            
            # 使用subprocess运行pip install命令
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "--upgrade", "openai>=1.0"],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.report({'INFO'}, "OpenAI SDK安装成功！请重启Blender以使用AI翻译功能。")
                # 设置安装成功标志
                context.preferences.addons[__package__].preferences.openai_sdk_install_success = True
                # 强制刷新UI以显示重启提示
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                # 强制更新首选项面板
                for area in context.screen.areas:
                    if area.type == 'PREFERENCES':
                        area.tag_redraw()
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                self.report({'ERROR'}, f"OpenAI SDK安装失败: {error_msg}")
                
        except subprocess.TimeoutExpired:
            self.report({'ERROR'}, "安装超时，请检查网络连接后重试")
        except Exception as e:
            self.report({'ERROR'}, f"安装过程中发生错误: {str(e)}")
            
        return {'FINISHED'}

class POPTOOLS_OT_check_openai_sdk_status(Operator):
    """手动检测OpenAI SDK状态"""
    bl_idname = "poptools.check_openai_sdk_status"
    bl_label = "检测OpenAI SDK状态"
    bl_description = "手动检测OpenAI SDK是否已正确安装"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        try:
            # 尝试导入OpenAI SDK
            import openai
            
            # SDK导入成功，重置安装标志
            prefs.openai_sdk_install_success = False
            
            # 强制刷新UI
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            for area in context.screen.areas:
                if area.type == 'PREFERENCES':
                    area.tag_redraw()
            
            self.report({'INFO'}, "OpenAI SDK检测成功！OpenAI SDK已正确安装并可以使用")
            
        except ImportError as e:
            self.report({'WARNING'}, f"OpenAI SDK检测失败：OpenAI SDK未安装或安装不完整 - {str(e)}")
        except Exception as e:
            self.report({'ERROR'}, f"OpenAI SDK检测过程中发生错误：{str(e)}")
            
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
        from .encryption_utils import get_decrypted_api_key
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
        from .encryption_utils import get_decrypted_api_key
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
    
    def get_decrypted_doubao_api_key(self):
        """获取解密后的Doubao API Key"""
        from .encryption_utils import get_decrypted_api_key
        if self.api_password:
            decrypted = get_decrypted_api_key("doubao_api_key", self.api_password)
            print(f"[调试] 解密Doubao API Key: 密码='{self.api_password}', 解密结果='{decrypted}'")
            if decrypted:
                # 解密成功，自动填入手动配置字段
                if self.doubao_api_key != decrypted:
                    self.doubao_api_key = decrypted
                    print(f"[调试] 自动更新手动配置的Doubao API Key: '{decrypted}'")
                return decrypted
        # 如果解密失败，尝试返回手动配置的密钥
        manual_key = self.doubao_api_key
        print(f"[调试] 使用手动配置的Doubao API Key: '{manual_key}'")
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
    
    # Doubao AI翻译配置
    doubao_api_key: StringProperty(
        name="Doubao API Key",
        description="Doubao AI翻译API密钥（ARK_API_KEY）",
        default="",
        subtype='PASSWORD'
    )
    
    # OpenAI SDK安装成功标志
    openai_sdk_install_success: BoolProperty(
        name="OpenAI SDK安装成功",
        description="标记OpenAI SDK是否安装成功",
        default=False
    )
    
    
    def draw(self, context):
        layout = self.layout
        
        # 翻译工具配置 - 移到最上方
        if self.enable_translation_tools:
            box = layout.box()
            box.label(text="翻译工具配置:", icon='FILE_TEXT')
            
            # SDK状态检查
            try:
                import tencentcloud
                sdk_available = True
            except ImportError:
                sdk_available = False
            
            # SDK状态显示
            col = box.column()
            if sdk_available and not self.sdk_install_success:
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
                    from .encryption_utils import get_decrypted_api_key
                    secret_id = get_decrypted_api_key("tencent_secret_id", self.api_password)
                    secret_key = get_decrypted_api_key("tencent_secret_key", self.api_password)
                    doubao_api_key = get_decrypted_api_key("doubao_api_key", self.api_password)
                    
                    # 统计解锁成功的密钥数量
                    success_count = 0
                    if secret_id and secret_key:
                        success_count += 1
                    if doubao_api_key:
                        success_count += 1
                    
                    if success_count > 0:
                        row = col.row()
                        if success_count == 2:
                            row.label(text="✓ 所有API密钥解锁成功,请记得保存首选项", icon='CHECKMARK')
                        else:
                            row.label(text="✓ 部分API密钥解锁成功,请记得保存首选项", icon='CHECKMARK')
                        
                        # 显示具体解锁状态
                        status_box = col.box()
                        status_col = status_box.column(align=True)
                        status_col.label(text="解锁状态:", icon='INFO')
                        if secret_id and secret_key:
                            status_col.label(text="• 腾讯云API: ✓ 已解锁")
                        else:
                            status_col.label(text="• 腾讯云API: ✗ 未解锁")
                        if doubao_api_key:
                            status_col.label(text="• Doubao AI API: ✓ 已解锁")
                        else:
                            status_col.label(text="• Doubao AI API: ✗ 未解锁")
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
                
                # 腾讯云API配置
                tencent_box = manual_col.box()
                tencent_col = tencent_box.column()
                tencent_col.label(text="腾讯云翻译API:", icon='WORLD')
                tencent_col.prop(self, "tencent_secret_id")
                tencent_col.prop(self, "tencent_secret_key")
                
                # Doubao AI API配置
                doubao_box = manual_col.box()
                doubao_col = doubao_box.column()
                doubao_col.label(text="Doubao AI翻译API:", icon='OUTLINER_OB_LIGHT')
                doubao_col.prop(self, "doubao_api_key")
                
                # 地域设置
                col.separator()
                col.prop(self, "tencent_region")
                
            elif self.sdk_install_success:
                # SDK安装成功，显示重启按钮
                row = col.row()
                row.label(text="✓ 腾讯云SDK安装成功", icon='CHECKMARK')
                
                row = col.row()
                row.alert = True
                row.label(text="请重启Blender以使用翻译功能", icon='INFO')
                
                # 按钮行：重启和手动检测
                button_row = col.row(align=True)
                button_row.scale_y = 1.3
                
                # 重启按钮
                restart_btn = button_row.row()
                restart_btn.scale_x = 2.0
                restart_btn.operator("poptools.restart_blender", text="保存配置并重启Blender", icon='FILE_REFRESH')
                
                # 手动检测按钮
                check_btn = button_row.row()
                check_btn.operator("poptools.check_sdk_status", text="手动检测SDK", icon='VIEWZOOM')
                 
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
            
            # Doubao AI翻译配置
            col.separator()
            ai_box = box.box()
            ai_box.label(text="Doubao AI翻译配置:", icon='OUTLINER_OB_LIGHT')
            
            # OpenAI SDK状态检查
            try:
                import openai
                openai_sdk_available = True
            except ImportError:
                openai_sdk_available = False
            
            ai_col = ai_box.column()
            if openai_sdk_available and not self.openai_sdk_install_success:
                row = ai_col.row()
                row.label(text="✓ OpenAI SDK已安装", icon='CHECKMARK')
                
                # API密钥配置
                ai_col.separator()
                ai_col.label(text="Doubao API密钥配置:", icon='KEY_HLT')
                ai_col.prop(self, "doubao_api_key")
                
                # 配置说明
                help_box = ai_col.box()
                help_col = help_box.column(align=True)
                help_col.label(text="配置说明:", icon='INFO')
                help_col.label(text="• 请在豆包官网申请API密钥")
                help_col.label(text="• 或设置环境变量 ARK_API_KEY")
                help_col.label(text="• AI翻译专为游戏角色动作命名优化")
                
            elif self.openai_sdk_install_success:
                # OpenAI SDK安装成功，显示重启按钮
                row = ai_col.row()
                row.label(text="✓ OpenAI SDK安装成功", icon='CHECKMARK')
                
                row = ai_col.row()
                row.alert = True
                row.label(text="请重启Blender以使用AI翻译功能", icon='INFO')
                
                # 按钮行：重启和手动检测
                button_row = ai_col.row(align=True)
                button_row.scale_y = 1.3
                
                # 重启按钮
                restart_btn = button_row.row()
                restart_btn.scale_x = 2.0
                restart_btn.operator("poptools.restart_blender", text="保存配置并重启Blender", icon='FILE_REFRESH')
                
                # 手动检测按钮
                check_btn = button_row.row()
                check_btn.operator("poptools.check_openai_sdk_status", text="手动检测OpenAI SDK", icon='VIEWZOOM')
                
            else:
                # OpenAI SDK未安装
                row = ai_col.row()
                row.alert = True
                row.label(text="⚠ OpenAI SDK未安装", icon='ERROR')
                
                # 安装按钮
                row = ai_col.row()
                row.scale_y = 1.2
                row.operator("poptools.install_openai_sdk", text="自动安装OpenAI SDK", icon='IMPORT')
                
                # 手动安装提示
                row = ai_col.row()
                row.label(text="或手动运行: pip install --upgrade openai>=1.0")
        
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
    POPTOOLS_OT_check_sdk_status,
    POPTOOLS_OT_install_openai_sdk,
    POPTOOLS_OT_check_openai_sdk_status,
    PopToolsPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)