#!/usr/bin/env python3
"""
正确修复文档字符串语法错误
"""

import os
import re

def correct_fix_file(filepath):
    """正确修复文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # 情况1: 完全损坏的文档字符串
        # 检查是否有嵌套的三引号
        if '\"\"\"\n    \"\"\"' in content or '\"\"\"\n        \"\"\"' in content:
            # 完全重建文档字符串
            filename = os.path.basename(filepath)
            module_name = os.path.splitext(filename)[0]
            
            # 提取类定义
            class_match = re.search(r'class\s+(\w+)', content)
            class_name = class_match.group(1) if class_match else 'Unknown'
            
            # 创建新的文档字符串
            new_doc = f'''"""
{module_name} - {filepath}

模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""

'''
            
            # 移除旧的损坏文档字符串
            # 找到第一个非文档字符串的内容
            lines = content.split('\n')
            new_lines = []
            in_doc = False
            doc_ended = False
            
            for line in lines:
                stripped = line.strip()
                
                if stripped.startswith('\"\"\"') and not doc_ended:
                    if not in_doc:
                        in_doc = True
                    else:
                        in_doc = False
                        doc_ended = True
                    continue
                
                if not in_doc:
                    new_lines.append(line)
            
            # 组合新内容
            new_content = new_doc + '\n'.join(new_lines)
            
            # 确保类有文档字符串
            if class_match and f'class {class_name}' in new_content:
                # 在类定义后添加文档字符串
                class_pos = new_content.find(f'class {class_name}')
                after_class = new_content[class_pos:]
                class_def_end = after_class.find(':') + 1
                
                # 检查类后是否有文档字符串
                after_def = after_class[class_def_end:].lstrip()
                if not after_def.startswith('\"\"\"'):
                    # 添加类文档字符串
                    indent = ' ' * 4
                    class_doc = f'\n{indent}\"\"\"{class_name} - 类功能描述\"\"\"'
                    insert_pos = class_pos + class_def_end
                    new_content = new_content[:insert_pos] + class_doc + new_content[insert_pos:]
            
            content = new_content
        
        # 情况2: 缺少文件末尾换行符
        if not content.endswith('\n'):
            content += '\n'
        
        # 情况3: 移除空白行中的空格
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if line.strip() == '':
                cleaned_lines.append('')
            else:
                # 移除行尾空格
                cleaned_lines.append(line.rstrip())
        content = '\n'.join(cleaned_lines)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 修复 {filepath} 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔧 正确修复语法错误...")
    
    # 先修复几个关键文件
    key_files = [
        'zoo_framework/constant/waiter_constant.py',
        'zoo_framework/constant/worker_constant.py',
        'zoo_framework/workers/worker_result.py'
    ]
    
    for filepath in key_files:
        if os.path.exists(filepath):
            print(f"🔧 修复: {filepath}")
            if correct_fix_file(filepath):
                print("  ✅ 已修复")
            else:
                print("  ⚠️  无需修复")
    
    # 验证修复
    print("\n🔍 验证修复结果...")
    os.system('python3 -m ruff check zoo_framework/constant/waiter_constant.py')
    print("\n---")
    os.system('python3 -m ruff check zoo_framework/constant/worker_constant.py')

if __name__ == '__main__':
    main()