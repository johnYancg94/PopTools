import os
import zipfile
import hashlib
import json
from pathlib import Path

def create_zip_package():
    source_dir = Path('.')
    packages_dir = Path('./packages')
    zip_path = packages_dir / 'PopTools.zip'
    
    exclude_patterns = {
        '__pycache__', '.mypy_cache', '.gitignore', 'packages', 
        'generate_json.py', 'create_package.py', '.git','docs',
    }
    
    # 确保packages目录存在
    packages_dir.mkdir(exist_ok=True)
    print(f"创建packages目录: {packages_dir}")
    
    if zip_path.exists():
        zip_path.unlink()
        print(f"删除现有zip文件: {zip_path}")
    
    print(f"开始创建zip包: {zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                file_path = Path(root) / file
                should_exclude = any(pattern in str(file_path) or file == pattern for pattern in exclude_patterns)
                
                if not should_exclude:
                    rel_path = file_path.relative_to(source_dir)
                    zipf.write(file_path, rel_path)
                    print(f"添加文件: {rel_path}")
    
    file_size = zip_path.stat().st_size
    print(f"zip文件大小: {file_size} 字节")
    
    sha256_hash = hashlib.sha256()
    with open(zip_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    hash_value = sha256_hash.hexdigest()
    print(f"zip文件哈希: {hash_value}")
    
    return file_size, hash_value

def read_plugin_metadata():
    """从插件文件中读取元数据"""
    metadata = {
        'id': 'poptools',
        'name': 'PopTools - 蜂鸟工具箱',
        'tagline': '专业的Blender游戏资产制作和导出工具集，支持多引擎导出和纹理管理',
        'version': '1.0.0',
        'maintainer': 'johnYancg94',
        'license': ['SPDX:GPL-3.0-or-later'],
        'blender_version_min': '4.2.0',
        'website': 'https://github.com/johnYancg94/PopTools',
        'tags': ['3D View', 'Object', 'UV', 'Mesh', 'Import-Export', 'Modeling', 'Game Development', 'Texture', 'Animation']
    }
    
    import re
    
    # 首先从__init__.py读取版本信息（更准确）
    try:
        with open('__init__.py', 'r', encoding='utf-8') as f:
            content = f.read()
            print("正在读取__init__.py...")
            
            # 查找版本号
            version_match = re.search(r'"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)', content)
            if version_match:
                major, minor, patch = version_match.groups()
                metadata['version'] = f"{major}.{minor}.{patch}"
                print(f"从__init__.py读取到版本: {metadata['version']}")
            
            # 查找插件名称
            name_match = re.search(r'"name":\s*"([^"]+)"', content)
            if name_match:
                metadata['name'] = name_match.group(1)
                print(f"从__init__.py读取到名称: {metadata['name']}")
                
    except Exception as e:
        print(f"警告：无法读取__init__.py中的元数据: {e}")
    
    # 然后从blender_manifest.toml读取其他信息
    try:
        with open('blender_manifest.toml', 'r', encoding='utf-8') as f:
            content = f.read()
            print("正在读取blender_manifest.toml...")
            
            # 查找ID
            id_match = re.search(r'id\s*=\s*"([^"]+)"', content)
            if id_match:
                metadata['id'] = id_match.group(1)
                print(f"从manifest读取到ID: {metadata['id']}")
            
            # 查找名称
            name_match = re.search(r'name\s*=\s*"([^"]+)"', content)
            if name_match:
                metadata['name'] = name_match.group(1)
                print(f"从manifest读取到名称: {metadata['name']}")
            
            # 查找标语
            tagline_match = re.search(r'tagline\s*=\s*"([^"]+)"', content)
            if tagline_match:
                metadata['tagline'] = tagline_match.group(1)
                print(f"从manifest读取到标语: {metadata['tagline']}")
            
            # 查找维护者
            maintainer_match = re.search(r'maintainer\s*=\s*"([^"]+)"', content)
            if maintainer_match:
                metadata['maintainer'] = maintainer_match.group(1)
                print(f"从manifest读取到维护者: {metadata['maintainer']}")
            
            # 查找网站
            website_match = re.search(r'website\s*=\s*"([^"]+)"', content)
            if website_match:
                metadata['website'] = website_match.group(1)
                print(f"从manifest读取到网站: {metadata['website']}")
            
            # 查找最低Blender版本
            blender_min_match = re.search(r'blender_version_min\s*=\s*"([^"]+)"', content)
            if blender_min_match:
                metadata['blender_version_min'] = blender_min_match.group(1)
                print(f"从manifest读取到最低版本: {metadata['blender_version_min']}")
            
            # 查找标签 - 支持多行格式
            tags_match = re.search(r'tags\s*=\s*\[([^\]]+)\]', content, re.DOTALL)
            if tags_match:
                tags_str = tags_match.group(1)
                # 解析标签列表，处理换行和引号
                tags = []
                for tag in tags_str.split(','):
                    tag = tag.strip().strip('"').strip("'").strip()
                    if tag:
                        tags.append(tag)
                metadata['tags'] = tags
                print(f"从manifest读取到标签: {metadata['tags']}")
                
    except Exception as e:
        print(f"警告：无法读取blender_manifest.toml中的元数据: {e}")
    
    return metadata

def create_index_json(file_size, hash_value):
    metadata = read_plugin_metadata()
    
    print("使用插件元数据:")
    print(f"  ID: {metadata['id']}")
    print(f"  名称: {metadata['name']} ")
    print(f"  版本: {metadata['version']}")
    print(f"  维护者: {metadata['maintainer']}")
    
    index_data = {
        "version": "v1",
        "blocklist": [],
        "data": [
            {
                "schema_version": "1.0.0",
                "id": metadata['id'],
                "name": metadata['name'],
                "tagline": metadata['tagline'],
                "version": metadata['version'],
                "type": "add-on",
                "maintainer": metadata['maintainer'],
                "license": metadata['license'],
                "blender_version_min": metadata['blender_version_min'],
                "website": metadata['website'],
                "tags": metadata['tags'],
                "archive_url": "./PopTools.zip",
                "archive_size": file_size,
                "archive_hash": f"sha256:{hash_value}"
            }
        ]
    }
    
    packages_dir = Path('./packages')
    packages_dir.mkdir(exist_ok=True)
    
    json_path = packages_dir / 'index.json'
    print(f"创建JSON文件: {json_path}")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    
    docs_dir = Path('./docs')
    docs_dir.mkdir(exist_ok=True)
    
    import shutil
    
    # 复制JSON文件到docs目录
    docs_json_path = docs_dir / 'index.json'
    if docs_json_path.exists():
        docs_json_path.unlink()
        print(f"删除原有JSON文件: {docs_json_path}")
    shutil.copy2(json_path, docs_json_path)
    print(f"复制JSON文件到: {docs_json_path}")
    
    # 复制ZIP文件到docs目录
    zip_source = packages_dir / 'PopTools.zip'
    zip_dest = docs_dir / 'PopTools.zip'
    if zip_dest.exists():
        zip_dest.unlink()
        print(f"删除原有ZIP文件: {zip_dest}")
    shutil.copy2(zip_source, zip_dest)
    print(f"复制ZIP文件到: {zip_dest}")

if __name__ == '__main__':
    file_size, hash_value = create_zip_package()
    create_index_json(file_size, hash_value)
    print("打包完成!")