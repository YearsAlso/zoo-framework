#!/bin/bash
# 快速修复语法错误

echo "🚀 快速修复语法错误..."

# 1. 修复缺失闭合引号
echo "🔧 修复缺失闭合引号..."
find zoo_framework -name "*.py" -type f | while read file; do
    # 统计三引号数量
    count=$(grep -o '"""' "$file" | wc -l | tr -d ' ')
    if [ $((count % 2)) -ne 0 ]; then
        echo "  修复: $(basename "$file") (添加缺失的\"\"\")"
        echo '"""' >> "$file"
    fi
done

# 2. 修复中文标点
echo "🔧 修复中文标点..."
find zoo_framework -name "*.py" -type f -exec sed -i '' 's/：/:/g; s/，/,/g; s/；/;/g; s/。/./g' {} \;

# 3. 修复常见的语法错误模式
echo "🔧 修复常见语法错误..."
cat > /tmp/fix_patterns.py << 'EOF'
import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 修复模式：嵌套的文档字符串
    # """模块文档\n    """类文档\n    """\n更多内容"""
    lines = content.split('\n')
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # 跳过嵌套的三引号行
        if line.strip() == '"""' and i > 0 and lines[i-1].strip().startswith('"""'):
            i += 1
            continue
        
        new_lines.append(line)
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    # 移除模块文档中的类文档标题
    new_content = re.sub(r'模块功能描述：\s*"""', '模块功能描述：', new_content)
    new_content = re.sub(r'TODO:.*"""', 'TODO:', new_content)
    
    if new_content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

# 修复关键目录
key_dirs = ['zoo_framework/conf', 'zoo_framework/core', 'zoo_framework/params']
for dir_path in key_dirs:
    if os.path.exists(dir_path):
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        if fix_file(filepath):
                            print(f"修复: {filepath}")
                    except:
                        pass
EOF

python3 /tmp/fix_patterns.py

# 4. 运行Ruff自动修复
echo "🔄 运行Ruff自动修复..."
python3 -m ruff check zoo_framework --fix --unsafe-fixes 2>&1 | tail -5

echo "🎉 快速修复完成！"