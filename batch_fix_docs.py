#!/usr/bin/env python3
"""
批量修复文档字符串语法错误
"""

import os
import re
import sys
from pathlib import Path

def fix_all_problematic_files(project_root):
    """修复所有有问题的文件"""
    fixed_files = []
    
    # 遍历所有Python文件
    for root, dirs, files in os.walk(project_root):
        # 跳过隐藏目录和虚拟环境
        if any(part.startswith('.') for part in root.split('/')):
            continue
        if 'venv' in root or '__pycache__' in root or '.git' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_file_docstring(filepath):
                    fixed_files.append(os.path.relpath(filepath, project_root))
    
    return fixed_files

def fix_file_docstring(filepath):
    """修复单个文件的文档字符串"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 修复1: 确保模块文档以三引号开始
        if not content.startswith('\"\"\"') and not content.startswith('\'\'\''):
            # 检查是否有不完整的文档字符串
            lines = content.split('\n')
            if len(lines) > 1 and ('模块功能描述' in lines[0] or 'TODO' in lines[0]):
                # 这是一个损坏的文档字符串，需要修复
                content = '\"\"\"\n' + content
        
        # 修复2: 移除嵌套的文档字符串
        # 查找模块文档部分
        module_doc_match = re.search(r'^(\"\"\"|\'\'\')(.*?)(\"\"\"|\'\'\')', content, re.DOTALL)
        if module_doc_match:
            module_doc = module_doc_match.group(0)
            
            # 检查模块文档中是否有嵌套的三引号
            if '\"\"\"' in module_doc[3:-3] or '\'\'\'' in module_doc[3:-3]:
                # 移除嵌套的三引号行
                lines = module_doc.split('\n')
                cleaned_lines = []
                in_nested = False
                
                for line in lines:
                    stripped = line.strip()
                    if stripped == '\"\"\"' or stripped == '\'\'\'':
                        if not in_nested:
                            in_nested = True
                        else:
                            in_nested = False
                        continue
                    
                    if not in_nested:
                        cleaned_lines.append(line)
                
                cleaned_doc = '\n'.join(cleaned_lines)
                content = content.replace(module_doc, cleaned_doc)
        
        # 修复3: 确保类文档字符串正确
        # 查找类定义后的文档字符串
        class_pattern = r'class\s+\w+.*?:\s*(\"\"\"|\'\'\')'
        matches = list(re.finditer(class_pattern, content, re.DOTALL))
        
        for match in matches:
            # 检查类文档字符串是否完整
            quote_type = match.group(1)
            start_pos = match.end() - len(quote_type)
            
            # 查找结束的三引号
            remaining = content[start_pos:]
            end_pattern = quote_type + r'(?!\")'  # 避免匹配四个引号
            end_match = re.search(end_pattern, remaining[3:])  # 跳过开始的三个引号
            
            if not end_match:
                # 文档字符串不完整，添加结束引号
                # 在类定义后添加简单的文档字符串
                class_def_end = match.end()
                simple_doc = f'\n    {quote_type}类功能描述{quote_type}\n'
                content = content[:class_def_end] + simple_doc + content[class_def_end:]
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 修复 {filepath} 失败: {e}")
        return False

def create_simple_docstring(filepath):
    """为文件创建简单的文档字符串（如果完全损坏）"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 获取文件名
        filename = os.path.basename(filepath)
        module_name = os.path.splitext(filename)[0]
        
        # 创建简单的文档字符串
        simple_doc = f'''"""
{module_name} - {filepath}

模块功能描述。

作者: XiangMeng
版本: 0.5.1-beta
"""

'''
        
        # 如果文件没有文档字符串，添加一个
        if not content.startswith('\"\"\"') and not content.startswith('\'\'\''):
            new_content = simple_doc + content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 创建简单文档失败 {filepath}: {e}")
        return False

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python batch_fix_docs.py <项目路径>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"❌ 项目路径不存在: {project_root}")
        sys.exit(1)
    
    print("🔧 批量修复文档字符串...")
    
    # 1. 先尝试修复
    fixed_files = fix_all_problematic_files(project_root)
    
    if fixed_files:
        print(f"✅ 修复了 {len(fixed_files)} 个文件:")
        for file in fixed_files[:20]:
            print(f"  • {file}")
        if len(fixed_files) > 20:
            print(f"  ... 还有 {len(fixed_files) - 20} 个")
    else:
        print("✅ 未发现需要修复的文件")
    
    # 2. 为关键文件创建简单文档
    print("\n📝 为关键文件创建简单文档...")
    key_files = [
        'zoo_framework/fifo/base_fifo.py',
        'zoo_framework/fifo/__init__.py',
        'zoo_framework/event/__init__.py',
        'zoo_framework/event/event_channel.py',
        'zoo_framework/core/aop/__init__.py',
        'zoo_framework/core/aop/event.py',
        'zoo_framework/conf/log_config.py'
    ]
    
    created_count = 0
    for rel_path in key_files:
        filepath = os.path.join(project_root, rel_path)
        if os.path.exists(filepath):
            if create_simple_docstring(filepath):
                print(f"✅ 已创建: {rel_path}")
                created_count += 1
    
    print(f"✅ 为 {created_count} 个关键文件创建了简单文档")
    
    # 3. 验证修复
    print("\n🔍 验证修复结果...")
    test_files = [
        'zoo_framework/__init__.py',
        'zoo_framework/utils/__init__.py',
        'zoo_framework/fifo/__init__.py'
    ]
    
    for rel_path in test_files:
        filepath = os.path.join(project_root, rel_path)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    compile(f.read(), filepath, 'exec')
                print(f"✅ {rel_path}: 语法正确")
            except SyntaxError as e:
                print(f"❌ {rel_path}: 语法错误 - {e}")
    
    print(f"\n🎉 批量修复完成！")
    print(f"📁 总共处理了 {len(fixed_files) + created_count} 个文件")

if __name__ == '__main__':
    main()