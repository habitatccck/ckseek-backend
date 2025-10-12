# Railway 快速部署指南 🚀

## 最快 3 步部署

### 1️⃣ 推送代码到 GitHub

```bash
git add .
git commit -m "Add Railway deployment config"
git push origin main
```

### 2️⃣ 在 Railway 创建项目

- 访问 [railway.app](https://railway.app/)
- 点击 **"New Project"** → **"Deploy from GitHub repo"**
- 选择你的仓库（ckseek/backend）

### 3️⃣ 配置环境变量

在 Railway 项目设置中添加：

```env
OPENAI_API_KEY=sk-xxx...
ANTHROPIC_API_KEY=sk-ant-xxx...（可选）
TAVILY_API_KEY=tvly-xxx...（可选）
```

✅ **完成！** Railway 会自动检测 Dockerfile 并部署。

---

## 部署后测试

获取 Railway 生成的 URL，然后测试：

```bash
# 健康检查
curl https://your-app.railway.app/health

# 查看 API 文档
# 浏览器访问: https://your-app.railway.app/docs
```

---

## 本地 Docker 测试（可选）

部署前可以先本地测试：

```bash
# 1. 构建镜像
docker build -t ckseek-backend .

# 2. 运行容器
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="你的key" \
  ckseek-backend

# 3. 测试
curl http://localhost:0:8000/health
```

---

## 文件说明

| 文件               | 作用             |
| ------------------ | ---------------- |
| `Dockerfile`       | Docker 构建配置  |
| `railway.json`     | Railway 部署配置 |
| `.dockerignore`    | 排除不需要的文件 |
| `requirements.txt` | Python 依赖列表  |
| `DEPLOYMENT.md`    | 完整部署文档     |

---

## 常见问题

**Q: 部署失败怎么办？**

- 检查 Railway 日志（Deployments → 点击失败的部署 → Logs）
- 确认所有环境变量都已设置

**Q: 如何更新部署？**

- 推送新代码到 GitHub，Railway 会自动重新部署

**Q: 如何查看日志？**

- Railway 控制台 → 你的项目 → Deployments → View Logs

---

## 需要帮助？

查看完整文档：[DEPLOYMENT.md](./DEPLOYMENT.md)
