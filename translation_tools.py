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
import time
import threading
import re
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, EnumProperty, BoolProperty, CollectionProperty
from .doubao_responses import DEFAULT_DOUBAO_MODEL, build_translation_input, extract_response_text
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

# 尝试导入OpenAI SDK（用于Doubao）
try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    print("[翻译工具] OpenAI SDK未安装，请运行: pip install --upgrade 'openai>=1.0'")


DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_REQUEST_TIMEOUT = 15.0
_DOUBAO_CLIENT_CACHE = {}
_DOUBAO_TRANSLATION_CACHE = {}
_AI_TRANSLATION_JOBS = {}
_AI_TRANSLATION_JOBS_LOCK = threading.Lock()
LOCAL_TRANSLATION_DICTIONARY_PATH = os.path.join(os.path.dirname(__file__), "local_translation_dictionary.json")


def load_local_translation_dictionary():
    try:
        with open(LOCAL_TRANSLATION_DICTIONARY_PATH, "r", encoding="utf-8") as dictionary_file:
            payload = json.load(dictionary_file)
    except Exception as exc:
        print(f"[AI翻译工具] 本地词典读取失败: {exc}")
        return {}, {}

    exact = payload.get("exact", {})
    tokens = payload.get("tokens", {})
    if not isinstance(exact, dict):
        exact = {}
    if not isinstance(tokens, dict):
        tokens = {}
    return exact, tokens


LOCAL_TRANSLATION_EXACT, LOCAL_TRANSLATION_TOKENS = load_local_translation_dictionary()


def to_lower_camel(words):
    cleaned_words = [word for word in words if word]
    if not cleaned_words:
        return ""
    first = cleaned_words[0][:1].lower() + cleaned_words[0][1:]
    rest = [word[:1].upper() + word[1:] for word in cleaned_words[1:]]
    return first + "".join(rest)


def sanitize_local_translation(text):
    text = re.sub(r"[^0-9A-Za-z]+", "", text or "")
    if not text:
        return ""
    return text[:1].lower() + text[1:]


def local_rule_translate(input_text):
    """常见资产名本地翻译；命中时不调用AI。"""
    text = (input_text or "").strip()
    if not text:
        return ""

    compact_text = re.sub(r"[\s_\\/\-·,，.。:：;；()（）\[\]【】]+", "", text)
    if not compact_text:
        return ""

    exact = LOCAL_TRANSLATION_EXACT.get(text) or LOCAL_TRANSLATION_EXACT.get(compact_text)
    if exact:
        return sanitize_local_translation(exact)

    token_keys = sorted(LOCAL_TRANSLATION_TOKENS.keys(), key=len, reverse=True)
    words = []
    index = 0
    while index < len(compact_text):
        matched_key = ""
        for token_key in token_keys:
            if compact_text.startswith(token_key, index):
                matched_key = token_key
                break
        if not matched_key:
            return ""
        words.append(LOCAL_TRANSLATION_TOKENS[matched_key])
        index += len(matched_key)

    return sanitize_local_translation(to_lower_camel(words))


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


