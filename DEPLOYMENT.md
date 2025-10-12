# Railway + Docker 部署指南

本指南将帮助你使用 Railway 和 Docker 部署后端项目。

## 📋 前置要求

1. [Railway](https://railway.app/) 账号
2. 安装 [Railway CLI](https://docs.railway.app/develop/cli)（可选）
3. 准备好所需的 API Keys：
   - OpenAI API Key
   - Anthropic API Key（可选）
   - Tavily API Key（可选）

## 🚀 快速部署步骤

### 方法一：通过 Railway 网页界面部署

1. **登录 Railway**

   - 访问 [railway.app](https://railway.app/)
   - 登录你的账号

2. **创建新项目**

   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 授权并选择你的仓库

3. **配置环境变量**

   - 在项目设置中点击 "Variables"
   - 添加以下环境变量：
     ```
     OPENAI_API_KEY=你的-openai-api-key
     ANTHROPIC_API_KEY=你的-anthropic-api-key
     TAVILY_API_KEY=你的-tavily-api-key
     ```

4. **部署**
   - Railway 会自动检测 Dockerfile 并开始构建
   - 等待部署完成
   - 获取生成的 URL

### 方法二：使用 Railway CLI 部署

1. **安装 Railway CLI**

   ```bash
   # macOS/Linux
   curl -fsSL https://railway.app/install.sh | sh

   # Windows (PowerShell)
   iwr https://railway.app/install.ps1 | iex
   ```

2. **登录 Railway**

   ```bash
   railway login
   ```

3. **初始化项目**

   ```bash
   cd backend
   railway init
   ```

4. **设置环境变量**

   ```bash
   railway variables set OPENAI_API_KEY="你的-openai-api-key"
   railway variables set ANTHROPIC_API_KEY="你的-anthropic-api-key"
   railway variables set TAVILY_API_KEY="你的-tavily-api-key"
   ```

5. **部署**
   ```bash
   railway up
   ```

## 🐳 本地 Docker 测试

在部署到 Railway 之前，建议先在本地测试 Docker 镜像：

1. **构建镜像**

   ```bash
   docker build -t ckseek-backend .
   ```

2. **运行容器**

   ```bash
   docker run -p 8000:8000 \
     -e OPENAI_API_KEY="你的-openai-api-key" \
     -e ANTHROPIC_API_KEY="你的-anthropic-api-key" \
     -e TAVILY_API_KEY="你的-tavily-api-key" \
     ckseek-backend
   ```

3. **测试 API**
   ```bash
   curl http://localhost:8000/health
   ```

## 🔧 配置文件说明

### Dockerfile

- 基于 Python 3.11-slim 镜像
- 自动安装所有依赖
- 暴露 8000 端口
- 使用 uvicorn 启动 FastAPI 应用

### railway.json

- 配置 Railway 构建和部署选项
- 指定使用 Dockerfile 构建
- 配置自动重启策略

### .dockerignore

- 排除不必要的文件，减小镜像大小
- 排除虚拟环境、缓存、日志等文件

### requirements.txt

- 列出所有 Python 依赖
- Railway 和 Docker 都会使用此文件安装依赖

## 🌐 环境变量配置

必需的环境变量：

| 变量名              | 说明                         | 必需 |
| ------------------- | ---------------------------- | ---- |
| `OPENAI_API_KEY`    | OpenAI API 密钥              | 是   |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥           | 可选 |
| `TAVILY_API_KEY`    | Tavily 搜索 API 密钥         | 可选 |
| `PORT`              | 服务端口（Railway 自动设置） | 否   |

## 📊 部署后验证

部署完成后，访问以下端点验证：

```bash
# 健康检查
curl https://your-app.railway.app/health

# API 文档
https://your-app.railway.app/docs

# Redoc 文档
https://your-app.railway.app/redoc
```

## 🔍 常见问题

### 1. 构建失败

- 检查 Dockerfile 语法
- 确保 requirements.txt 中的依赖版本兼容
- 查看 Railway 构建日志

### 2. 启动失败

- 检查环境变量是否正确设置
- 查看 Railway 部署日志
- 确保端口配置正确

### 3. API 无法访问

- 检查 CORS 配置
- 确保 Railway 服务已启动
- 检查防火墙设置

## 📝 更新部署

### 自动部署

- 推送代码到 GitHub 主分支
- Railway 会自动检测变更并重新部署

### 手动部署

```bash
railway up
```

## 💰 成本优化建议

1. **使用适当的实例大小**

   - Railway 提供多种实例规格
   - 根据实际负载选择合适的配置

2. **配置自动休眠**

   - 低流量时自动休眠节省成本
   - 首次请求时自动唤醒

3. **监控资源使用**
   - 定期检查 CPU 和内存使用情况
   - 优化代码以减少资源消耗

## 🔗 相关链接

- [Railway 官方文档](https://docs.railway.app/)
- [Docker 官方文档](https://docs.docker.com/)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)

## 📞 获取帮助

如果遇到问题：

1. 查看 Railway 部署日志
2. 检查本文档的常见问题部分
3. 访问 Railway 社区论坛
