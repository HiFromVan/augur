# 订阅体系更新 & AI 功能接入总结

## 📋 更新概览

### 1. 新的订阅体系

已将订阅从月付/季付/年付改为两档年付制：

#### 基础档 - ¥1399/年
- ✅ 查看所有比赛预测
- ✅ 五大联赛全覆盖
- ✅ 历史数据查询
- ✅ 基础统计分析
- ❌ AI 对话助手
- ❌ 高级筛选功能
- ❌ 数据导出
- ❌ API 访问
- ❌ 投注组合跟踪
- ❌ 高级分析报告
- ❌ 优先客服

#### 高级档 - ¥2399/年（推荐）
- ✅ 基础档所有功能
- ✅ **🤖 专属 AI 对话助手**
- ✅ 高级筛选功能
- ✅ 数据导出 (CSV/Excel)
- ✅ API 访问权限
- ✅ 投注组合跟踪
- ✅ 高级分析报告
- ✅ 优先客服支持

### 2. AI 功能实现

#### ✅ 已实现功能

1. **AI 对话助手**
   - 位置：所有页面右下角浮动按钮
   - 模型：Claude 3.5 Haiku
   - 功能：
     - 回答足球预测问题
     - 解释比赛预测依据
     - 分析球队表现
     - 提供投注建议
   - 权限：仅高级档用户可用

2. **批量生成预测说明**
   - 脚本：`src/generate_explanations.py`
   - 功能：为所有比赛生成 150-200 字 AI 分析
   - 使用：`python3 src/generate_explanations.py 10`

3. **权限控制系统**
   - 数据库函数：`check_user_feature(user_id, feature_name)`
   - API 权限检查：chat 端点验证用户是否有 `ai_chat` 权限
   - 前端提示：非高级档用户点击 AI 按钮时提示升级

#### 🚧 待实现功能（高级档专属）

1. **高级筛选功能**
   - 按价值区间筛选
   - 按联赛/球队筛选
   - 按预测概率筛选
   - 自定义筛选条件保存

2. **数据导出**
   - 导出预测数据为 CSV
   - 导出为 Excel 格式
   - 自定义导出字段
   - 批量导出历史数据

3. **投注组合跟踪**
   - 记录用户投注
   - 计算投注收益
   - ROI 统计
   - 投注历史分析

4. **高级分析报告**
   - 每周预测表现报告
   - 个性化推荐
   - 趋势分析
   - PDF 报告生成

5. **API 访问**
   - RESTful API 端点
   - API Key 管理
   - 速率限制
   - API 文档

6. **媒体分析**
   - 新闻爬虫
   - 伤病信息整合
   - 社交媒体情感分析
   - AI 生成赛前分析

## 🗄️ 数据库变更

### 新增迁移

**006_update_subscription_tiers.sql**
- 添加 `features` JSONB 字段到 `subscription_plans`
- 添加 `subscription_plan_id` 到 `users` 表
- 创建 `check_user_feature()` 函数
- 创建 `get_user_plan_info()` 函数
- 更新套餐数据为基础档和高级档

**005_add_ai_explanation.sql**
- 添加 `ai_explanation` TEXT 字段到 `matches`
- 添加 `explanation_generated_at` TIMESTAMP 字段

### 套餐数据

```sql
-- 基础档
plan_code: 'basic_yearly'
price: 139900 (¥1399)
duration_days: 365

-- 高级档
plan_code: 'premium_yearly'
price: 239900 (¥2399)
duration_days: 365
```

## 🔧 技术实现

### 后端 API 更新

**src/api/main.py**
- `/api/chat` 端点添加权限检查
- 使用 `check_user_feature()` 验证 `ai_chat` 权限
- 返回 403 错误给非高级档用户

### 前端更新

**web/app/pricing/page.tsx**
- 重新设计为 2 列布局
- 动态显示功能列表（基于 `features` 字段）
- 高级功能用金色图标标识
- 高级档卡片突出显示（边框、缩放）

