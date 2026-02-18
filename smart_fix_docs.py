#!/usr/bin/env python3
"""
智能修复文档字符串问题
"""

import os
import re
import sys

def is_valid_python(content):
    """检查Python代码是否有效"""
    try:
        compile(content, '<string>', 'exec')
        return True
    except SyntaxError:
        return False

def fix_documentation(filepath):
    """修复文档字符串"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # 如果已经是有效的Python，跳过
        if is_valid_python(content):
            return False
        
        # 修复模式1: 嵌套的三引号
        # 查找所有三引号的位置
        triple_quote_positions = []
        for match in re.finditer(r'\"\"\"', content):
            triple_quote_positions.append(match.start())
        
        # 如果三引号数量是奇数，添加一个结束引号
        if len(triple_quote_positions) % 2 != 0:
            content += '\n\"\"\"'
            triple_quote_positions.append(len(content) - 3)
        
        # 修复模式2: 移除模块文档中的嵌套类文档
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是模块文档开始
            if i == 0 and line.strip().startswith('\"\"\"'):
                # 收集模块文档行
                module_doc_lines = [line]
                j = i + 1
                while j < len(lines) and not lines[j].strip().endswith('\"\"\"'):
                    module_doc_lines.append(lines[j])
                    j += 1
                
                if j < len(lines):
                    module_doc_lines.append(lines[j])
                    
                    # 清理模块文档
                    cleaned_doc = []
                    for doc_line in module_doc_lines:
                        stripped = doc_line.strip()
                        
                        # 跳过嵌套的三引号行
                        if stripped == '\"\"\"':
                            continue
                        
                        # 跳过类文档标题
                        if '类功能描述' in stripped and 'TODO' in stripped:
                            continue
                        
                        # 清理TODO行
                        if 'TODO:' in doc_line:
                            doc_line = re.sub(r'TODO:.*', '', doc_line)
                        
                        if doc_line.strip():
                            cleaned_doc.append(doc_line)
                    
                    # 确保有模块文档
                    if len(cleaned_doc) < 3:  # 至少要有开头的"""、内容和结尾的"""
                        filename = os.path.basename(filepath)
                        module_name = os.path.splitext(filename)[0]
                        simple_doc = [
                            '\"\"\"',
                            f'{module_name} - {filepath}',
                            '',
                            '模块功能描述。',
                            '',
                            '作者: XiangMeng',
                            '版本: 0.5.2-beta',
                            '\"\"\"'
                        ]
                        new_lines.extend(simple_doc)
                    else:
                        new_lines.extend(cleaned_doc)
                    
                    i = j + 1
                    continue
            
            new_lines.append(line)
            i += 1
        
        content = '\n'.join(new_lines)
        
        # 修复模式3: 确保类有文档字符串
        # 查找类定义
        class_pattern = r'^class\s+(\w+).*?:'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            class_name = match.group(1)
            class_start = match.start()
            
            # 获取类定义行
            lines_before = content[:class_start].count('\n')
            lines = content.split('\n')
            class_line_idx = lines_before
            class_line = lines[class_line_idx]
            
            # 计算缩进
            indent = len(class_line) - len(class_line.lstrip())
            
            # 检查下一行是否是文档字符串
            if class_line_idx + 1 < len(lines):
                next_line = lines[class_line_idx + 1].strip()
                if not (next_line.startswith('\"\"\"') or next_line.startswith("'''")):
                    # 添加简单的类文档字符串
                    class_doc = f'\n{" " * (indent + 4)}\"\"\"{class_name} - 类功能描述\"\"\"'
                    
                    # 插入位置
                    insert_pos = class_start + len(class_line)
                    content = content[:insert_pos] + class_doc + content[insert_pos:]
        
        # 修复模式4: 确保文件以换行符结束
        if not content.endswith('\n'):
            content += '\n'
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 验证修复后的代码
            if is_valid_python(content):
                return True
            else:
                # 恢复原始内容
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(original)
                return False
        
        return False
        
    except Exception as e:
        print(f"❌ 修复 {filepath} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🤖 智能修复文档字符串...")
    
    # 收集所有Python文件
    python_files = []
    for root, dirs, files in os.walk('zoo_framework'):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"📁 发现 {len(python_files)} 个Python文件")
    
    # 先修复有语法错误的文件
    fixed_count = 0
    for filepath in python_files[:50]:  # 先处理前50个文件
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not is_valid_python(content):
                print(f"🔧 修复语法错误: {filepath}")
                if fix_documentation(filepath):
                    fixed_count += 1
                    print("  ✅ 已修复")
                else:
                    print("  ❌ 修复失败")
        except Exception as e:
            print(f"❌ 读取 {filepath} 失败: {e}")
    
    print(f"\n🎉 修复完成！")
    print(f"🔧 修复了 {fixed_count} 个文件")
    
    # 运行自动修复
    print("\n🔄 运行自动修复...")
    os.system('python3 -m ruff check zoo_framework --fix --unsafe-fixes 2>&1 | tail -20')
    
    # 验证结果
    print("\n🔍 验证修复结果...")
    os.system('python3 -m ruff check zoo_framework --statistics')

if __name__ == '__main__':
    main()