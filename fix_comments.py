#!/usr/bin/env python3
"""
注释检查和修复脚本
检查 Zoo-Framework 项目的注释完整性，并添加缺失的注释
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class CommentAnalyzer:
    """注释分析器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.stats = {
            'files_analyzed': 0,
            'files_fixed': 0,
            'modules_without_docstring': [],
            'classes_without_docstring': [],
            'functions_without_docstring': [],
            'low_comment_files': []
        }
    
    def find_python_files(self) -> List[Path]:
        """查找所有Python文件"""
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)
            
            # 跳过隐藏目录和虚拟环境
            if any(part.startswith('.') for part in root_path.relative_to(self.project_root).parts):
                continue
            if 'venv' in root or '__pycache__' in root or '.git' in root:
                continue
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(root_path / file)
        
        return python_files
    
    def analyze_file(self, filepath: Path) -> Dict:
        """分析单个文件的注释情况"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            relative_path = filepath.relative_to(self.project_root)
            
            # 检查模块文档字符串
            has_module_docstring = content.strip().startswith('"""') or content.strip().startswith("'''")
            
            # 查找类定义
            class_pattern = r'^class\s+(\w+)(?:\([^)]*\))?:'
            classes = []
            for match in re.finditer(class_pattern, content, re.MULTILINE):
                class_name = match.group(1)
                class_start = match.start()
                
                # 检查类是否有文档字符串
                has_docstring = False
                # 查找类定义后的第一个三引号字符串
                after_class = content[class_start:]
                docstring_match = re.search(r'^\s*(\"\"\"|\'\'\')', after_class, re.MULTILINE)
                if docstring_match:
                    has_docstring = True
                
                classes.append({
                    'name': class_name,
                    'has_docstring': has_docstring,
                    'line': content[:class_start].count('\n') + 1
                })
            
            # 查找函数定义（排除类方法）
            function_pattern = r'^def\s+(\w+)\s*\([^)]*\)(?:\s*->[^:]+)?:'
            functions = []
            for match in re.finditer(function_pattern, content, re.MULTILINE):
                func_name = match.group(1)
                func_start = match.start()
                
                # 检查是否是类方法（前面有缩进）
                lines_before = content[:func_start].split('\n')
                if lines_before:
                    last_line = lines_before[-1]
                    if last_line and not last_line[0].isspace():
                        # 顶级函数
                        has_docstring = False
                        after_func = content[func_start:]
                        docstring_match = re.search(r'^\s*(\"\"\"|\'\'\')', after_func, re.MULTILINE)
                        if docstring_match:
                            has_docstring = True
                        
                        functions.append({
                            'name': func_name,
                            'has_docstring': has_docstring,
                            'line': content[:func_start].count('\n') + 1
                        })
            
            # 计算注释比例
            lines = content.split('\n')
            total_lines = len(lines)
            comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
            
            # 粗略估计文档字符串行数
            docstring_matches = re.findall(r'(\"\"\"|\'\'\')', content)
            docstring_lines = len(docstring_matches) * 2  # 粗略估计
            
            comment_ratio = (comment_lines + docstring_lines) / total_lines if total_lines > 0 else 0
            
            return {
                'file': relative_path,
                'has_module_docstring': has_module_docstring,
                'classes': classes,
                'functions': functions,
                'total_lines': total_lines,
                'comment_lines': comment_lines,
                'docstring_lines': docstring_lines,
                'comment_ratio': comment_ratio,
                'needs_fix': not has_module_docstring or comment_ratio < 0.1
            }
            
        except Exception as e:
            print(f"❌ 分析文件 {filepath} 时出错: {e}")
            return None
    
    def add_module_docstring(self, filepath: Path) -> bool:
        """添加模块文档字符串"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 如果已经有文档字符串，跳过
            if content.strip().startswith('"""') or content.strip().startswith("'''"):
                return False
            
            # 获取模块名
            module_name = filepath.stem
            relative_path = filepath.relative_to(self.project_root)
            
            # 创建文档字符串
            docstring = f'''"""
{module_name} - {relative_path}

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

'''
            
            # 如果有 shebang 或编码声明，放在它们后面
            lines = content.split('\n')
            new_lines = []
            shebang_added = False
            encoding_added = False
            
            for i, line in enumerate(lines):
                new_lines.append(line)
                if i == 0 and line.startswith('#!'):
                    shebang_added = True
                elif i == (1 if shebang_added else 0) and ('coding' in line or 'encoding' in line):
                    encoding_added = True
                elif i == (1 if shebang_added else 0) and not encoding_added:
                    # 插入文档字符串
                    new_lines.append(docstring.strip())
            
            # 如果没有 shebang 或编码声明，直接在最前面添加
            if not shebang_added and not encoding_added:
                new_content = docstring + content
            else:
                new_content = '\n'.join(new_lines)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ 已添加模块文档字符串: {relative_path}")
            return True
            
        except Exception as e:
            print(f"❌ 添加模块文档字符串失败 {filepath}: {e}")
            return False
    
    def add_class_docstring(self, filepath: Path, class_name: str, line_number: int) -> bool:
        """添加类文档字符串"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 找到类定义行
            class_line_idx = line_number - 1
            
            # 检查是否已经有文档字符串
            if class_line_idx + 1 < len(lines):
                next_line = lines[class_line_idx + 1].strip()
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    return False
            
            # 创建文档字符串
            indent_match = re.match(r'^(\s*)', lines[class_line_idx])
            indent = indent_match.group(1) if indent_match else ''
            
            docstring = f'{indent}    """{class_name} - 类功能描述\n\n    TODO: 添加类功能详细描述\n    """\n'
            
            # 插入文档字符串
            lines.insert(class_line_idx + 1, docstring)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            relative_path = filepath.relative_to(self.project_root)
            print(f"✅ 已添加类文档字符串: {relative_path}.{class_name}")
            return True
            
        except Exception as e:
            print(f"❌ 添加类文档字符串失败 {filepath}.{class_name}: {e}")
            return False
    
    def add_function_docstring(self, filepath: Path, func_name: str, line_number: int) -> bool:
        """添加函数文档字符串"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 找到函数定义行
            func_line_idx = line_number - 1
            
            # 检查是否已经有文档字符串
            if func_line_idx + 1 < len(lines):
                next_line = lines[func_line_idx + 1].strip()
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    return False
            
            # 创建文档字符串
            indent_match = re.match(r'^(\s*)', lines[func_line_idx])
            indent = indent_match.group(1) if indent_match else ''
            
            docstring = f'{indent}    """{func_name} - 函数功能描述\n\n    TODO: 添加函数参数和返回值描述\n    """\n'
            
            # 插入文档字符串
            lines.insert(func_line_idx + 1, docstring)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            relative_path = filepath.relative_to(self.project_root)
            print(f"✅ 已添加函数文档字符串: {relative_path}.{func_name}()")
            return True
            
        except Exception as e:
            print(f"❌ 添加函数文档字符串失败 {filepath}.{func_name}: {e}")
            return False
    
    def run_analysis(self):
        """运行分析"""
        print("🔍 开始分析代码注释...")
        print("=" * 80)
        
        python_files = self.find_python_files()
        print(f"📁 找到 {len(python_files)} 个Python文件")
        
        core_files = [f for f in python_files if 'zoo_framework' in str(f) and 'test' not in str(f)]
        print(f"🔧 核心模块文件: {len(core_files)} 个")
        
        for filepath in core_files:
            analysis = self.analyze_file(filepath)
            if not analysis:
                continue
            
            self.stats['files_analyzed'] += 1
            relative_path = analysis['file']
            
            # 记录需要修复的问题
            if not analysis['has_module_docstring']:
                self.stats['modules_without_docstring'].append(str(relative_path))
            
            for cls in analysis['classes']:
                if not cls['has_docstring']:
                    self.stats['classes_without_docstring'].append(
                        f"{relative_path}.{cls['name']} (第{cls['line']}行)"
                    )
            
            for func in analysis['functions']:
                if not func['has_docstring']:
                    self.stats['functions_without_docstring'].append(
                        f"{relative_path}.{func['name']}() (第{func['line']}行)"
                    )
            
            if analysis['comment_ratio'] < 0.1:
                self.stats['low_comment_files'].append(
                    f"{relative_path} (注释率: {analysis['comment_ratio']:.1%})"
                )
        
        # 输出分析结果
        print("\n📊 分析结果:")
        print("-" * 80)
        print(f"📁 分析文件数: {self.stats['files_analyzed']}")
        print(f"⚠️  缺少模块文档: {len(self.stats['modules_without_docstring'])}")
        print(f"⚠️  缺少类文档: {len(self.stats['classes_without_docstring'])}")
        print(f"⚠️  缺少函数文档: {len(self.stats['functions_without_docstring'])}")
        print(f"⚠️  注释率低文件: {len(self.stats['low_comment_files'])}")
        
        if self.stats['modules_without_docstring']:
            print("\n📝 缺少模块文档的文件:")
            for file in self.stats['modules_without_docstring'][:10]:
                print(f"  • {file}")
            if len(self.stats['modules_without_docstring']) > 10:
                print(f"  ... 还有 {len(self.stats['modules_without_docstring']) - 10} 个")
        
        if self.stats['classes_without_docstring']:
            print("\n🏗️  缺少类文档:")
            for cls in self.stats['classes_without_docstring'][:10]:
                print(f"  • {cls}")
            if len(self.stats['classes_without_docstring']) > 10:
                print(f"  ... 还有 {len(self.stats['classes_without_docstring']) - 10} 个")
        
        if self.stats['low_comment_files']:
            print("\n📉 注释率低的文件 (<10%):")
            for file in self.stats['low_comment_files'][:10]:
                print(f"  • {file}")
    
    def run_fixes(self, dry_run: bool = False):
        """运行修复"""
        print("\n🔧 开始修复注释...")
        print("=" * 80)
        
        if dry_run:
            print("🏃 干跑模式 - 只显示会修复的内容，不实际修改文件")
        
        python_files = self.find_python_files()
        core_files = [f for f in python_files if 'zoo_framework' in str(f) and 'test' not in str(f)]
        
        fixed_count = 0
        
        for filepath in core_files:
            analysis = self.analyze_file(filepath)
            if not analysis:
                continue
            
            relative_path = analysis['file']
            needs_fix = False
            
            # 修复模块文档字符串
            if not analysis['has_module_docstring']:
                print(f"📝 需要添加模块文档: {relative_path}")
                if not dry_run:
                    if self.add_module_docstring(filepath):
                        fixed_count += 1
                        needs_fix = True
            
            # 修复类文档字符串
            for cls in analysis['classes']:
                if not cls['has_docstring']:
                    print(f"🏗️  需要添加类文档: {relative_path}.{cls['name']}")
                    if not dry_run:
                        if self.add_class_docstring(filepath, cls['name'], cls['line']):
                            fixed_count += 1
                            needs_fix = True
            
            # 修复函数文档字符串
            for func in analysis['functions']:
                if not func['has_docstring']:
                    print(f"🔧 需要添加函数文档: {relative_path}.{func['name']}()")
                    if not dry_run:
                        if self.add_function_docstring(filepath, func['name'], func['line']):
                            fixed_count += 1
                            needs_fix = True
            
            if needs_fix:
                self.stats['files_fixed'] += 1
        
        print(f"\n✅ 修复完成！共修复 {fixed_count} 处注释问题")
        print(f"📁 修改了 {self.stats['files_fixed']} 个文件")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python fix_comments.py <项目路径> [--dry-run]")
        sys.exit(1)
    
    project_root = sys.argv[1]
    dry_run = '--dry-run' in sys.argv
    
    if not os.path.exists(project_root):
        print(f"❌ 项目路径不存在: {project_root}")
        sys.exit(1)
    
    analyzer = CommentAnalyzer(project_root)
    
    # 运行分析
    analyzer.run_analysis()
    
    # 询问是否继续修复
    if not dry_run:
        response = input("\n是否继续修复注释？(y/N): ")
        if response.lower() != 'y':
            print("❌ 用户取消操作")
            return
    
    # 运行修复
    analyzer.run_fixes(dry_run=dry_run)
    
    # 输出总结
    print("\n🎉 注释修复完成！")
    print("=" * 80)
    print("建议后续操作:")
    print("1. 审查自动添加的文档字符串，补充具体内容")
    print("2. 运行测试确保没有破坏现有功能")
    print("3. 提交代码到新分支")
    print("4. 创建 Pull Request 合并到 develop 分支")

if __name__ == '__main__':
    main()