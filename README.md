# Terminal-Bench 2.0 任务样例

本仓库收录两个 **Terminal-Bench 2.0 任务样例**，以及制作、运行和验证任务所需的规则文档、环境搭建指南与参考资料。

两个样例都是完整可运行的任务目录，遵循官方 2.0 目录结构——`task.toml`、`instruction.md`、`environment/`、`solution/`、`tests/`——可直接用 Harbor 评测。

Terminal-Bench 2.0 与传统代码生成数据集不同：模型必须作为 Agent 在真实终端里不断发送 Bash/Zsh 命令、读取输出反馈、迭代修正，直到任务完成。因此一个合格的任务必须具备规格严密、结果确定、可黑盒验证这三个特征。

## 项目要点

- **两个完整任务样例** —— 一个确定性 Python CLI 修复任务，一个浏览器扩展 UI 约束校验任务。
- **完整的 2.0 目录结构** —— 所需文件齐全，`schema_version = "1.1"`。
- **纯黑盒验证** —— 测试只观察外部行为（退出码、输出 JSON、页面状态），绝不读取参考解。
- **确定性设计** —— 不依赖随机数、当前时间、外部网络、私有 API 或登录态。
- **参考资料齐全** —— 附带任务规则、环境搭建指南与工具版本要求，可从零复现。

## 仓库结构

```text
.
├── README.md
├── terminal bench规则文档.md / .pdf    # Terminal-Bench 2.0 规则与验收标准
├── 环境配置指南.md                     # 环境搭建：WSL 2 → Docker → Python → uv → Harbor
├── 3.安装环境工具要求.md                # 所需工具与版本要求
├── 学习资料链接.md                     # 教程与官方文档链接
├── warehouse-transfer-validator/       # 任务样例一：Python CLI 修复任务
└── option-conflict-validator/          # 任务样例二：浏览器扩展
```

## 任务样例

| 任务 | 类型 | 目标文件 | 验证方式 |
| --- | --- | --- | --- |
| [`warehouse-transfer-validator`](warehouse-transfer-validator/) | 确定性 Python CLI 修复 | `/app/warehouse_validator/audit.py` | 12 项黑盒行为测试 |
| [`option-conflict-validator`](option-conflict-validator/) | Chrome MV3 扩展 + UI 约束校验 | `content.js` | `demo/index.html` 交互用例 |

### warehouse-transfer-validator

任务给 Agent 一个存在缺陷的 Python CLI，要求它读取仓库与转账数据、按规格校验并执行转账、写出确定性的 JSON 报告。规格密度较高：标识规范化、两阶段重复项消解、实时库存与容量规则，以及全排序的输出。

```text
warehouse-transfer-validator/
├── task.toml                  # Terminal-Bench 2.0 schema，schema_version = "1.1"
├── instruction.md             # 任务规格（英文）
├── environment/
│   ├── Dockerfile             # python:3.13-slim-bookworm
│   └── app/                   # 交付给 Agent 的缺陷实现
├── solution/                  # Oracle 参考解
└── tests/                     # test.sh（写 reward.txt 与 CTRF）＋ 12 项黑盒测试
```

规格要点：

- **规范化** —— 仓库 ID、SKU、转账 ID 一律 `strip()` 后 `casefold()`，输出必须使用规范化后的标识。
- **重复项消解** —— 有效重复后者胜出；**无效的后者不得遮蔽先前的有效定义**。
- **两阶段处理** —— 先按文件名字典序校验候选，再按时间戳顺序执行选中的转账。
- **执行期拒绝** —— `unknown_source` → `unknown_destination` → `same_warehouse` → `unknown_sku` → `invalid_pack_quantity` → `insufficient_available_stock` → `destination_capacity_exceeded`，被拒绝的转账不产生任何库存副作用。
- **确定性输出** —— 记录按执行顺序、键按字典序排序。

### option-conflict-validator

