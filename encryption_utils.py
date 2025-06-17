# -*- coding: utf-8 -*-
"""
加密工具模块
用于API密钥的加密存储和解密
"""

import base64
import hashlib
import os

class APIKeyEncryption:
    """API密钥加密工具（使用简单XOR加密）"""
    
    def __init__(self, password="fengniao666"):
        self.password = password
        self.key = self._generate_key(password)
    
    def _generate_key(self, password):
        """从密码生成加密密钥"""
        # 使用SHA256生成固定长度的密钥
        password_with_salt = f"poptools_{password}_2024"
        return hashlib.sha256(password_with_salt.encode('utf-8')).digest()
    
    def _xor_encrypt_decrypt(self, data, key):
        """XOR加密/解密"""
        result = bytearray()
        key_len = len(key)
        for i, byte in enumerate(data):
            result.append(byte ^ key[i % key_len])
        return bytes(result)
    
    def encrypt(self, text):
        """加密文本"""
        if not text:
            return ""
        try:
            text_bytes = text.encode('utf-8')
            encrypted_bytes = self._xor_encrypt_decrypt(text_bytes, self.key)
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            print(f"加密失败: {e}")
            return ""
    
    def decrypt(self, encrypted_text):
        """解密文本"""
        if not encrypted_text:
            return ""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
            decrypted_bytes = self._xor_encrypt_decrypt(encrypted_bytes, self.key)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            return None
    


# 预加密的API密钥（使用密码"fengniao666"加密）
class EncryptedAPIKeys:
    """存储预加密的API密钥"""
    
    def __init__(self):
        # 这里存储的是已经用"fengniao666"密码加密后的密钥
        # 实际使用时需要替换为真实的加密密钥
        self.encrypted_keys = {
            "tencent_secret_id": "5vO2a99KvqyDpiXXz-_gHpwfbeCnP_SDovdggbgtoenG9857",
            "tencent_secret_key": "_8qFWMNrnb7Ipjjy_6nOB_5cYZLqM_G-7OR70LYbg-g=",
            "doubao_api_key": "lY3NS5kVwfbWujGOovGNWp9Lde7tboH0t4cTguF09eXGgMca"
        }
    
    def get_decrypted_key(self, key_name, password="fengniao666"):
        """获取解密后的API密钥"""
        if key_name not in self.encrypted_keys:
            return None
        
        encrypted_value = self.encrypted_keys[key_name]
        
        try:
            encryption = APIKeyEncryption(password)
            return encryption.decrypt(encrypted_value)
        except Exception as e:
            print(f"解密 {key_name} 失败: {e}")
            return None
    
    def verify_master_password(self, password):
        """验证主密码是否正确"""
        # 通过尝试解密一个已知的密钥来验证密码
        test_key = "tencent_secret_id"
        if test_key in self.encrypted_keys:
            encrypted_value = self.encrypted_keys[test_key]
            try:
                encryption = APIKeyEncryption(password)
                decrypted = encryption.decrypt(encrypted_value)
                return decrypted is not None and len(decrypted) > 0
            except:
                return False
        return False

# 全局实例
encrypted_api_keys = EncryptedAPIKeys()

# 全局函数，方便其他模块调用
def get_decrypted_api_key(key_name, password="fengniao666"):
    """获取解密后的API密钥"""
    return encrypted_api_keys.get_decrypted_key(key_name, password)

def verify_master_password(password):
    """验证主密码"""
    return encrypted_api_keys.verify_master_password(password)