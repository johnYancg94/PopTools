import os
import zipfile
import hashlib
import json
from pathlib import Path

def create_zip_package():
    source_dir = Path('.')
    zip_path = Path('./packages/PopTools.zip')
    
    exclude_patterns = {
        '__pycache__', '.mypy_cache', '.gitignore', 'packages', 
        'generate_json.py', 'create_package.py', '.git','docs',
    }
    
    zip_path.parent.mkdir(exist_ok=True)
    
    if zip_path.exists():
        zip_path.unlink()
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                file_path = Path(root) / file
                should_exclude = any(pattern in str(file_path) or file == pattern for pattern in exclude_patterns)
                
                if not should_exclude:
                    rel_path = file_path.relative_to(source_dir)
                    zipf.write(file_path, rel_path)
    
    file_size = zip_path.stat().st_size
    
    sha256_hash = hashlib.sha256()
    with open(zip_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    return file_size, sha256_hash.hexdigest()

def create_index_json(file_size, hash_value):
    index_data = {
        "version": "v1",
        "blocklist": [],
        "data": [{
            "schema_version": "1.0.0",
            "id": "poptools",
            "name": "PopTools - 蜂鸟工具箱",
            "tagline": "专业的Blender游戏资产制作和导出工具集，支持多引擎导出和纹理管理",
            "version": "3.3.5",
            "type": "add-on",
            "maintainer": "johnYancg94",
            "license": ["SPDX:GPL-3.0-or-later"],
            "blender_version_min": "4.2.0",
            "website": "https://github.com/johnYancg94/PopTools",
            "tags": ["3D View", "Object", "UV", "Mesh", "Import-Export", "Modeling", "Game Development", "Texture", "Animation"],
            "archive_url": "./PopTools.zip",
            "archive_size": file_size,
            "archive_hash": f"sha256:{hash_value}"
        }]
    }
    
    docs_dir = Path('./docs')
    docs_dir.mkdir(exist_ok=True)
    
    with open(docs_dir / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    import shutil
    shutil.copy2('./packages/PopTools.zip', docs_dir / 'PopTools.zip')

if __name__ == '__main__':
    file_size, hash_value = create_zip_package()
    create_index_json(file_size, hash_value)
    print("打包完成!")