# -*- coding: utf-8 -*-
"""
PopTools Crypto Utils
简单的密钥加密解密工具
"""

import base64
import hashlib

class SimpleCrypto:
    """简单的加密解密工具类"""
    
    @staticmethod
    def _generate_key(password: str) -> bytes:
        """根据密码生成密钥"""
        # 使用SHA-256生成固定长度的密钥
        return hashlib.sha256(password.encode('utf-8')).digest()
    
    @staticmethod
    def _xor_encrypt_decrypt(data: bytes, key: bytes) -> bytes:
        """使用XOR进行加密/解密"""
        result = bytearray()
        key_len = len(key)
        
        for i, byte in enumerate(data):
            result.append(byte ^ key[i % key_len])
        
        return bytes(result)
    
    @staticmethod
    def encrypt(text: str, password: str) -> str:
        """加密文本
        
        Args:
            text: 要加密的文本
            password: 密码
            
        Returns:
            加密后的Base64编码字符串
        """
        if not text or not password:
            return text
            
        try:
            # 生成密钥
            key = SimpleCrypto._generate_key(password)
            
            # 将文本转换为字节
            text_bytes = text.encode('utf-8')
            
            # 加密
            encrypted_bytes = SimpleCrypto._xor_encrypt_decrypt(text_bytes, key)
            
            # 转换为Base64编码
            encrypted_b64 = base64.b64encode(encrypted_bytes).decode('ascii')
            
            return encrypted_b64
            
        except Exception as e:
            print(f"[加密错误] {str(e)}")
            return text
    
    @staticmethod
    def decrypt(encrypted_text: str, password: str) -> str:
        """解密文本
        
        Args:
            encrypted_text: 加密的Base64编码字符串
            password: 密码
            
        Returns:
            解密后的原始文本
        """
        if not encrypted_text or not password:
            return encrypted_text
            
        try:
            # 生成密钥
            key = SimpleCrypto._generate_key(password)
            
            # 从Base64解码
            encrypted_bytes = base64.b64decode(encrypted_text.encode('ascii'))
            
            # 解密
            decrypted_bytes = SimpleCrypto._xor_encrypt_decrypt(encrypted_bytes, key)
            
            # 转换为文本
            decrypted_text = decrypted_bytes.decode('utf-8')
            
            return decrypted_text
            
        except Exception as e:
            print(f"[解密错误] {str(e)}")
            return encrypted_text
    
    @staticmethod
    def is_encrypted(text: str) -> bool:
        """检查文本是否为加密格式
        
        简单检查：如果是有效的Base64且长度合理，认为是加密的
        """
        if not text:
            return False
            
        try:
            # 检查是否为有效的Base64
            decoded = base64.b64decode(text.encode('ascii'))
            # 重新编码检查是否一致
            reencoded = base64.b64encode(decoded).decode('ascii')
            return reencoded == text and len(text) > 20  # 加密后的文本通常较长
        except:
            return False


ENCRYPTED_KEYS = {
    "tencent_secret_id": "HhITV1//xmQXrmPUI647Xcm8ThbQUrXXAbe2dszUDjc+FmtH",
    "tencent_secret_key": "BysgZEPe5XZcrn7xE+gVRKv/QmSdXrDqT6StJ8LiLDY="
}

def get_decrypted_api_key(key_name: str, user_password: str) -> str:
    """获取解密后的API密钥
    
    Args:
        key_name: 密钥名称（如'tencent_secret_id'）
        user_password: 用户输入的密码
        
    Returns:
        解密后的API密钥，如果解密失败返回空字符串
    """
    print(f"[调试] get_decrypted_api_key: key_name='{key_name}', password='{user_password}'")
    
    if key_name not in ENCRYPTED_KEYS:
        print(f"[调试] 密钥名称 '{key_name}' 不在ENCRYPTED_KEYS中")
        return ""
        
    encrypted_key = ENCRYPTED_KEYS[key_name]
    print(f"[调试] 获取到加密密钥: '{encrypted_key}'")
    
    if not encrypted_key or encrypted_key == "your_encrypted_secret_id_here" or encrypted_key == "your_encrypted_secret_key_here":
        print(f"[调试] 加密密钥无效或为默认值")
        return ""
    
    decrypted = SimpleCrypto.decrypt(encrypted_key, user_password)
    print(f"[调试] 解密结果: '{decrypted}'")
    return decrypted

def encrypt_api_keys(secret_id: str, secret_key: str, password: str) -> dict:
    """加密API密钥（用于生成加密后的密钥）
    
    Args:
        secret_id: 腾讯云Secret ID
        secret_key: 腾讯云Secret Key
        password: 加密密码
        
    Returns:
        包含加密后密钥的字典
    """
    return {
        "tencent_secret_id": SimpleCrypto.encrypt(secret_id, password),
        "tencent_secret_key": SimpleCrypto.encrypt(secret_key, password)
    }

if __name__ == "__main__":
    # 测试代码
    test_text = "这是一个测试文本"
    test_password = "poptools2024"
    
    print(f"原始文本: {test_text}")
    
    encrypted = SimpleCrypto.encrypt(test_text, test_password)
    print(f"加密后: {encrypted}")
    
    decrypted = SimpleCrypto.decrypt(encrypted, test_password)
    print(f"解密后: {decrypted}")
    
    print(f"加密检查: {SimpleCrypto.is_encrypted(encrypted)}")
    print(f"原文检查: {SimpleCrypto.is_encrypted(test_text)}")