# Doubao AI翻译API配置
class DoubaoTranslateAPI:
    """Doubao AI翻译API封装类"""
    
    def __init__(self, api_key="", base_url=DOUBAO_BASE_URL, model=DEFAULT_DOUBAO_MODEL):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        # 检查SDK是否可用
        if not OPENAI_SDK_AVAILABLE:
            raise ImportError("OpenAI SDK未安装，请运行: pip install --upgrade 'openai>=1.0'")
            
        # 初始化客户端
        self._init_client()
        
    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            # 验证API密钥
            print(f"[调试] DoubaoTranslateAPI._init_client: api_key='{self.api_key[:8]}...' if self.api_key else 'None'")
            
            if not self.api_key:
                raise Exception(f"API密钥不能为空: api_key='{self.api_key}'")
            
            if not self.api_key.strip():
                raise Exception(f"API密钥不能为空白字符: api_key='{self.api_key}'")
            
            # 初始化OpenAI客户端
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=DOUBAO_REQUEST_TIMEOUT,
                max_retries=0,
            )
            
        except Exception as e:
            raise Exception(f"初始化Doubao客户端失败: {str(e)}")
    
    @classmethod
    def from_preferences(cls):
        """从插件首选项创建API实例"""
        prefs = bpy.context.preferences.addons[__package__].preferences
        
        # 手动配置字段已被解锁流程写入时，优先直接复用，避免每次点击都重新解密。
        api_key = getattr(prefs, "doubao_api_key", "").strip()
        if not api_key:
            api_key = prefs.get_decrypted_doubao_api_key()
        
        if not api_key:
            # 如果解密失败，尝试从环境变量获取
            api_key = os.getenv('ARK_API_KEY')
        
        print(f"[调试] from_preferences: doubao_api_key='{api_key[:8]}...' if api_key else 'None'")

        cache_key = (api_key, DOUBAO_BASE_URL, DEFAULT_DOUBAO_MODEL)
        cached_api = _DOUBAO_CLIENT_CACHE.get(cache_key)
        if cached_api:
            return cached_api

        api = cls(
            api_key=api_key,
            base_url=DOUBAO_BASE_URL,
            model=DEFAULT_DOUBAO_MODEL
        )
        _DOUBAO_CLIENT_CACHE[cache_key] = api
        return api

    def _translate_with_chat_completions(self, text, system_prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=32,
        )
        choices = getattr(response, "choices", []) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", "") if message else ""
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
                else:
                    parts.append(getattr(item, "text", ""))
            content = "".join(parts)
        return str(content).strip()

    def _translate_with_responses(self, text, system_prompt):
        response = self.client.responses.create(
            model=self.model,
            input=build_translation_input(system_prompt, text),
            max_output_tokens=32,
        )
        return extract_response_text(response)
    
    def translate_text(self, text, system_prompt=None):
        """使用AI翻译文本"""
        # 验证API密钥
        if not self.api_key:
            return {"error": "请配置Doubao API密钥（ARK_API_KEY环境变量）"}
            
        if not self.api_key.strip():
            return {"error": "API密钥不能为空，请检查ARK_API_KEY环境变量"}
            
        # 默认系统提示词
        if system_prompt is None:
            system_prompt = "请将输入的中文动作名称翻译为简洁的英文。要求:\n1. 尽量使用单个单词\n2. 必须简洁精确只表达最核心的语义即可\n3. 不含任何符号和空格\n4. 首字母小写\n5. 多词组合时,首字母小写,后续单词首字母大写,例如: walkRunFast"
            
        cache_key = (self.model, system_prompt, text.strip())
        cached_translation = _DOUBAO_TRANSLATION_CACHE.get(cache_key)
        if cached_translation:
            print(f"[AI翻译调试] 使用缓存翻译: '{cached_translation}'")
            return {
                "translated_text": cached_translation,
                "source_lang": "zh",
                "target_lang": "en"
            }

        print(f"[AI翻译调试] 开始翻译: '{text}'")
        print(f"[AI翻译调试] 使用模型: {self.model}")
        print(f"[AI翻译调试] API Key: {self.api_key[:8]}...")
            
        try:
            started_at = time.perf_counter()
            try:
                translated_text = self._translate_with_chat_completions(text, system_prompt)
                api_mode = "chat.completions"
            except Exception as chat_exc:
                print(f"[AI翻译调试] Chat Completions调用失败，回退Responses: {chat_exc}")
                translated_text = self._translate_with_responses(text, system_prompt)
                api_mode = "responses"
            
            elapsed = time.perf_counter() - started_at
            print(f"[AI翻译调试] API响应成功: mode={api_mode}, elapsed={elapsed:.2f}s")
            
            if not translated_text:
                return {"error": "AI翻译响应为空"}
            _DOUBAO_TRANSLATION_CACHE[cache_key] = translated_text
            print(f"[AI翻译调试] 翻译成功: '{translated_text}'")
            
            return {
                "translated_text": translated_text,
                "source_lang": "zh",
                "target_lang": "en"
            }
                
        except Exception as e:
            error_detail = f"AI翻译错误: {str(e)}"
            print(f"[AI翻译调试] {error_detail}")
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

