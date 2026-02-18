#!/usr/bin/env python3
"""
简单测试：验证Zoo-Framework基本功能
"""

import sys
import os

def test_imports():
    """测试基本导入"""
    print("🧪 测试基本导入...")
    
    try:
        import zoo_framework
        print("✅ zoo_framework 导入成功")
        print(f"   版本: {zoo_framework.__version__}")
    except Exception as e:
        print(f"❌ zoo_framework 导入失败: {e}")
        return False
    
    # 测试核心模块
    modules_to_test = [
        ('zoo_framework.core', '核心模块'),
        ('zoo_framework.utils', '工具模块'),
        ('zoo_framework.workers', '工作器模块'),
        ('zoo_framework.params', '参数模块'),
    ]
    
    all_passed = True
    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {description} 导入成功")
        except Exception as e:
            print(f"❌ {description} 导入失败: {e}")
            all_passed = False
    
    return all_passed

def test_syntax():
    """测试语法"""
    print("\n🔍 测试语法检查...")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ['python3', '-m', 'ruff', 'check', 'zoo_framework', '--statistics'],
            capture_output=True,
            text=True,
            cwd='/tmp/zoo-framework'
        )
        
        if result.returncode == 0:
            print("✅ Ruff检查通过（0错误）")
            return True
        else:
            print("❌ Ruff检查失败")
            print(f"输出:\n{result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Ruff检查执行失败: {e}")
        return False

def test_basic_functionality():
    """测试基本功能"""
    print("\n⚙️ 测试基本功能...")
    
    try:
        # 测试ParamsPath
        from zoo_framework.core import ParamsPath
        path = ParamsPath("test.path", "default")
        print(f"✅ ParamsPath 创建成功: {path}")
        
        # 测试WorkerResult
        from zoo_framework.workers import WorkerResult
        result = WorkerResult("test", "data", "TestWorker")
        print(f"✅ WorkerResult 创建成功: {result}")
        
        # 测试工具模块
        from zoo_framework.utils import FileUtils
        print(f"✅ FileUtils 导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 基本功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 Zoo-Framework 简单测试")
    print("=" * 50)
    
    # 添加项目路径
    sys.path.insert(0, '/tmp/zoo-framework')
    
    # 运行测试
    import_passed = test_imports()
    syntax_passed = test_syntax()
    functionality_passed = test_basic_functionality()
    
    print("\n" + "=" * 50)
    print("📊 测试结果:")
    print(f"  导入测试: {'✅ 通过' if import_passed else '❌ 失败'}")
    print(f"  语法检查: {'✅ 通过' if syntax_passed else '❌ 失败'}")
    print(f"  功能测试: {'✅ 通过' if functionality_passed else '❌ 失败'}")
    
    if import_passed and syntax_passed and functionality_passed:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n⚠️  测试失败，需要进一步修复")
        return 1

if __name__ == '__main__':
    sys.exit(main())