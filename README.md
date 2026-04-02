# 十字路口 · 法务助手

合同自动盖章工具。上传 Word/PDF 合同和印章图片，自动识别盖章位置、生成骑缝章、模拟扫描效果，输出成品 PDF。

## 功能

- **Word/PDF 上传** — 支持 `.docx`、`.doc`、`.pdf`，Word 文件自动转 PDF（自动接受修订，输出最终版）
- **自动识别盖章位置** — 搜索"甲方（盖章）"/"乙方（盖章）"等关键词，自动定位；未识别时支持手动点击指定
- **甲方/乙方切换** — 一键切换识别甲方或乙方盖章位置
- **骑缝章** — 按页数自动切割印章，每页右边缘放置，带随机偏移和旋转模拟手工效果
- **模拟扫描效果** — 可调节强度（轻度/中度/重度），包含亮度偏移、传感器噪点、页面倾斜、文字柔化、边缘阴影、四角暗角等真实扫描特征
- **管理后台** — 用户管理（增删用户、角色控制）、印章管理（上传印章 PNG + 公司主体名称）
- **处理记录** — 页面内查看历史处理记录，支持重新下载
- **完成动画** — 处理完成后播放烟花庆祝动画
- **RESTful API** — 所有功能可通过 API 调用，支持 MCP/Skill 集成

## 技术栈

- **后端**: Python 3.11 + FastAPI + PyMuPDF + Pillow + NumPy
- **前端**: Vanilla HTML/CSS/JS + PDF.js
- **文档转换**: LibreOffice (headless) + python-docx
- **部署**: Docker + Railway

## 快速开始

### 本地运行

```bash
# 1. 安装 Python 3.11 和 LibreOffice
brew install python@3.11
brew install --cask libreoffice

# 2. 创建虚拟环境并安装依赖
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 打开浏览器
# http://localhost:8000
# 默认管理员: admin / admin123
```

### Docker 运行

```bash
docker build -t contract-stamper .
docker run -p 8000:8000 \
  -e ADMIN_PASSWORD=your_admin_password \
  -e API_KEY=your_api_key \
  contract-stamper
```

### Railway 部署

1. Fork 本仓库
2. 在 Railway 创建新项目，连接 GitHub 仓库
3. 设置环境变量：
   - `ADMIN_PASSWORD` — 管理员密码
   - `API_KEY` — API 访问密钥
   - `PORT` — 端口（Railway 自动设置）

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_PASSWORD` | `admin123` | 管理员账户密码 |
| `API_KEY` | `dev-key` | API Bearer Token |
| `PORT` | `8000` | 服务端口 |
| `UPLOAD_DIR` | `/tmp/contract-stamper` | 文件存储目录 |

## 项目结构

```
contract-stamper/
├── app/
│   ├── main.py              # FastAPI 入口，路由挂载，认证端点
│   ├── config.py             # 环境变量配置
│   ├── auth.py               # 多用户认证系统（token + API Key）
│   ├── api/
│   │   ├── upload.py         # 文件上传（PDF/Word），Word→PDF 转换
│   │   ├── detect.py         # 关键词自动识别盖章位置
│   │   ├── stamp.py          # 异步盖章处理（乙方章 + 骑缝章 + 扫描效果）
│   │   ├── result.py         # 处理结果查询与下载
│   │   └── admin.py          # 管理后台 API（用户/印章管理）
│   ├── core/
│   │   ├── pdf_processor.py  # PDF 读取、渲染预览图
│   │   ├── stamp_placer.py   # 关键词检测 + 印章叠加
│   │   ├── seam_stamp.py     # 骑缝章切割与放置
│   │   └── scan_effect.py    # 模拟扫描效果（7 种效果叠加）
│   ├── static/
│   │   ├── logo.png          # 十字路口 Logo
│   │   ├── stamps/           # 预置印章目录（管理后台上传）
│   │   ├── css/style.css     # 有机绿主题样式
│   │   └── js/
│   │       ├── app.js        # 主页面交互逻辑
│   │       └── admin.js      # 管理后台交互逻辑
│   └── templates/
│       ├── index.html        # 主页面
│       └── admin.html        # 管理后台页面
├── tests/                    # 测试文件
├── Dockerfile                # Docker 构建配置
├── railway.toml              # Railway 部署配置
├── requirements.txt          # Python 依赖
└── .env.example              # 环境变量示例
```

## API 接口

Base URL: `/api/v1`，需要 `Authorization: Bearer <API_KEY>` 认证。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传合同文件（PDF/Word） |
| POST | `/upload/stamp` | 上传印章 PNG |
| POST | `/detect` | 自动识别盖章位置 |
| POST | `/stamp` | 执行盖章处理（异步） |
| GET | `/result/{task_id}` | 查询处理状态 |
| GET | `/download/{task_id}` | 下载处理结果 |
| GET | `/stamps/list` | 获取预置印章列表 |
| POST | `/login` | 用户登录 |
| GET | `/me` | 获取当前用户信息 |

### API 调用示例

```bash
# 上传合同
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer dev-key" \
  -F "file=@contract.docx"

# 识别盖章位置
curl -X POST http://localhost:8000/api/v1/detect \
  -H "Authorization: Bearer dev-key" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "party": "乙方"}'

# 执行盖章
curl -X POST http://localhost:8000/api/v1/stamp \
  -H "Authorization: Bearer dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "abc123",
    "stamp_id": "stamp456",
    "party_b_position": {"page": 4, "x": 400, "y": 650},
    "riding_seam": true,
    "scan_effect": 50,
    "original_filename": "合同.docx"
  }'

# 查询状态
curl http://localhost:8000/api/v1/result/task789 \
  -H "Authorization: Bearer dev-key"

# 下载结果
curl -O http://localhost:8000/api/v1/download/task789 \
  -H "Authorization: Bearer dev-key"
```

## 扫描效果参数

滑块 0-100，数值越低效果越重：

| 参数 | 高质量 (80-100) | 中等 (40-80) | 低质量 (0-40) |
|------|----------------|-------------|--------------|
| 页面倾斜 | 0-0.8° | 0.8-1.5° | 1.5-2.5° |
| 传感器噪点 | 极少 | 少量 | 明显 |
| 亮度偏移 | 微弱 | 轻微 | 明显 |
| 文字柔化 | 极轻 | 轻微 | 明显 |
| 边缘阴影 | 微弱 | 轻微 | 明显 |
| 四角暗角 | 微弱 | 中等 | 明显 |

## License

MIT
