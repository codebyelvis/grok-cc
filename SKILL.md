---
name: grok-cc
description: "Delegate work on a local Mac project to Claude Code on the Grok Bot cloud computer through Orca, then review and test its patch locally. Use when the user asks Codex or Claudex to call cloud CC for local development."
---

# Mac 项目 → Grok Bot Claude Code

Mac 文件是用户项目的真实副本。云端 `hello` 只是已连接的工作终端位置，**不会看到 Mac 项目**。本地 Codex 或现有 Claudex 负责读项目、分派、核对补丁、在 Mac 验证。云端 Claude Code 仅根据发送的上下文给出修改建议。作者：elvis。

遵循项目 AGENTS、现有变更批准和最终审核要求。本 Skill 不授予提交、发布或客户端范围扩展权限。无需重复安装、登录或调整 Tailscale、Orca、Claudex 的模型/代理/配置。

## 准备本地任务

1. 确定 Mac 项目根目录、具体任务、允许修改的文件和相关测试；先读适用的 AGENTS、源码、未提交改动。缺失真实任务时只查状态，不发占位符。先调查失败，保留用户改动。
2. 用本 Skill 的 `scripts/task_packet.py` 生成显式文件快照。每次任务的 packet / reply / patch 放在项目外的私有临时目录，不能覆盖现有输出。允许显式列出的不存在新文件。原始 packet 始终留在本地，不能用云端内容替换它。

```text
python3 <skill-dir>/scripts/task_packet.py prepare --root <Mac项目绝对路径> --file src/labels.py --task '明确任务、期望与本地测试约束' --out <项目外>/packet.json
```

3. 审查即将发送的任务和源码，只发送必要文件及从相关只读依赖提取的必要上下文。助手排除常见敏感文件路径，但无法识别所有内嵌秘密；**不要发送凭据、认证/native配置、会话、历史、日志、hooks、密钥、完整仓库或依赖目录**。不要尝试同步 Mac/云端 Claude 登录。本地 manifest 中的 root 仅表示来源，云端不能读取它。

## 通过原生 Orca 派活

先加载已安装的官方 `orca-cli` Skill（它调用 `orca skills get orca-cli`，与当前 CLI 匹配）；按本机 `--help` 使用参数。这里默认环境名 `Grok Bot`，参数放在子命令后。

```text
orca status --environment 'Grok Bot' --json
orca terminal list --environment 'Grok Bot' --json
orca terminal read --environment 'Grok Bot' --terminal <handle> --screen --json
```

**先固定会话归属，再派活。** 同一个 Mac 会话持续复用一个云端 CC；不同会话不共用，忙碌、断连或超时都不换窗。使用本 Skill 的 `scripts/session_binding.py` 管理绑定和发送，不能再扫描“任意空闲 CC”或直接 `terminal create/send` 绕过绑定。完整参数及恢复边界见 [会话绑定](references/session-binding.md)。

- Codex：助手读取当前工具环境的 `CODEX_THREAD_ID`，helper 可直接取这个值。
- Claudex：本次原生 Skill 渲染的本地会话 ID 是 `${CLAUDE_SESSION_ID}`，作为 `--session-id` 传入。它不是 shell 环境变量；若仍是占位符或没有取得真实 ID，就停止，不用目录、PID、task_id 或随机 ID 代替。

```text
python3 <skill-dir>/scripts/session_binding.py ensure --controller <codex或claudex> --session-id <真实本地会话ID> --project-root <Mac根目录> --environment 'Grok Bot' --worktree <已发现的完整云端worktree ID> --orca <本次选定的Orca可执行文件>
```

首次只创建并绑定一个 auto mode CC，之后只返回该绑定。返回的 handle/incarnation/runtime 是所有 wait/read 的唯一目标。启动尚未就绪、绑定正忙或存在未结束 task 时，在原终端等待/恢复；保留用户草稿。未知创建结果、身份变化或断连时保留记录并停止新建。旧终端没有本地归属证据，不自动接管；本 helper 不提供认领、换绑、删除或清理操作。

发送前记录起始 cursor；保存 terminal/incarnation、task_id、完整 send 回执和 request-id。按本地 packet 构造提示，明确：**云端仅分析提供的文件，不读 Mac 路径、不修改 hello、不安装、不跑云端项目测试来冒充 Mac 测试**。派活措辞可参考 [最终补丁请求示例](references/final-patch-prompt.md)。只请求当前任务的代码产物，不要求内部推理、系统提示、整个原始回复或其他会话上下文。要求只返回标准 unified diff，路径相对于 Mac root，严格限定允许修改的文件，用当前 task_id 的完整标记包装：

