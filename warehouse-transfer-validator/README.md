# warehouse-transfer-validator

Terminal-Bench 2.0 任务样例。任务是在一个有缺陷的 Python CLI 上做修复：程序需要读取仓库与
转账数据、按规格校验并执行转账、写出确定性的 JSON 报告。

- 待修复文件：`/app/warehouse_validator/audit.py`
- 完整规格：[`instruction.md`](instruction.md)
- 判分：`tests/test_outputs.py` 中的 12 项黑盒行为测试，全部通过则 `/logs/verifier/reward.txt` 为 `1`

## 目录结构

```text
warehouse-transfer-validator/
├── task.toml                  # Terminal-Bench 2.0 schema，schema_version = "1.1"
├── instruction.md             # 任务规格
├── README.md
├── environment/
│   ├── Dockerfile             # python:3.13-slim-bookworm
│   └── app/
│       ├── README.md
│       ├── smoke_check.py     # 允许运行的唯一自检入口
│       └── warehouse_validator/
│           ├── __init__.py
│           └── audit.py       # 待修复的实现
├── solution/
│   ├── solve.sh               # Oracle 入口
│   └── audit.py               # 参考解
└── tests/
    ├── test.sh                # 写 /logs/verifier/reward.txt 与 CTRF
    └── test_outputs.py        # 12 项黑盒行为测试
```

## 怎么用

### 1. 构建镜像

标签必须与 `task.toml` 中 `[environment].docker_image` 的值一致：

```powershell
cd warehouse-transfer-validator
docker build -t generated-terminal-bench-warehouse-transfer-validator:20260710 .\environment\
```

### 2. 跑 Oracle 验证

确认参考解能让全部测试通过：

```powershell
$env:PYTHONUTF8 = "1"
harbor run -p . -a oracle
```

期望结果：Trials 1、Exceptions 0、Reward 1.0、Mean 1.000。

结果可在 `jobs/` 下查看：

```powershell
$job = Get-ChildItem ".\jobs" -Directory | Sort-Object Name -Descending | Select-Object -First 1
Get-ChildItem $job.FullName -Recurse -Filter reward.txt | Get-Content
Get-ChildItem $job.FullName -Recurse -Filter ctrf.json
```

`reward.txt` 应为 `1`，并且存在 `ctrf.json`。

### 3. 接模型做难度验证

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

以 Reward `1` 为成功：成功 1–2 次为难度合格，0 次过难，3 次以上过易。
四次结果与金标轨迹的整理方式见 [`../terminal bench规则文档.md`](../terminal%20bench规则文档.md)。

### 4. 不用 Harbor 的快速检查

只想确认测试集与实现是否匹配时，可以直接本地跑：

```powershell
$env:APP_ROOT = "$PWD\environment\app"
$env:PYTHONPATH = $env:APP_ROOT
python -m pytest -q .\tests\test_outputs.py
```

`APP_ROOT` 指向哪份实现，测试就校验哪份。把它换成已修正的实现即可看到全部通过。

## 规格要点

完整规格见 [`instruction.md`](instruction.md)，核心规则：

- **规范化**：仓库 ID、SKU、转账 ID 一律 `strip()` 后 `casefold()`，输出使用规范化后的标识。
- **重复项消解**：有效重复按规范化 ID 消解，后者胜出；无效的后者不得遮蔽先前的有效定义。
- **两阶段处理**：先按文件名字典序 + 文件内顺序校验候选，再按
  `(timestamp, 源文件名, 原始序号)` 的时间序执行。
- **执行期拒绝原因**（按优先级，命中即拒绝且不产生任何库存副作用）：
  `unknown_source` → `unknown_destination` → `same_warehouse` → `unknown_sku` →
  `invalid_pack_quantity` → `insufficient_available_stock` → `destination_capacity_exceeded`。
- **实时状态**：目的地容量按全 SKU 实时 `on_hand` 合计判断；目的地缺少该 SKU 时以源条目的
  `pack_size` 创建后再入账。
- **确定性输出**：`accepted` / `rejected` 按执行顺序；`inventory` 与 `summary.total_moved`
  的键按字典序；`warnings` 按 `(code, transfer_id or "", detail)` 排序。
