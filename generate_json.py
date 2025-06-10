#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blender扩展仓库JSON生成器
自动为packages目录下的zip文件生成符合Blender官方规范的index.json文件
"""

import os
import json
import hashlib
import zipfile
from pathlib import Path
import re

def calculate_file_hash(file_path):
    """计算文件的SHA256哈希值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def get_file_size(file_path):
    """获取文件大小（字节）"""
    return os.path.getsize(file_path)

def read_manifest_info(manifest_path):
    """读取blender_manifest.toml文件信息（简单TOML解析）"""
    try:
        manifest = {}
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 简单的TOML解析（仅支持基本键值对和数组）
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 处理字符串值
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 移除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # 处理数组
                if value.startswith('[') and value.endswith(']'):
                    # 简单数组解析
                    array_content = value[1:-1]
                    if array_content.strip():
                        items = []
                        # 分割数组项
                        for item in array_content.split(','):
                            item = item.strip()
                            if item.startswith('"') and item.endswith('"'):
                                item = item[1:-1]
                            elif item.startswith("'") and item.endswith("'"):
                                item = item[1:-1]
                            if item:
                                items.append(item)
                        value = items
                    else:
                        value = []
                
                manifest[key] = value
        
        return manifest
    except Exception as e:
        print(f"读取manifest文件失败: {e}")
        return None

def generate_extension_json(packages_dir, output_dir, manifest_path):
    """生成扩展仓库JSON文件"""
    
    # 读取manifest信息
    manifest = read_manifest_info(manifest_path)
    if not manifest:
        print("无法读取manifest文件，使用默认值")
        manifest = {
            "id": "poptools",
            "version": "3.3.2",
            "name": "PopTools - 蜂鸟工具箱",
            "tagline": "专业的Blender游戏资产制作和导出工具集，支持多引擎导出和纹理管理",
            "maintainer": "johnYancg94",
            "type": "add-on",
            "website": "https://github.com/johnYancg94/PopTools",
            "tags": ["3D View", "Object", "UV", "Mesh", "Import-Export", "Modeling", "Game Development", "Texture", "Animation"],
            "blender_version_min": "4.2.0",
            "license": ["SPDX:GPL-3.0-or-later"]
        }
    
    # 扫描packages目录下的zip文件
    packages_path = Path(packages_dir)
    if not packages_path.exists():
        print(f"packages目录不存在: {packages_dir}")
        return False
    
    zip_files = list(packages_path.glob("*.zip"))
    if not zip_files:
        print(f"在{packages_dir}目录下未找到zip文件")
        return False
    
    # 生成JSON数据
    json_data = {
        "version": "v1",
        "blocklist": [],
        "data": []
    }
    
    for zip_file in zip_files:
        print(f"处理文件: {zip_file.name}")
        
        # 计算文件信息
        file_size = get_file_size(zip_file)
        file_hash = calculate_file_hash(zip_file)
        
        # 构建扩展信息
        extension_data = {
            "schema_version": "1.0.0",
            "id": manifest.get("id", "poptools"),
            "name": manifest.get("name", "PopTools - 蜂鸟工具箱"),
            "tagline": manifest.get("tagline", "专业的Blender游戏资产制作和导出工具集，支持多引擎导出和纹理管理"),
            "version": manifest.get("version", "3.3.2"),
            "type": manifest.get("type", "add-on"),
            "maintainer": manifest.get("maintainer", "johnYancg94"),
            "license": manifest.get("license", ["SPDX:GPL-3.0-or-later"]),
            "blender_version_min": manifest.get("blender_version_min", "4.2.0"),
            "website": manifest.get("website", "https://github.com/johnYancg94/PopTools"),
            "tags": manifest.get("tags", ["3D View", "Object", "UV", "Mesh", "Import-Export", "Modeling", "Game Development", "Texture", "Animation"]),
            "archive_url": f"./{zip_file.name}",
            "archive_size": file_size,
            "archive_hash": f"sha256:{file_hash}"
        }
        
        json_data["data"].append(extension_data)
        
        print(f"  文件大小: {file_size} 字节")
        print(f"  SHA256: {file_hash}")
    
    # 保存JSON文件
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    json_file_path = output_path / "index.json"
    
    try:
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ JSON文件生成成功: {json_file_path}")
        print(f"📦 处理了 {len(zip_files)} 个zip文件")
        return True
        
    except Exception as e:
        print(f"❌ 保存JSON文件失败: {e}")
        return False

def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    
    # 设置路径
    packages_dir = script_dir / "packages"
    output_dir = script_dir / "docs"
    manifest_path = script_dir / "blender_manifest.toml"
    
    print("🚀 开始生成Blender扩展仓库JSON文件...")
    print(f"📁 packages目录: {packages_dir}")
    print(f"📁 输出目录: {output_dir}")
    print(f"📄 manifest文件: {manifest_path}")
    print("-" * 50)
    
    # 生成JSON
    success = generate_extension_json(packages_dir, output_dir, manifest_path)
    
    if success:
        print("\n🎉 所有操作完成！")
        print("💡 提示: 生成的index.json文件已保存到docs目录")
        print("💡 提示: 请确保zip文件也复制到docs目录以便GitHub Pages访问")
    else:
        print("\n❌ 操作失败，请检查错误信息")

if __name__ == "__main__":
    main()