# -*- coding: utf-8 -*-
"""
PopTools Translation Tools
翻译工具模块 - 支持腾讯云翻译API
"""

import bpy
import bmesh
import json
import sys
import os
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, EnumProperty, BoolProperty, CollectionProperty
from .utils import show_message_box

# 尝试导入腾讯云SDK
try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.tmt.v20180321 import tmt_client, models
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("[翻译工具] 腾讯云SDK未安装，请运行: pip install tencentcloud-sdk-python")

# 腾讯云翻译API配置
class TencentTranslateAPI:
    """腾讯云翻译API封装类"""
    
    def __init__(self, secret_id="", secret_key="", region="ap-beijing"):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region
        
        # 检查SDK是否可用
        if not SDK_AVAILABLE:
            raise ImportError("腾讯云SDK未安装，请运行: pip install tencentcloud-sdk-python")
            
        # 初始化客户端
        self._init_client()
        
    def _init_client(self):
        """初始化腾讯云客户端"""
        try:
            # 验证API密钥
            print(f"[调试] TencentTranslateAPI._init_client: secret_id='{self.secret_id}', secret_key='{self.secret_key}'")
            
            if not self.secret_id or not self.secret_key:
                raise Exception(f"API密钥不能为空: secret_id='{self.secret_id}', secret_key='{self.secret_key}'")
            
            if not self.secret_id.strip() or not self.secret_key.strip():
                raise Exception(f"API密钥不能为空白字符: secret_id='{self.secret_id}', secret_key='{self.secret_key}'")
            
            # 实例化一个认证对象，入参需要传入腾讯云账户secretId，secretKey
            cred = credential.Credential(self.secret_id, self.secret_key)
            
            # 实例化一个http选项，可以没有实例化，没有实例化时会使用默认值
            httpProfile = HttpProfile()
            httpProfile.endpoint = "tmt.tencentcloudapi.com"
            
            # 实例化一个client选项，可以没有实例化，没有实例化时会使用默认值
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            
            # 实例化要请求产品的client对象，clientProfile是可选的
            self.client = tmt_client.TmtClient(cred, self.region, clientProfile)
            
        except Exception as e:
            raise Exception(f"初始化腾讯云客户端失败: {str(e)}")
    
    @classmethod
    def from_preferences(cls):
        """从插件首选项创建API实例"""
        prefs = bpy.context.preferences.addons[__package__].preferences
        
        # 获取解密后的密钥
        secret_id = prefs.get_decrypted_secret_id()
        secret_key = prefs.get_decrypted_secret_key()
        
        print(f"[调试] from_preferences: secret_id='{secret_id}', secret_key='{secret_key}'")
        print(f"[调试] from_preferences: api_password='{prefs.api_password}'")
        print(f"[调试] from_preferences: manual_secret_id='{prefs.tencent_secret_id}'")
        print(f"[调试] from_preferences: manual_secret_key='{prefs.tencent_secret_key}'")
        
        return cls(
            secret_id=secret_id,
            secret_key=secret_key,
            region=prefs.tencent_region
        )
    
    def translate_text(self, text, source_lang="auto", target_lang="zh"):
        """翻译文本"""
        # 验证API密钥
        if not self.secret_id or not self.secret_key:
            return {"error": "请在插件首选项中配置腾讯云API密钥"}
            
        if not self.secret_id.strip() or not self.secret_key.strip():
            return {"error": "API密钥不能为空，请检查插件首选项配置"}
            
        print(f"[翻译调试] 开始翻译: '{text}' ({source_lang} -> {target_lang})")
        print(f"[翻译调试] 使用地域: {self.region}")
        print(f"[翻译调试] Secret ID: {self.secret_id[:8]}...")
            
        try:
            # 实例化一个请求对象，每个接口都会对应一个request对象
            req = models.TextTranslateRequest()
            
            # 设置请求参数
            req.SourceText = text
            req.Source = source_lang
            req.Target = target_lang
            req.ProjectId = 0
            
            print(f"[翻译调试] 发送请求: {req}")
            
            # 返回的resp是一个TextTranslateResponse的实例，与请求对象对应
            resp = self.client.TextTranslate(req)
            
            print(f"[翻译调试] API响应: {resp.to_json_string()}")
            
            # 解析响应
            translated_text = resp.TargetText
            print(f"[翻译调试] 翻译成功: '{translated_text}'")
            
            return {
                "translated_text": translated_text,
                "source_lang": resp.Source,
                "target_lang": resp.Target
            }
                
        except TencentCloudSDKException as e:
            error_code = e.code
            error_message = e.message
            
            # 根据错误代码提供具体的解决建议
            if error_code == 'AuthFailure.SecretIdNotFound':
                detailed_error = f"Secret ID无效: {error_message}\n请检查插件首选项中的Secret ID是否正确"
            elif error_code == 'AuthFailure.SignatureFailure':
                detailed_error = f"签名验证失败: {error_message}\n请检查Secret Key是否正确，或尝试重新生成API密钥"
            elif error_code == 'AuthFailure.TokenFailure':
                detailed_error = f"Token验证失败: {error_message}\n请检查API密钥是否已过期或被禁用"
            elif error_code == 'LimitExceeded':
                detailed_error = f"API调用频率超限: {error_message}\n请稍后重试"
            elif error_code == 'ResourceUnavailable':
                detailed_error = f"服务不可用: {error_message}\n请检查所选地域是否支持翻译服务"
            elif error_code == 'InvalidParameter':
                detailed_error = f"参数错误: {error_message}\n请检查输入的语言代码是否正确"
            else:
                detailed_error = f"API错误 [{error_code}]: {error_message}"
            
            print(f"[翻译调试] API错误: {detailed_error}")
            return {"error": detailed_error}
            
        except Exception as e:
            error_detail = f"未知错误: {str(e)}\n请检查插件配置或联系开发者"
            print(f"[翻译调试] {error_detail}")
            return {"error": error_detail}
    


