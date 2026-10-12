# Terminal-Bench 2.0 规则文档

> 与同目录下的 `terminal bench规则文档.pdf` 内容一致，本文件便于检索与复制。

## 一、数据集介绍

与传统的代码生成数据集（如 HumanEval）或静态问答数据集不同，Terminal-Bench 强调**动态交互**。
模型不能仅仅输出一段代码，而是需要作为一个 Agent，通过不断向终端发送 Bash/Zsh 命令，
观察终端的输出反馈，并根据反馈调整后续操作，直到完成最终任务。

- 任务地址：<https://github.com/harbor-framework/terminal-bench-2>
- ⚠️ **均考虑 2.0 的版本，不考虑 1.0 的版本。**

## 二、数据集格式介绍

每个任务必须是一个独立目录：

```text
<task_slug>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   └── app/
├── solution/
│   └── solve.sh
└── tests/
    ├── test.sh
    └── test_outputs.py
```

规则：

- `task_slug` 使用小写字母、数字和短横线。
- `task.toml` 使用 Terminal-Bench 2.0 schema，`schema_version = "1.1"`。
- `instruction.md` 用英文写清楚输入、输出、格式、排序、错误处理和边界条件。
- `environment/Dockerfile` 的 build context 是 `environment/`。
- `environment/Dockerfile` 不允许 `COPY ../...`。
- `solution/solve.sh` 是 oracle 参考解法，只能修复 `/app` 中的项目文件。
- `tests/test.sh` 必须写 `/logs/verifier/reward.txt`。
- `tests/test_outputs.py` 必须验证行为，不能读取 `solution/solve.sh`、`/app/solve.sh` 或 `solution/` 目录。
- 任务必须可离线运行，不能依赖外部网络、私有 API、登录态或随机结果。

## 三、运行指南

### 1. 进入任务目录，执行 docker build

```bash
docker build environment/Dockerfile -t tag
```

这里的 tag 要和 `task.toml` 中 `[environment]` 的 `docker_image` 的值一致。

例如 `task.toml`：

```toml
[environment]
build_timeout_sec = 600.0
docker_image = "generated-terminal-bench-hard-ledger-reconciliation-engine:20260610"
cpus = 1
memory_mb = 2048
storage_mb = 10240
gpus = 0
allow_internet = true
mcp_servers = []
```

对应构建命令：

```bash
docker build environment/Dockerfile -t generated-terminal-bench-hard-ledger-reconciliation-engine:20260610
```

### 2. Python 环境下安装 harbor（uv、conda 等）

```bash
uv run harbor trial start -p . -a oracle
```

此命令会验证 `solution/solve.sh` 执行以后所有的测试是否通过，
也就是 `/logs/verifier/reward.txt` 是否是 `1`。

### 3. 调用模型执行修复

```bash
uv run harbor trial start \
  -p . \
  -a claude-code \
  -m model \
  --ae ANTHROPIC_API_KEY=你的Key \
  --ae ANTHROPIC_AUTH_TOKEN=你的Key \
  --ae ANTHROPIC_BASE_URL=https://你的BaseUrl \
  --ae ANTHROPIC_MODEL=model
```

此命令会调用模型进行修复，最后在 jobs 文件夹下查看是否 `/logs/verifier/reward.txt` 是 `1`。

## 四、注意事项

### 使用 DeepSeek 等输出为 UTF-8 的模型

找到 harbor 源代码 `harbor/agents/installed/claude_code.py`，找到函数：

```python
def _convert_events_to_trajectory(self, session_dir: Path) -> Trajectory | None:
```

把：

```python
with open(session_file, "r", encoding="gbk", errors="replace") as handle:
```

改为：

```python
with open(session_file, "r", encoding="utf-8", errors="replace") as handle:
```

可以查看报错的日志，如果出现 gbk 报错即可用这个方法解决。

## 五、验收标准

1. **抽检**：采购方随机抽取 200 条数据，供应商提供对应的运行环境和测试用例用于评估，
   每条数据字段符合要求，交付轨迹使用 DeepSeek V4-pro-max 或 Claude-Code Opus4.6/4.7
   模型推理完整慢思考轨迹，难度评分根据数据源正确率统计模型对应采用
   DeepSeek V4-pro-max、Claude-Code Opus4.6/4.7、GLM-5、opus4.5、GPT-5.2、Gemini3-pro
   模型进行慢思考推理，**4 次回复准确率大于 0 小于等于 50%（答对 1–2 次）即为通过**。
   样本整体通过率达到 98%，视为整批次通过。

2. **整体检查**：任务的领域、技能分布涵盖 Terminal Bench 2.0 评测集所涉及领域和技能，
   整体字段格式要求通过率 100% 且任务查重通过比例不低于 98%，视为整批次验收通过。
