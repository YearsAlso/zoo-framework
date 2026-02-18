#!/usr/bin/env python3
"""
批量修复Ruff检查出的语法错误
主要修复文档字符串格式问题
"""

import os
import re
import sys
from pathlib import Path

def fix_docstring_syntax(filepath):
    """修复文档字符串语法错误"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 修复1: 移除模块文档中的嵌套类文档
        # 模式: """模块文档\n    """类文档\n    """\n更多内容"""
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是模块文档开始
            if i == 0 and (line.strip().startswith('"""') or line.strip().startswith("'''")):
                quote_type = '"""' if '"""' in line else "'''"
                
                # 找到模块文档结束
                j = i
                module_doc_end = -1
                while j < len(lines):
                    if lines[j].strip().endswith(quote_type) and j > i:
                        module_doc_end = j
                        break
                    j += 1
                
                if module_doc_end != -1:
                    # 提取模块文档内容
                    module_doc = lines[i:module_doc_end+1]
                    
                    # 清理嵌套的文档字符串
                    cleaned_doc = []
                    in_nested = False
                    
                    for doc_line in module_doc:
                        stripped = doc_line.strip()
                        
                        # 跳过嵌套的三引号行
                        if stripped == '"""' or stripped == "'''":
                            if not in_nested:
                                in_nested = True
                            else:
                                in_nested = False
                            continue
                        
                        if not in_nested:
                            # 清理类文档标题行
                            if '类功能描述' in doc_line or 'TODO:' in doc_line:
                                # 跳过这些行
                                continue
                            cleaned_doc.append(doc_line)
                    
                    new_lines.extend(cleaned_doc)
                    i = module_doc_end + 1
                    continue
            
            new_lines.append(line)
            i += 1
        
        content = '\n'.join(new_lines)
        
        # 修复2: 确保文档字符串正确闭合
        triple_quotes = content.count('"""')
        if triple_quotes % 2 != 0:
            # 添加缺失的结束引号
            content += '\n"""'
        
        # 修复3: 移除多余的中文字符问题
        content = re.sub(r'模块功能描述：\s*$', '模块功能描述：', content, flags=re.MULTILINE)
        
        # 修复4: 确保类文档字符串格式正确
        # 查找类定义
        class_pattern = r'^class\s+\w+.*?:'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            class_start = match.start()
            # 检查类后是否有文档字符串
            after_class = content[class_start:]
            lines_after = after_class.split('\n', 3)
            
            if len(lines_after) > 1:
                # 检查第二行是否是文档字符串开始
                second_line = lines_after[1].strip() if len(lines_after) > 1 else ''
                third_line = lines_after[2].strip() if len(lines_after) > 2 else ''
                
                if not (second_line.startswith('"""') or second_line.startswith("'''")):
                    # 类没有文档字符串，添加一个简单的
                    indent = len(lines_after[0]) - len(lines_after[0].lstrip())
                    simple_doc = '\n' + ' ' * (indent + 4) + '"""类功能描述"""'
                    
                    # 插入文档字符串
                    insert_pos = class_start + len(lines_after[0])
                    content = content[:insert_pos] + simple_doc + content[insert_pos:]
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 修复 {filepath} 失败: {e}")
        return False

def get_files_with_syntax_errors():
    """获取有语法错误的文件列表"""
    import subprocess
    
    try:
        result = subprocess.run(
            ['python3', '-m', 'ruff', 'check', 'zoo_framework', '--output-format=json'],
            capture_output=True,
            text=True,
            cwd='/tmp/zoo-framework'
        )
        
        if result.returncode != 0:
            # 解析JSON输出
            import json
            errors = json.loads(result.stdout)
            
            syntax_error_files = set()
            for error in errors:
                if error.get('code', '').startswith('invalid-syntax'):
                    filepath = error.get('location', {}).get('file', '')
                    if filepath:
                        syntax_error_files.add(filepath)
            
            return list(syntax_error_files)
    
    except Exception as e:
        print(f"❌ 获取语法错误文件失败: {e}")
    
    return []

def main():
    """主函数"""
    print("🔧 开始修复语法错误...")
    
    # 获取有语法错误的文件
    error_files = get_files_with_syntax_errors()
    
    if not error_files:
        print("✅ 未发现语法错误文件")
        return
    
    print(f"📁 发现 {len(error_files)} 个有语法错误的文件")
    
    fixed_count = 0
    for rel_path in error_files[:20]:  # 先处理前20个文件
        filepath = os.path.join('/tmp/zoo-framework', rel_path)
        if os.path.exists(filepath):
            print(f"🔧 修复: {rel_path}")
            if fix_docstring_syntax(filepath):
                fixed_count += 1
                print(f"  ✅ 已修复")
            else:
                print(f"  ⚠️  无需修复")
    
    print(f"\n🎉 修复完成！")
    print(f"📁 总共修复了 {fixed_count} 个文件")
    
    # 验证修复结果
    print("\n🔍 验证修复结果...")
    os.chdir('/tmp/zoo-framework')
    os.system('python3 -m ruff check zoo_framework --statistics')

if __name__ == '__main__':
    main()