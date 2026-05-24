# 📖 Novel Dehydrator · 网文脱水机

**用 AI 把长篇网络小说"脱水"成精华速读版——保留核心剧情、关键角色与伏笔，去掉注水叙述，让你 1/5 的时间读完整本书。**

> 示例：《凡人修仙传》第一章原文约 3200 字 → 脱水后 800 字，压缩比 ~75%，剧情/人物/伏笔完整保留。

---

## 功能特性

- **批量脱水**：上传 TXT / EPUB，自动逐章处理，断点续传
- **可配置压缩**：自定义 Prompt，调节摘要风格和压缩比
- **结构化输出**：每章附带剧情摘要、关键人物、伏笔线索（`---CHAPTER_META---` 分隔）
- **Web 界面**：浏览器操作，实时进度，支持导出完整脱水版
- **并发处理**：可配置并发数，快速处理千章巨作
- **DeepSeek 驱动**：默认调用 DeepSeek API（`deepseek-chat`），兼容 OpenAI 接口格式

## 效果示例

见 [`examples/fanren-xiuxian/`](examples/fanren-xiuxian/)，包含《凡人修仙传》前 5 章的原文与脱水版对比：

| 文件 | 章节 | 原文字数 | 脱水字数 | 压缩比 |
|------|------|----------|----------|--------|
| 1455 | 第一章 山边小村 | ~3200 | ~800 | ~75% |
| 1456 | 第二章 青牛镇 | ~2800 | ~700 | ~75% |
| 1457 | 第三章 七玄门 | ~3100 | ~800 | ~74% |
| 1458 | 第四章 炼骨崖 | ~2900 | ~750 | ~74% |
| 1459 | 第五章 墨大夫 | ~3000 | ~780 | ~74% |

## 快速开始

### 环境要求

- Python 3.10+
- [DeepSeek API Key](https://platform.deepseek.com/)

### 安装

```bash
git clone https://github.com/SilenceX9/novel-dehydrator.git
cd novel-dehydrator

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEHYDRATE_CONCURRENCY=5    # 并发数，建议 1-20
MAX_RETRIES=3
CHUNK_CHAR_LIMIT=12000     # 单次传给 AI 的最大字符数
```

### 启动

```bash
bash run.sh
```

浏览器打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)

### 使用流程

1. 点击「上传书籍」，支持 `.txt`（单文件全书）和 `.epub`
2. 上传后系统自动解析章节结构，预览确认
3. 点击「开始脱水」，实时查看进度
4. 完成后在阅读器浏览，或导出为 TXT 文件

## 项目结构

```
novel-dehydrator/
├── app/
│   ├── api/          # FastAPI 路由（books, jobs, export, prompts, settings…）
│   ├── services/     # 业务逻辑（dehydrator, parser, epub_parser, exporter…）
│   ├── models/       # Pydantic 模型 + DB schema
│   ├── storage/      # 文件系统读写封装
│   ├── config.py     # 配置（从 .env 注入）
│   ├── database.py   # SQLite 连接与初始化
│   └── main.py       # FastAPI 应用入口
├── static/           # CSS
├── templates/        # Jinja2 HTML 模板
├── examples/         # 示例数据（凡人修仙传前 5 章原文 + 脱水版）
├── .env.example      # 环境变量模板
├── requirements.txt
└── run.sh            # 启动脚本
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python · FastAPI · SQLite (aiosqlite) |
| AI | DeepSeek API（兼容 OpenAI 格式） |
| 解析 | ebooklib (EPUB) · 自研 TXT 章节检测 |
| 前端 | 原生 HTML/CSS/JS · SSE 实时推送 |

## 常见问题

**Q: 支持其他 AI 提供商吗？**
A: 支持所有兼容 OpenAI Chat API 格式的服务（如 OpenAI、Qwen、GLM 等），修改 `.env` 中的 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 即可。

**Q: 并发数设多少合适？**
A: 取决于你的 API 速率限制。DeepSeek 免费额度建议设 1-3；付费账号可设 10-20。

**Q: 脱水后内容有遗漏怎么办？**
A: 在设置页面调整 Prompt，要求 AI 保留更多内容，或降低 `CHUNK_CHAR_LIMIT` 减少单次输入量。

**Q: 处理中途断了怎么办？**
A: 直接重新点「开始脱水」，系统会跳过已完成章节，从断点继续。

**感谢Linux Do社区提供的公益服务**

## 许可证

MIT License

---

# 📖 Novel Dehydrator · English

**AI-powered tool that condenses long Chinese web novels into fast-read summaries — preserving key plot, characters, and foreshadowing while stripping filler content. Read the whole book in 1/5 the time.**

## Features

- **Batch processing**: Upload TXT/EPUB, auto-parse chapters, resume-on-failure
- **Configurable compression**: Custom prompts, adjustable summary style
- **Structured output**: Each chapter includes plot summary, key characters, and foreshadowing hints
- **Web UI**: Browser-based, real-time progress, export to TXT
- **Concurrent processing**: Configurable concurrency for fast processing of 1000+ chapter novels
- **DeepSeek powered**: Uses DeepSeek API by default, compatible with any OpenAI-format API

## Quick Start

```bash
git clone https://github.com/SilenceX9/novel-dehydrator.git
cd novel-dehydrator

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # Add your DEEPSEEK_API_KEY
bash run.sh            # Open http://127.0.0.1:8765
```

## License

MIT

**Thanks to Linux Do Community for the public welfare services provided**