# 翻译工具属性组
class TranslationToolsSettings(PropertyGroup):
    """翻译工具设置"""
    
    # 翻译设置
    source_language: EnumProperty(
        name="源语言",
        description="选择源语言",
        items=[
            ('auto', "自动检测", "自动检测源语言"),
            ('zh', "中文", "中文"),
            ('en', "英语", "英语"),
            ('ja', "日语", "日语"),
            ('ko', "韩语", "韩语"),
            ('fr', "法语", "法语"),
            ('de', "德语", "德语"),
            ('es', "西班牙语", "西班牙语"),
            ('ru', "俄语", "俄语"),
        ],
        default='auto'
    )
    
    target_language: EnumProperty(
        name="目标语言",
        description="选择目标语言",
        items=[
            ('zh', "中文", "中文"),
            ('en', "英语", "英语"),
            ('ja', "日语", "日语"),
            ('ko', "韩语", "韩语"),
            ('fr', "法语", "法语"),
            ('de', "德语", "德语"),
            ('es', "西班牙语", "西班牙语"),
            ('ru', "俄语", "俄语"),
        ],
        default='en'
    )
    
    # 翻译文本
    input_text: StringProperty(
        name="输入文本",
        description="要翻译的文本",
        default="",
        maxlen=5000
    )
    
    output_text: StringProperty(
        name="翻译结果",
        description="翻译后的文本",
        default="",
        maxlen=5000
    )
    
    # 批量翻译设置
    batch_translate_objects: BoolProperty(
        name="批量翻译对象名称",
        description="批量翻译选中对象的名称",
        default=False
    )
    
    batch_translate_materials: BoolProperty(
        name="批量翻译材质名称",
        description="批量翻译场景中的材质名称",
        default=False
    )

# 翻译操作符
class POPTOOLS_OT_translate_text(Operator):
    """翻译文本操作符"""
    bl_idname = "poptools.translate_text"
    bl_label = "翻译文本"
    bl_description = "使用腾讯云API翻译文本"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.poptools_props.translation_tools
        
        # 检查SDK是否可用
        if not SDK_AVAILABLE:
            show_message_box("腾讯云SDK未安装\n请运行: pip install tencentcloud-sdk-python", "SDK错误", 'ERROR')
            return {'CANCELLED'}
        
        if not settings.input_text.strip():
            show_message_box("请输入要翻译的文本", "错误", 'ERROR')
            return {'CANCELLED'}
        
        try:
            # 从插件首选项创建翻译API实例
            translator = TencentTranslateAPI.from_preferences()
        except Exception as e:
            show_message_box(f"API配置错误: {str(e)}", "配置错误", 'ERROR')
            return {'CANCELLED'}
        
        # 执行翻译
        result = translator.translate_text(
            text=settings.input_text,
            source_lang=settings.source_language,
            target_lang=settings.target_language
        )
        
        if "error" in result:
            show_message_box(result["error"], "翻译错误", 'ERROR')
            return {'CANCELLED'}
        else:
            settings.output_text = result["translated_text"]
            show_message_box("翻译完成！", "成功", 'INFO')
            return {'FINISHED'}

