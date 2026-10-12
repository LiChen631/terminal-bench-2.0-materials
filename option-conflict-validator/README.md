# option-conflict-validator

浏览器扩展样例（Chrome Manifest V3）。用于校验四组多选框之间的互斥关系：当「无」与其它选项
被同时选中时，在页面上标红定位并给出报错提示。

校验的四组多选框：

```text
画内人声 / 唇动方式 / 非语言人声 / 画外声
```

## 目录结构

```text
option-conflict-validator/
├── manifest.json      # MV3 清单，声明 storage 权限与内容脚本注入
├── content.js         # 页面内侦测多选框状态变化，发现冲突时标红并提示
├── content.css        # 冲突态视觉标记
├── popup.html         # 扩展弹窗
├── popup.js           # 弹窗逻辑：当前校验状态与开关
├── popup.css
└── demo/
    └── index.html     # 本地演示页，覆盖「无 + 其他」的冲突组合
```

## 怎么用

不需要 Docker 与 Harbor，在 Chrome 中加载即可：

1. 打开 `chrome://extensions`，开启右上角「开发者模式」；
2. 点「加载已解压的扩展程序」，选择本目录 `option-conflict-validator`；
3. 打开 [`demo/index.html`](demo/index.html) 查看校验效果，或在任意含多选框的页面上试用；
4. 点扩展图标可打开弹窗，查看当前校验状态。

命令行打开演示页：

```powershell
start .\demo\index.html
```

## 用例覆盖

| 场景 | 期望行为 |
| --- | --- |
| 只选「无」 | 无冲突，不标红 |
| 只选非「无」选项 | 无冲突，不标红 |
| 「无」+ 任一其他选项 | 标红冲突项并提示 |
| 多组同时冲突 | 各组分别标红，提示可定位到具体多选框 |
| 撤销选择后 | 冲突标记即时清除 |
