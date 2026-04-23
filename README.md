# AI玄幻小说编辑器 — 墨笔

## 快速启动

### 1. 创建数据库
```sql
CREATE DATABASE novel_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 后端
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置 Doubao / 火山方舟 Key（标准位置：backend/.env）
cat > .env <<'EOF'
DATABASE_URL=mysql+pymysql://root:@localhost:3306/novel_ai
ARK_API_KEY=your_ark_key_here
STORAGE_PATH=./storage/projects
SECRET_KEY=change_this_in_production_32chars_min
CORS_ORIGINS=http://localhost:5173
EOF

# 启动
uvicorn app.main:app --reload --port 8000
```

也支持从仓库根目录启动，后端会优先读取 `backend/.env`，并兼容根目录 `.env`：
```bash
backend/venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

### 3. 前端
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

---

## 项目结构

```
xs/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI入口
│   │   ├── config.py            # 配置（.env）
│   │   ├── database.py          # SQLAlchemy
│   │   ├── models/              # ORM模型
│   │   ├── schemas/             # Pydantic
│   │   ├── routers/             # API路由
│   │   └── services/
│   │       ├── context_builder.py  # AI上下文构建（核心）
│   │       ├── ai_service.py       # 豆包 / 火山方舟封装
│   │       ├── validator.py        # 细纲人物校验
│   │       └── file_service.py     # 文件系统同步
│   └── storage/projects/        # 小说文件存储
│
└── frontend/
    └── src/
        ├── pages/
        │   ├── OutlinePage.tsx      # 大纲（idea→AI生成→确认）
        │   ├── CharactersPage.tsx   # 角色管理
        │   ├── WorldbuildingPage.tsx # 世界观设定
        │   └── ChapterPage.tsx      # 细纲+正文编辑器
        ├── components/layout/       # 三栏布局
        ├── api/                     # HTTP + AI任务轮询
        ├── store/                   # Zustand状态
        └── styles/                  # 东方风主题
```

## AI上下文策略

每次调用AI时，`context_builder.py` 会自动注入：
- 大纲摘要（前1500字）
- 世界观设定（境界/货币/势力）
- 角色卡（仅本章出场角色的详细信息）
- 近3章剧情缩略（连贯性保障）
- 上一章结尾钩子（衔接）

## 细纲人物校验

保存细纲时，系统自动校验所有出场人物是否在角色库中存在。
未定义的角色会触发422错误，提示先创建角色。

## 创作流程

```
输入Idea → AI生成大纲 → 确认大纲
  ↓
创建角色 → 设计世界观
  ↓
循环（每章）：
  AI生成细纲 → 校验人物 → 确认细纲
    ↓
  AI生成正文（非流式任务）→ 编辑润色 → 完成章节
    ↓
  自动更新主线剧情缩略
```