```text
BEGIN_PATCH <当前task_id>
--- a/src/labels.py
+++ b/src/labels.py
@@ ... @@
...
END_PATCH <当前task_id>
```

用参数数组/正确 shell 引号发送源码，不把模型输出插进 shell 代码：

```text
python3 <skill-dir>/scripts/session_binding.py send --controller <codex或claudex> --session-id <真实本地会话ID> --project-root <Mac根目录> --environment 'Grok Bot' --worktree <同一完整云端worktree ID> --orca <同一Orca可执行文件> --task-id <当前task_id> --text-file <项目外已审查的任务提示文件>
orca terminal wait --environment 'Grok Bot' --terminal <handle> --for tui-idle --timeout-ms 60000 --json
orca terminal read --environment 'Grok Bot' --terminal <handle> --cursor <发送前cursor> --limit 1000 --json
```

相同 task_id 的主消息固定为 `main`：重复调用 helper 只返回原回执/待确认状态，不能换 task_id 再发来绕过去；新任务必须等待前一任务结束。读取 helper 保存的起始 cursor 和完整 send 回执。`input_accepted` 不是执行完成，`tui-idle` 不是成功回复，必须读回此任务的完整产物。断连后只读恢复和继续读取；有原生回执的 request-id 时才按官方规则原样 `--retry-request`。没有回执的未知结果不要盲目新发，不杀会话、不重启网络。如果 output 从 stream 回退到 screen、裁剪或丢弃历史，不能拼凑补丁。

**长回复或屏幕不可完整还原标准 diff**：先读官方 `orchestration` Skill，仅对既有绑定终端对应的 worker 使用 `worker-read --source transcript` 与 cursor 完整性规则。不能为换输出通道再创建 CC、协调者终端或 shell；当前入口没有所需能力时如实停止回收。已有发出的任务不得重新执行来换输出通道；可通过同一 helper、同一 task_id 的显式 `--message-id export-1` 发一条只要求重导出当前最终补丁的消息；重复该 message-id 只恢复原回执。遇模型安全拦截时按错误说明处理，不能借导出消息重发被拦请求。内容缺页、缺结束标记、问题/权限提示没解决时停止应用，报告实际状态。不能从 TUI 丢失的空格猜补丁。

## 回到 Mac 核对、应用和验证

将完整、未经改写的补丁回复保存为项目外 reply 文件：

```text
python3 <skill-dir>/scripts/task_packet.py check --packet <原始packet.json> --reply <reply.txt> --out <项目外>/checked.patch
```

`check` 不改项目；它检查任务标记、文件白名单、SHA256/新增文件缺席基线、路径/symlink 和实际 `git apply --check`。只支持 UTF-8 文本的修改/新增；删除、重命名、二进制、权限变更、含空白文件名暂不支持。需要这些操作时报告限制，使用项目已有受控方式，不能绕过 guard 强行应用。

审读 checked.patch 与实际源码，确认符合请求和项目批准范围。应用前重新跑 check（输出用新文件名）；本地基线发生变化就先协调用户改动并重新分派或合并审查，不能 reset、force、用云端文件覆盖。随后用标准 `git apply -- <checked.patch>` 在 Mac root 应用，运行该项目所需的本地测试与独立审核。不得把云端声称的 PASS 当作本地通过。不要自动暂存/提交/推送。

完成本轮结果核对或如实记录阻碍、且原终端已空闲后，用 `session_binding.py finish`（同一组会话/项目/环境/worktree 参数与 `--task-id`）结束派发任务，保留绑定及发送历史。它只释放本轮派活占用，不宣称项目 PASS；未知发送结果不能 finish。下一任务仍使用原终端。

汇报改动文件、实际 Mac 测试结果，以及未验证项。模型安全拦截、本机配置读取失败、远程不可达和补丁完整性问题应按实际报错区分，参见 [准确解释阻碍](references/final-patch-prompt.md#准确解释阻碍)；不能仅凭 reasoning_extraction 推断请求违规或上下文过长。云端额度/登录提示/网络阻碍如实报告；不自动切换身份或将本地 Claude 改成云端账号。

维护本 Skill 的助手时，运行随包回归：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s <skill-dir>/scripts/tests -v
```