**web/components/ChatWindow.tsx**
- 已集成到首页和比赛详情页
- 浮动按钮设计
- 支持比赛上下文
- 对话历史管理

## 📊 成本估算

### Anthropic Claude 3.5 Haiku 定价
- 输入：$0.80 / 百万 tokens
- 输出：$4.00 / 百万 tokens

### 月度成本估算（100 高级档用户）
- 对话：1000 次 × $0.0028 = **$2.80**
- 说明生成：500 场 × $0.0018 = **$0.90**
- 媒体分析：200 场 × $0.0036 = **$0.72**
- **总计：~$4.50/月**

### 收入估算
- 基础档：10 用户 × ¥1399 = ¥13,990/年
- 高级档：100 用户 × ¥2399 = ¥239,900/年
- **总计：¥253,890/年**
- **AI 成本：~$54/年 (¥390)**
- **利润率：99.8%**

## 🚀 配置步骤

### 1. 获取 Anthropic API Key

```bash
# 访问 https://console.anthropic.com/
# 注册并创建 API Key
```

### 2. 配置环境变量

```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 3. 运行迁移

```bash
# 已完成
python3 -c "import asyncio; import asyncpg; ..."
```

### 4. 重启服务

```bash
# 后端会自动重载
# 前端已清除缓存并重启
```

### 5. 测试 AI 功能

```bash
# 使用配置脚本
chmod +x scripts/setup_ai.sh
./scripts/setup_ai.sh

# 或手动测试
python3 src/generate_explanations.py 2
```

## 📝 使用指南

### 用户端

1. **查看定价**：访问 `/pricing` 页面
2. **订阅套餐**：选择基础档或高级档
3. **使用 AI 对话**：
   - 高级档用户：点击右下角聊天按钮
   - 基础档用户：点击后提示升级

### 管理端

1. **批量生成说明**：
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-xxxxx
   python3 src/generate_explanations.py 50
   ```

2. **检查用户权限**：
   ```sql
   SELECT check_user_feature(user_id, 'ai_chat');
   ```

3. **查看套餐信息**：
   ```sql
   SELECT * FROM subscription_plans;
   ```

## 📂 相关文件

### 新增文件
- `src/migrations/005_add_ai_explanation.sql` - AI 说明字段
- `src/migrations/006_update_subscription_tiers.sql` - 订阅体系更新
- `src/generate_explanations.py` - 批量生成脚本
- `scripts/setup_ai.sh` - AI 配置脚本
- `docs/AI_INTEGRATION.md` - AI 接入文档
- `.env.example` - 环境变量模板

### 修改文件
- `src/api/main.py` - 添加 AI chat 权限检查
- `web/app/pricing/page.tsx` - 新定价页面
- `web/components/ChatWindow.tsx` - AI 对话组件
- `web/app/page.tsx` - 集成 ChatWindow
- `web/app/match/[id]/page.tsx` - 集成 ChatWindow

## ✅ 测试清单

- [x] 数据库迁移成功
- [x] 套餐数据正确
- [x] 定价页面显示正确
- [x] AI 对话组件渲染
- [x] 权限检查功能
- [x] 后端 API 正常运行
- [x] 前端页面正常访问
- [ ] 支付流程（待开发）
- [ ] 高级功能实现（待开发）

## 🎯 下一步计划

### 短期（1-2周）
1. 实现支付集成（支付宝/微信）
2. 完善用户账户管理页面
3. 添加订阅状态提醒
4. 实现数据导出功能

### 中期（1-2月）
1. 开发高级筛选功能
2. 实现投注组合跟踪
3. 开发 API 访问功能
4. 添加高级分析报告

### 长期（3-6月）
1. 媒体分析功能
2. 移动端 App
3. 社区功能
4. 推荐系统优化

## 📞 技术支持

- 文档：`docs/AI_INTEGRATION.md`
- 配置脚本：`scripts/setup_ai.sh`
- API 文档：http://localhost:8000/docs

---

**更新时间**：2026-04-08
**版本**：v2.0
**状态**：✅ 已部署