class POPTOOLS_OT_batch_translate_objects(Operator):
    """批量翻译对象名称"""
    bl_idname = "poptools.batch_translate_objects"
    bl_label = "批量翻译对象名称"
    bl_description = "批量翻译选中对象的名称"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.poptools_props.translation_tools
        selected_objects = context.selected_objects
        
        # 检查SDK是否可用
        if not SDK_AVAILABLE:
            show_message_box("腾讯云SDK未安装\n请运行: pip install tencentcloud-sdk-python", "SDK错误", 'ERROR')
            return {'CANCELLED'}
        
        if not selected_objects:
            show_message_box("请先选择要翻译名称的对象", "错误", 'ERROR')
            return {'CANCELLED'}
        
        try:
            # 从插件首选项创建翻译API实例
            translator = TencentTranslateAPI.from_preferences()
        except Exception as e:
            show_message_box(f"API配置错误: {str(e)}", "配置错误", 'ERROR')
            return {'CANCELLED'}
        
        translated_count = 0
        failed_count = 0
        
        for obj in selected_objects:
            if obj.name.strip():
                result = translator.translate_text(
                    text=obj.name,
                    source_lang=settings.source_language,
                    target_lang=settings.target_language
                )
                
                if "error" not in result:
                    obj.name = result["translated_text"]
                    translated_count += 1
                else:
                    failed_count += 1
                    print(f"翻译对象 {obj.name} 失败: {result['error']}")
        
        message = f"翻译完成！成功: {translated_count}, 失败: {failed_count}"
        show_message_box(message, "批量翻译结果", 'INFO')
        return {'FINISHED'}

class POPTOOLS_OT_clear_translation(Operator):
    """清空翻译内容"""
    bl_idname = "poptools.clear_translation"
    bl_label = "清空"
    bl_description = "清空输入和输出文本"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.poptools_props.translation_tools
        settings.input_text = ""
        settings.output_text = ""
        return {'FINISHED'}

# ============================================================================
# 翻译工具函数 / Translation Tool Functions
# ============================================================================

def translate_text_tool(input_text, source_lang='zh', target_lang='en', secret_id=None, secret_key=None, region=None):
    """翻译工具函数，供其他模块调用
    
    Args:
        input_text (str): 要翻译的文本
        source_lang (str): 源语言代码，默认'zh'
        target_lang (str): 目标语言代码，默认'en'
        secret_id (str): 腾讯云API Secret ID，如果为None则从插件首选项获取
        secret_key (str): 腾讯云API Secret Key，如果为None则从插件首选项获取
        region (str): 腾讯云地域，如果为None则从插件首选项获取
    
    Returns:
        str: 翻译后的文本，如果翻译失败返回原文本
    """
    if not input_text or not input_text.strip():
        return ""
    
    # 检查SDK是否可用
    if not SDK_AVAILABLE:
        print("[翻译工具] 腾讯云SDK未安装，请运行: pip install tencentcloud-sdk-python")
        return input_text
    
    try:
        # 如果没有提供API密钥参数，则从插件首选项获取
        if secret_id is None or secret_key is None or region is None:
            try:
                api = TencentTranslateAPI.from_preferences()
                print(f"[翻译工具] 从插件首选项获取API配置")
            except Exception as e:
                print(f"[翻译工具] 无法从插件首选项获取API配置: {e}")
                return input_text
        else:
            # 使用提供的参数创建API实例
            api = TencentTranslateAPI(secret_id, secret_key, region or 'ap-beijing')
            print(f"[翻译工具] 使用提供的API配置")
        
        print(f"[翻译工具] 开始翻译: '{input_text}' 从 {source_lang} 到 {target_lang}")
        result = api.translate_text(input_text, source_lang, target_lang)
        print(f"[翻译工具] API返回结果: {result}")
        
        # 检查返回结果是否包含错误
        if isinstance(result, dict):
            if "error" in result:
                print(f"[翻译工具] 翻译API错误: {result['error']}")
                return input_text  # 翻译失败时返回原文本
            elif "translated_text" in result:
                translated = result["translated_text"]
                print(f"[翻译工具] 翻译成功: '{translated}'")
                return translated  # 返回翻译后的文本字符串
            else:
                print(f"[翻译工具] 翻译API返回格式错误，完整结果: {result}")
                return input_text
        else:
            # 如果返回的不是字典，直接返回
            print(f"[翻译工具] API返回非字典类型: {type(result)}, 值: {result}")
            return str(result)
    except Exception as e:
        print(f"[翻译工具] 翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return input_text  # 翻译失败时返回原文本

class POPTOOLS_OT_swap_languages(Operator):
    """交换源语言和目标语言"""
    bl_idname = "poptools.swap_languages"
    bl_label = "交换语言"
    bl_description = "交换源语言和目标语言"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.poptools_props.translation_tools
        
        # 交换语言设置
        temp = settings.source_language
        settings.source_language = settings.target_language
        settings.target_language = temp
        
        # 如果目标语言变成了auto，改为zh
        if settings.target_language == 'auto':
            settings.target_language = 'zh'
            
        return {'FINISHED'}

# ============================================================================
# 注册和注销 / Registration and Unregistration
# ============================================================================

classes = [
    TranslationToolsSettings,
    POPTOOLS_OT_translate_text,
    POPTOOLS_OT_batch_translate_objects,
    POPTOOLS_OT_clear_translation,
    POPTOOLS_OT_swap_languages,
    # POPTOOLS_PT_translation_tools,  # 面板已删除 - 主要用于被其他模块调用
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()