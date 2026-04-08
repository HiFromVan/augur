#!/bin/bash

# AI 功能配置和测试脚本

echo "================================"
echo "Augur AI 功能配置向导"
echo "================================"
echo ""

# 检查是否已有 .env 文件
if [ -f .env ]; then
    echo "✓ 发现现有 .env 文件"
    source .env
else
    echo "创建新的 .env 文件..."
    cp .env.example .env
fi

# 检查 API Key
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "sk-ant-xxxxx" ]; then
    echo ""
    echo "⚠️  未检测到有效的 Anthropic API Key"
    echo ""
    echo "请按照以下步骤获取 API Key:"
    echo "1. 访问 https://console.anthropic.com/"
    echo "2. 注册/登录账号"
    echo "3. 创建 API Key"
    echo "4. 复制 Key (格式: sk-ant-xxxxx)"
    echo ""
    read -p "请输入你的 Anthropic API Key: " api_key

    if [ -z "$api_key" ]; then
        echo "❌ 未输入 API Key，退出配置"
        exit 1
    fi

    # 更新 .env 文件
    if grep -q "ANTHROPIC_API_KEY=" .env; then
        sed -i.bak "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$api_key|" .env
    else
        echo "ANTHROPIC_API_KEY=$api_key" >> .env
    fi

    echo "✓ API Key 已保存到 .env 文件"
    export ANTHROPIC_API_KEY=$api_key
else
    echo "✓ 检测到 API Key: ${ANTHROPIC_API_KEY:0:20}..."
fi

echo ""
echo "================================"
echo "测试 AI 功能"
echo "================================"
echo ""

# 测试 1: 检查 Python 依赖
echo "[1/4] 检查 Python 依赖..."
if python3 -c "import anthropic" 2>/dev/null; then
    echo "✓ anthropic 库已安装"
else
    echo "⚠️  anthropic 库未安装，正在安装..."
    pip3 install anthropic
fi

if python3 -c "import httpx" 2>/dev/null; then
    echo "✓ httpx 库已安装"
else
    echo "⚠️  httpx 库未安装，正在安装..."
    pip3 install httpx
fi

# 测试 2: 测试 API 连接
echo ""
echo "[2/4] 测试 Anthropic API 连接..."
python3 << 'EOF'
import os
from anthropic import Anthropic

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("❌ API Key 未设置")
    exit(1)

try:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=50,
        messages=[{"role": "user", "content": "Say hello in Chinese"}]
    )
    print(f"✓ API 连接成功")
    print(f"  响应: {response.content[0].text}")
except Exception as e:
    print(f"❌ API 连接失败: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ API 测试失败，请检查 API Key 是否正确"
    exit 1
fi

# 测试 3: 检查后端服务
echo ""
echo "[3/4] 检查后端服务..."
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "✓ 后端服务运行中 (http://localhost:8000)"
else
    echo "⚠️  后端服务未运行"
    echo "   请运行: python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
fi

# 测试 4: 检查前端服务
echo ""
echo "[4/4] 检查前端服务..."
if curl -s http://localhost:3000 > /dev/null; then
    echo "✓ 前端服务运行中 (http://localhost:3000)"
else
    echo "⚠️  前端服务未运行"
    echo "   请运行: cd web && npm run dev"
fi

echo ""
echo "================================"
echo "配置完成！"
echo "================================"
echo ""
echo "AI 功能使用指南:"
echo ""
echo "1. 对话功能:"
echo "   - 访问 http://localhost:3000"
echo "   - 点击右下角聊天按钮"
echo "   - 输入问题测试"
echo ""
echo "2. 批量生成预测说明:"
echo "   export ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
echo "   python3 src/generate_explanations.py 5"
echo ""
echo "3. 查看完整文档:"
echo "   cat docs/AI_INTEGRATION.md"
echo ""
echo "成本估算: 每 1000 次对话约 $2.80"
echo ""