Chrome Manifest V3 扩展，用于校验四组多选框（画内人声 / 唇动方式 / 非语言人声 / 画外声）之间的互斥关系。当「无」与其它选项被同时选中时，在页面上标红冲突项并报错。附带独立的 `demo/index.html`，覆盖全部冲突组合，无需登录或真实站点即可复现。

## 快速开始

### 1. 先看规则

从 [`terminal bench规则文档.md`](terminal%20bench规则文档.md) 开始，它规定了任务目录结构、`task.toml` 配置要求、测试写法与验收标准。

### 2. 搭建环境

按 [`环境配置指南.md`](环境配置指南.md) 依次安装，工具与版本要求见 [`3.安装环境工具要求.md`](3.安装环境工具要求.md)。装完自检：

```powershell
uv --version
harbor --version
git --version
docker version        # Client 与 Server 都要有输出
python --version
```

### 3. 构建并验证任务

```powershell
cd warehouse-transfer-validator

# 标签必须与 task.toml 中 [environment].docker_image 的值一致
docker build -t generated-terminal-bench-warehouse-transfer-validator:20260710 .\environment\

# Oracle 验证，期望 Trials 1、Exceptions 0、Reward 1.0
$env:PYTHONUTF8 = "1"
harbor run -p . -a oracle
```

结果可在 `jobs/` 下查看：

```powershell
$job = Get-ChildItem ".\jobs" -Directory | Sort-Object Name -Descending | Select-Object -First 1
Get-ChildItem $job.FullName -Recurse -Filter reward.txt | Get-Content   # 应为 1
Get-ChildItem $job.FullName -Recurse -Filter ctrf.json
```

### 4. 运行浏览器扩展样例

不需要 Docker 与 Harbor，步骤见 [`option-conflict-validator/README.md`](option-conflict-validator/README.md)。简要来说：打开 `chrome://extensions`，开启开发者模式，把 `option-conflict-validator/` 作为已解压的扩展加载，然后打开 `demo/index.html`。

### 5. 不用 Harbor 的快速验证

黑盒测试可以直接对任意一份实现运行，只需把 `APP_ROOT` 指向它：

```powershell
$env:APP_ROOT = "$PWD\environment\app"
$env:PYTHONPATH = $env:APP_ROOT
python -m pytest -q .\tests\test_outputs.py
```

`APP_ROOT` 决定测试校验哪份实现，因此同一套测试既能跑交付的缺陷代码，也能跑参考解。

## 难度验证

除 Oracle 验证外，还需要用同一模型、在任务文件不变的前提下独立运行四次：

```powershell
harbor run `
  -p . `
  -a claude-code `
  -m deepseek-v4-pro `
  --ae "ANTHROPIC_AUTH_TOKEN=$env:DEEPSEEK_API_KEY" `
  --ae "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic" `
  --ae "ANTHROPIC_MODEL=deepseek-v4-pro" `
  --n-attempts 4 `
  --n-concurrent 1
```

以 Reward `1` 为成功。按规则：四次中成功 1–2 次为目标难度区间，0 次过难，3 次及以上过易。

## 环境要求

| 组件 | 版本 |
| --- | --- |
| uv | 0.9.5 |
| Harbor | ≥ 0.16.1 |
| Git | ≥ 2.24.0 |
| Docker Desktop | 引擎 29.4.2 |
| Python | 3.12+（任务容器内为 `python:3.13-slim-bookworm`） |

> Harbor 统一使用 `harbor run`。旧写法 `uv run harbor trial start` 已不适用。

## 参考链接

- Terminal-Bench 2.0 任务集 —— <https://github.com/harbor-framework/terminal-bench-2>
- Harbor 框架 —— <https://github.com/harbor-framework>
- Docker 文档 —— <https://docs.docker.com/>
- uv 文档 —— <https://docs.astral.sh/uv/>
- WSL 文档 —— <https://learn.microsoft.com/windows/wsl/>
