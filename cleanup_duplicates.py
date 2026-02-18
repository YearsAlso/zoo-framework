#!/usr/bin/env python3
"""
清理重复的文档字符串内容
"""

import os
import re

def cleanup_file(filepath):
    """清理文件中的重复内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # 分割为行
        lines = content.split('\n')
        new_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查是否有重复的模块标题行
            # 模式: 模块名 - 文件路径
            module_pattern = r'^(\w+)\s*-\s*[\w/\.]+\.py$'
            match = re.match(module_pattern, line.strip())
            
            if match and i > 0:
                # 检查前几行是否有相同的模式
                for j in range(max(0, i-5), i):
                    prev_match = re.match(module_pattern, lines[j].strip())
                    if prev_match and prev_match.group(1) == match.group(1):
                        # 发现重复，跳过当前行
                        print(f"  跳过重复行: {line}")
                        i += 1
                        continue
            
            new_lines.append(line)
            i += 1
        
        new_content = '\n'.join(new_lines)
        
        # 移除多余的空行（连续3个以上空行）
        new_content = re.sub(r'\n\s*\n\s*\n\s*\n+', '\n\n\n', new_content)
        
        if new_content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 清理 {filepath} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🧹 清理重复内容...")
    
    # 收集所有Python文件
    python_files = []
    for root, dirs, files in os.walk('zoo_framework'):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"📁 发现 {len(python_files)} 个Python文件")
    
    cleaned_count = 0
    for filepath in python_files:
        print(f"🧹 清理: {os.path.basename(filepath)}", end='')
        if cleanup_file(filepath):
            cleaned_count += 1
            print(" ✅")
        else:
            print(" ⚠️")
    
    print(f"\n🎉 清理完成！")
    print(f"🧹 清理了 {cleaned_count} 个文件")
    
    # 运行Ruff检查
    print("\n🔍 运行Ruff检查...")
    os.system('python3 -m ruff check zoo_framework --statistics 2>&1 | head -20')

if __name__ == '__main__':
    main()