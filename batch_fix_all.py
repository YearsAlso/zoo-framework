#!/usr/bin/env python3
"""
批量修复所有语法错误
"""

import os
import re
import sys

def fix_file(filepath):
    """修复单个文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # 修复模式1: 嵌套文档字符串
        # """模块文档\n    """类文档\n    """\n更多内容"""
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是模块文档开始
            if i == 0 and line.strip().startswith('"""'):
                # 找到模块文档结束
                j = i
                while j < len(lines):
                    if lines[j].strip().endswith('"""') and j > i:
                        break
                    j += 1
                
                if j < len(lines):
                    # 清理模块文档
                    module_doc = []
                    for k in range(i, j+1):
                        doc_line = lines[k]
                        # 跳过嵌套的三引号行
                        if doc_line.strip() == '"""':
                            continue
                        # 跳过类文档标题
                        if '类功能描述' in doc_line:
                            continue
                        # 跳过TODO行（但保留缩进）
                        if 'TODO:' in doc_line:
                            # 移除TODO但保留行
                            cleaned = re.sub(r'TODO:.*', '', doc_line)
                            if cleaned.strip():
                                module_doc.append(cleaned)
                            continue
                        module_doc.append(doc_line)
                    
                    new_lines.extend(module_doc)
                    i = j + 1
                    continue
            
            new_lines.append(line)
            i += 1
        
        content = '\n'.join(new_lines)
        
        # 修复模式2: 确保文档字符串正确
        # 添加缺失的模块文档
        if not content.startswith('"""'):
            filename = os.path.basename(filepath)
            module_name = os.path.splitext(filename)[0]
            simple_doc = f'''"""
{module_name} - {filepath}

模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""

'''
            content = simple_doc + content
        
        # 修复模式3: 确保类有文档字符串
        # 查找所有类定义
        class_matches = list(re.finditer(r'^class\s+(\w+).*?:', content, re.MULTILINE))
        
        for match in reversed(class_matches):  # 从后往前修复，避免位置偏移
            class_name = match.group(1)
            class_start = match.start()
            
            # 获取类定义后的内容
            after_class = content[class_start:]
            lines_after = after_class.split('\n', 3)
            
            if len(lines_after) > 1:
                # 检查第二行是否是文档字符串
                second_line = lines_after[1].strip() if len(lines_after) > 1 else ''
                
                if not (second_line.startswith('"""') or second_line.startswith("'''")):
                    # 类没有文档字符串，添加一个
                    indent = len(lines_after[0]) - len(lines_after[0].lstrip())
                    simple_class_doc = f'\n{" " * (indent + 4)}"""{class_name} - 类功能描述"""'
                    
                    # 插入文档字符串
                    insert_pos = class_start + len(lines_after[0])
                    content = content[:insert_pos] + simple_class_doc + content[insert_pos:]
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 修复 {filepath} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 批量修复语法错误...")
    
    # 需要修复的目录
    directories = [
        'zoo_framework/constant',
        'zoo_framework/workers',
        'zoo_framework/utils',
        'zoo_framework/fifo',
        'zoo_framework/reactor',
        'zoo_framework/event',
        'zoo_framework/core'
    ]
    
    fixed_count = 0
    total_files = 0
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
        
        print(f"\n📁 处理目录: {directory}")
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    total_files += 1
                    
                    print(f"  🔧 {file}", end='')
                    
                    if fix_file(filepath):
                        fixed_count += 1
                        print(" ✅")
                    else:
                        print(" ⚠️")
    
    print(f"\n🎉 批量修复完成！")
    print(f"📁 总共处理了 {total_files} 个文件")
    print(f"🔧 修复了 {fixed_count} 个文件")
    
    # 验证修复结果
    print("\n🔍 验证修复结果...")
    os.system('python3 -m ruff check zoo_framework --statistics')

if __name__ == '__main__':
    main()