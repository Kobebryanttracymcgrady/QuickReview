# QuickReview - 数码产品评测分析助手

输入产品型号或链接，AI 自动搜索并分析全网深度评测，生成优缺点清单和场景化购买建议。

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的硅基流动 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：
```
SILICONFLOW_API_KEY=sk-你的密钥
```

> 获取 API Key: https://cloud.siliconflow.cn

### 3. 启动后端

```bash
cd backend
python main.py
```

后端运行在 `http://localhost:8000`

### 4. 打开前端

直接用浏览器打开 `frontend/index.html`，或在设置中填入 API Key 即可使用。

## 项目结构

```
QuickReview/
├── backend/
│   ├── main.py              # FastAPI 后端
│   ├── requirements.txt     # Python 依赖
│   └── .env.example         # 环境变量模板
└── frontend/
    └── index.html           # 纯前端页面（无需构建）
```

## 技术栈

- **后端**: FastAPI + httpx（调用硅基流动 API）
- **AI 模型**: moonshotai/Kimi-K2.6（256K 上下文，支持搜索分析）
- **前端**: 原生 HTML/CSS/JS（零依赖，无需构建工具）

## API 说明

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/analyze` | POST | 分析产品评测 |
| `/api/health` | GET | 健康检查 |

### 分析接口请求体

```json
{
  "query": "iPhone 16 Pro",
  "api_key": "可选，覆盖默认 API Key"
}
```
