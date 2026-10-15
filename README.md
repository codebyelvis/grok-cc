# grok-cc

[简体中文](README.md) | [English](README.en.md)

作者：elvis。当前版本：`0.1.0.dev1`，开发版本，尚无正式 release。

在 Mac 上读取项目，将必要源码交给 Grok Bot 云电脑里的 Claude Code，通过 Orca 回收补丁，再在 Mac 校验、应用和测试。

![grok-cc：Mac 本地任务经 Orca 派发给云端 Claude Code，完整补丁回到 Mac 验证](docs/assets/architecture.svg)

[查看 SVG](docs/assets/architecture.svg) · [下载后在浏览器打开单文件 HTML](docs/architecture.html)。图示描述工作流程，不代表服务实时在线。

Mac 项目是源码真值。云端终端目录不等于 Mac 项目，也不会自动挂载 Mac 文件。本工程不转发 Claude API、不共享登录，也不配置代理、Tailscale 或模型。

## 使用条件

- Mac 本地已能使用 Codex，或用户已有的 Claudex；本项目不要求另行在 Mac 登录 Claude。
- 云电脑上的 Claude Code 已登录，Orca runtime 已配对且可达。
- 使用目标环境的 Orca CLI；先加载它提供的 `orca-cli` guide，不从示例猜命令。
- Python 3.11 及以上、Git；开发检查还需要 Make。helper 仅依赖 Python 标准库，使用 POSIX 文件锁与目录描述符，支持目标为 macOS/Linux，不支持 Windows 原生 Python。

Python 版本兼容矩阵由 CI 配置定义；配置存在不代表远端 CI 已运行。网络连通、模型登录、额度及外部项目测试也不由本仓库单测证明。

## 使用

安装到对应 Skill 入口后，在实际本地会话中调用：

```text
Codex：$grok-cc 修复当前项目中某个明确问题，并在 Mac 验证
Claudex：/grok-cc 修复当前项目中某个明确问题，并在 Mac 验证
```

任务需要明确修改范围和验收条件。助手按照 [SKILL.md](SKILL.md) 操作，不能把示例占位任务直接派发。

- 同一真实 Mac 会话固定一个云端 CC；不同会话不共用。
- busy、offline、身份变化或未知发送结果时保留原绑定，不换窗、不盲目重发。
- 同一 task/message/文本重复调用只恢复原回执；换 ID 不能作为重复派发的办法。
- 保留输入草稿；只在首次任务前识别已核实的精确启动提示，不匹配任意 `Try` 文本。
- 收到完整任务标记、通过原 packet 白名单/基线/路径检查后才可应用。`input_accepted`、`tui-idle` 或截图不等于产物通过。
- `finish` 释放派活占用并保留绑定，返回 `project_pass=false`，不代表项目验收成功。

详细规则：[会话绑定](references/session-binding.md)、[最终补丁请求与阻碍分类](references/final-patch-prompt.md)。

## 工程结构

```text
SKILL.md                       Skill 入口
agents/openai.yaml             Codex 展示信息
references/                    绑定与最终补丁规则
scripts/session_binding.py     归属、锁、去重与发送保护
scripts/task_packet.py         显式快照与只读补丁检查
scripts/tests/                 随包回归
bundle-files.txt               安装载荷的唯一文件清单
bundle-manifest.json           当前版本与载荷 SHA256
docs/installation.md           分阶段安装、校验与回退
docs/troubleshooting.md        已知故障机制与能力边界
docs/architecture.html         单文件终端蓝图（内联 SVG，无外部依赖）
docs/assets/architecture.svg   README 流程图
```

本次将原来安装目录中的 8 个载荷文件按原字节建立源码基线。仓库工程文件不属于安装载荷；私有运行状态始终留在仓库之外。

## 维护和验证

在本仓库根目录运行：

```sh
make check
```

该命令核对 8 文件清单及 SHA256、运行 helper 的无副作用帮助入口，再执行随包完整回归。检查不调用云端 Orca、模型或共享 registry。测试使用真实临时文件、锁和 Git；仅 Orca 外部边界用受控替身，不构成真实云端端到端验收。

也可分别运行：

```sh
make verify-payload
make smoke
make test
```

修改载荷后，先完成该行为所需的测试与独立审核，再有意识地更新 `bundle-manifest.json` 的受影响项和版本；不能通过重算所有哈希掩盖未知文件变化。行为、身份、安全或生命周期改变需先按适用变更规则明确范围，不能把工程整理当成批准。

GitHub CI 在 macOS/Linux、Python 3.11/3.13 上运行同一检查，不使用云端凭据，不自动发布或安装。Action 固定到已核实的上游提交；依赖说明见 [来源说明](PROVENANCE.md)。

## 发布与本地安装

本地 source repo、[GitHub 仓库](https://github.com/codebyelvis/grok-cc) 和 active Skill 安装是三个不同状态。源码发布后，以已审核的实际 Git 提交为安装来源，分别核验推送结果和本地安装；不会因工程准备完成就自动更新所有窗口。

[安装说明](docs/installation.md) 复用已有 `skill-installer` 的隔离 staging 能力，不新增安装器。必须先核对实际远程 revision、安装前像与并发漂移，再按授权同步固定载荷，保留已有入口链接和运行状态。仓库没有自动更新、重绑或清理命令。

## 许可

目前保留全部权利，见 [LICENSE](LICENSE) 和 [来源说明](PROVENANCE.md)。工程放在源码目录不代表已取得公开分发授权；正式发布前由作者确定许可证。