class POPTOOLS_OT_ai_translate_text(Operator):
    """AI翻译文本操作符"""
    bl_idname = "poptools.ai_translate_text"
    bl_label = "AI翻译文本"
    bl_description = "使用Doubao AI翻译文本"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.poptools_props.translation_tools
        
        # 检查OpenAI SDK是否可用
        if not OPENAI_SDK_AVAILABLE:
            show_message_box("OpenAI SDK未安装\n请运行: pip install --upgrade 'openai>=1.0'", "SDK错误", 'ERROR')
            return {'CANCELLED'}
        
        if not settings.input_text.strip():
            show_message_box("请输入要翻译的文本", "错误", 'ERROR')
            return {'CANCELLED'}
        
        try:
            # 从插件首选项创建AI翻译API实例
            translator = DoubaoTranslateAPI.from_preferences()
        except Exception as e:
            show_message_box(f"AI API配置错误: {str(e)}", "配置错误", 'ERROR')
            return {'CANCELLED'}
        
        # 执行AI翻译
        result = translator.translate_text(text=settings.input_text)
        
        if "error" in result:
            show_message_box(result["error"], "AI翻译错误", 'ERROR')
            return {'CANCELLED'}
        else:
            settings.output_text = result["translated_text"]
            show_message_box("AI翻译完成！", "成功", 'INFO')
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

