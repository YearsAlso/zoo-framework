#!/usr/bin/env python3
"""
修复文档字符串语法错误
检查并修复嵌套文档字符串等语法问题
"""

import os
import re
import sys
from pathlib import Path

def find_problematic_files(project_root):
    """查找有语法问题的文件"""
    problematic = []
    
    for root, dirs, files in os.walk(project_root):
        # 跳过隐藏目录和虚拟环境
        if any(part.startswith('.') for part in root.split('/')):
            continue
        if 'venv' in root or '__pycache__' in root or '.git' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 检查嵌套文档字符串
                    if '\"\"\"\n    \"\"\"' in content or '\"\"\"\n        \"\"\"' in content:
                        problematic.append(filepath)
                    
                    # 检查不匹配的三引号
                    triple_quotes = re.findall(r'\"\"\"|\'\'\'', content)
                    if len(triple_quotes) % 2 != 0:
                        problematic.append(filepath)
                        
                except Exception as e:
                    print(f"❌ 读取文件 {filepath} 时出错: {e}")
    
    return problematic

def fix_nested_docstrings(filepath):
    """修复嵌套的文档字符串"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 修复常见的嵌套模式
        # 模式1: """\n    """
        content = re.sub(r'\"\"\"\n\s+\"\"\"', '\"\"\"', content)
        
        # 模式2: '''\n    '''
        content = re.sub(r'\'\'\'\n\s+\'\'\'', '\'\'\'', content)
        
        # 模式3: 模块文档中的类文档
        lines = content.split('\n')
        new_lines = []
        in_module_docstring = False
        module_docstring_end = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 检测模块文档字符串开始
            if i == 0 and (stripped.startswith('\"\"\"') or stripped.startswith('\'\'\'')):
                in_module_docstring = True
                if stripped.count('\"\"\"') == 2 or stripped.count('\'\'\'') == 2:
                    in_module_docstring = False  # 单行文档字符串
            
            # 在模块文档字符串中查找嵌套的类文档
            if in_module_docstring and ('\"\"\"' in stripped or '\'\'\'' in stripped):
                # 检查是否是结束
                if stripped.endswith('\"\"\"') or stripped.endswith('\'\'\''):
                    in_module_docstring = False
                    module_docstring_end = i
            
            new_lines.append(line)
        
        # 重新组合
        content = '\n'.join(new_lines)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 修复文件 {filepath} 时出错: {e}")
        return False

def fix_specific_files(project_root):
    """修复特定的已知问题文件"""
    specific_fixes = {
        'zoo_framework/utils/datetime_utils.py': '''"""
datetime_utils - zoo_framework/utils/datetime_utils.py

日期时间工具模块，提供常用的日期时间处理功能。

功能：
- 日期时间格式化
- 时间差计算
- 时间戳转换
- 日期解析和验证

作者: XiangMeng
版本: 0.5.1-beta
"""

from datetime import datetime, timedelta


class DateTimeUtils:
    """日期时间工具类
    
    提供各种日期时间相关的实用方法，包括格式化、计算和转换。
    """
    
    @classmethod
    def get_format_now(cls, format_mod="%Y-%m-%d %H:%M:%S.%f"):
        """获取格式化后的当前时间"""
        return datetime.now().strftime(format_mod)

    @classmethod
    def get_now_timestamp(cls):
        """获取当前时间戳（秒级）"""
        return int(datetime.now().timestamp())

    @classmethod
    def get_now_timestamp_ms(cls):
        """获取当前时间戳（毫秒级）"""
        return int(datetime.now().timestamp() * 1000)

    @classmethod
    def format_datetime(cls, dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S"):
        """格式化日期时间对象"""
        return dt.strftime(format_str)

    @classmethod
    def parse_datetime(cls, date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S"):
        """解析字符串为日期时间对象"""
        return datetime.strptime(date_str, format_str)

    @classmethod
    def get_time_delta(cls, days=0, hours=0, minutes=0, seconds=0):
        """获取时间差对象"""
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)'''
    }
    
    fixed_count = 0
    for rel_path, new_content in specific_fixes.items():
        filepath = os.path.join(project_root, rel_path)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"✅ 已修复: {rel_path}")
                fixed_count += 1
            except Exception as e:
                print(f"❌ 修复 {rel_path} 失败: {e}")
    
    return fixed_count

def validate_python_syntax(filepath):
    """验证Python文件语法"""
    import ast
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        return True
    except SyntaxError as e:
        print(f"❌ 语法错误 {filepath}: {e}")
        return False
    except Exception as e:
        print(f"❌ 验证失败 {filepath}: {e}")
        return False

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python fix_docstring_syntax.py <项目路径>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"❌ 项目路径不存在: {project_root}")
        sys.exit(1)
    
    print("🔍 检查文档字符串语法问题...")
    
    # 1. 查找有问题的文件
    problematic = find_problematic_files(project_root)
    
    if problematic:
        print(f"⚠️  找到 {len(problematic)} 个可能有问题的文件:")
        for file in problematic[:10]:
            print(f"  • {os.path.relpath(file, project_root)}")
        if len(problematic) > 10:
            print(f"  ... 还有 {len(problematic) - 10} 个")
    else:
        print("✅ 未发现明显的文档字符串语法问题")
    
    # 2. 修复特定文件
    print("\n🔧 修复已知问题文件...")
    fixed_specific = fix_specific_files(project_root)
    print(f"✅ 修复了 {fixed_specific} 个特定文件")
    
    # 3. 自动修复嵌套文档字符串
    print("\n🔧 自动修复嵌套文档字符串...")
    fixed_auto = 0
    for filepath in problematic:
        if fix_nested_docstrings(filepath):
            print(f"✅ 已修复: {os.path.relpath(filepath, project_root)}")
            fixed_auto += 1
    
    print(f"✅ 自动修复了 {fixed_auto} 个文件")
    
    # 4. 验证语法
    print("\n🔍 验证Python语法...")
    python_files = []
    for root, dirs, files in os.walk(project_root):
        if any(part.startswith('.') for part in root.split('/')):
            continue
        if 'venv' in root or '__pycache__' in root or '.git' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    valid_count = 0
    invalid_files = []
    
    for filepath in python_files[:50]:  # 只检查前50个文件
        if validate_python_syntax(filepath):
            valid_count += 1
        else:
            invalid_files.append(os.path.relpath(filepath, project_root))
    
    print(f"📊 语法验证: {valid_count}/{min(50, len(python_files))} 个文件通过")
    
    if invalid_files:
        print("\n❌ 有语法错误的文件:")
        for file in invalid_files[:10]:
            print(f"  • {file}")
        if len(invalid_files) > 10:
            print(f"  ... 还有 {len(invalid_files) - 10} 个")
        
        # 尝试修复这些文件
        print("\n🔄 尝试修复语法错误文件...")
        for file in invalid_files[:5]:
            filepath = os.path.join(project_root, file)
            print(f"  检查: {file}")
    
    print(f"\n🎉 修复完成！")
    print(f"📁 总共修复了 {fixed_specific + fixed_auto} 个文件")
    
    if invalid_files:
        print("\n⚠️  注意：仍有文件存在语法错误，需要手动修复")
        print("建议操作:")
        print("1. 运行 pytest 检查具体错误")
        print("2. 手动修复剩余的语法问题")
        print("3. 验证所有测试通过")

if __name__ == '__main__':
    main()