def ai_translate_text_tool(input_text, system_prompt=None):
    """AI翻译工具函数，供其他模块调用
    
    Args:
        input_text (str): 要翻译的文本
        system_prompt (str): 系统提示词，如果为None则使用默认提示词
    
    Returns:
        str: 翻译后的文本，如果翻译失败返回原文本
    """
    # 检查输入文本
    if not input_text or not input_text.strip():
        return ""

    local_translation = local_rule_translate(input_text)
    if local_translation:
        print(f"[AI翻译工具] 使用本地词典: '{input_text}' -> '{local_translation}'")
        return local_translation
    
    # 检查OpenAI SDK是否可用
    if not OPENAI_SDK_AVAILABLE:
        print("[AI翻译工具] OpenAI SDK未安装，请运行: pip install --upgrade 'openai>=1.0'")
        return input_text
    
    try:
        # 从环境变量或插件首选项获取API配置
        api = DoubaoTranslateAPI.from_preferences()
        print(f"[AI翻译工具] 从配置获取API")
        
        print(f"[AI翻译工具] 开始AI翻译: '{input_text}'")
        result = api.translate_text(input_text, system_prompt)
        print(f"[AI翻译工具] API返回结果: {result}")
        
        # 检查返回结果是否包含错误
        if isinstance(result, dict):
            if "error" in result:
                print(f"[AI翻译工具] AI翻译API错误: {result['error']}")
                return input_text  # 翻译失败时返回原文本
            elif "translated_text" in result:
                translated = result["translated_text"]
                print(f"[AI翻译工具] AI翻译成功: '{translated}'")
                return translated  # 返回翻译后的文本字符串
            else:
                print(f"[AI翻译工具] AI翻译API返回格式错误，完整结果: {result}")
                return input_text
        else:
            # 如果返回的不是字典，直接返回
            print(f"[AI翻译工具] API返回非字典类型: {type(result)}, 值: {result}")
            return str(result)
    except Exception as e:
        print(f"[AI翻译工具] AI翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return input_text  # 翻译失败时返回原文本


def start_ai_translate_job(job_key, input_text, system_prompt=None):
    """启动后台AI翻译任务。API对象在主线程创建，避免后台线程读取Blender配置。"""
    if not input_text or not input_text.strip():
        return False, "请输入要翻译的文本"

    local_translation = local_rule_translate(input_text)
    if local_translation:
        with _AI_TRANSLATION_JOBS_LOCK:
            _AI_TRANSLATION_JOBS[job_key] = {
                "state": "done",
                "input_text": input_text,
                "system_prompt": system_prompt,
                "translated_text": local_translation,
                "error": "",
                "progress": 1.0,
                "message": "使用本地词典",
                "started_at": time.time(),
            }
        print(f"[AI翻译工具] 使用本地词典: '{input_text}' -> '{local_translation}'")
        return True, ""

    if not OPENAI_SDK_AVAILABLE:
        return False, "OpenAI SDK未安装，请运行: pip install --upgrade 'openai>=1.0'"

    with _AI_TRANSLATION_JOBS_LOCK:
        current_job = _AI_TRANSLATION_JOBS.get(job_key)
        if current_job and current_job.get("state") == "running":
            return False, "AI翻译正在进行中"

    try:
        api = DoubaoTranslateAPI.from_preferences()
    except Exception as exc:
        return False, f"初始化AI翻译失败: {exc}"

    job = {
        "state": "running",
        "input_text": input_text,
        "system_prompt": system_prompt,
        "translated_text": "",
        "error": "",
        "progress": 0.08,
        "message": "正在连接AI翻译",
        "started_at": time.time(),
    }

    with _AI_TRANSLATION_JOBS_LOCK:
        _AI_TRANSLATION_JOBS[job_key] = job

    def worker():
        try:
            with _AI_TRANSLATION_JOBS_LOCK:
                if job_key in _AI_TRANSLATION_JOBS:
                    _AI_TRANSLATION_JOBS[job_key]["progress"] = 0.25
                    _AI_TRANSLATION_JOBS[job_key]["message"] = "正在请求AI翻译"

            result = api.translate_text(input_text, system_prompt)

            with _AI_TRANSLATION_JOBS_LOCK:
                stored_job = _AI_TRANSLATION_JOBS.get(job_key)
                if not stored_job:
                    return
                if isinstance(result, dict) and "translated_text" in result:
                    stored_job["translated_text"] = result["translated_text"]
                    stored_job["state"] = "done"
                    stored_job["progress"] = 1.0
                    stored_job["message"] = "AI翻译完成"
                else:
                    stored_job["error"] = result.get("error", "AI翻译失败") if isinstance(result, dict) else "AI翻译失败"
                    stored_job["state"] = "error"
                    stored_job["progress"] = 1.0
                    stored_job["message"] = "AI翻译失败"
        except Exception as exc:
            with _AI_TRANSLATION_JOBS_LOCK:
                stored_job = _AI_TRANSLATION_JOBS.get(job_key)
                if stored_job:
                    stored_job["error"] = str(exc)
                    stored_job["state"] = "error"
                    stored_job["progress"] = 1.0
                    stored_job["message"] = "AI翻译失败"

    thread = threading.Thread(target=worker, name=f"PopToolsAITranslate-{job_key}", daemon=True)
    thread.start()
    return True, ""


def get_ai_translate_job(job_key):
    with _AI_TRANSLATION_JOBS_LOCK:
        job = _AI_TRANSLATION_JOBS.get(job_key)
        return dict(job) if job else None


def advance_ai_translate_job_progress(job_key, step=0.025, limit=0.9):
    with _AI_TRANSLATION_JOBS_LOCK:
        job = _AI_TRANSLATION_JOBS.get(job_key)
        if not job or job.get("state") != "running":
            return dict(job) if job else None
        job["progress"] = min(limit, float(job.get("progress", 0.0)) + step)
        if job["progress"] > 0.55:
            job["message"] = "等待AI翻译结果"
        return dict(job)


def clear_ai_translate_job(job_key):
    with _AI_TRANSLATION_JOBS_LOCK:
        _AI_TRANSLATION_JOBS.pop(job_key, None)


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
    POPTOOLS_OT_ai_translate_text,
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
