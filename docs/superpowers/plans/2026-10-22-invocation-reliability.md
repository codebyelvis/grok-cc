# Invocation Reliability Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the main implementation and bounded parallel file tasks. Steps use checkbox syntax; canonical progress lives in the OpenSpec tasks.

**Goal:** 修复已复现调用卡点，保留安装版兼容能力，完成审核、发布和本地更新。

**Architecture:** 复用两 helper、现有 registry 和测试，不增加框架。绑定与 packet 各由一个有界任务处理；主控维护文档、合并、发布及安装。

**Tech Stack:** Python stdlib、unittest、Git、OpenSpec、既有 skill-installer/rsync。

**Spec:** openspec/specs/invocation-reliability/spec.md；设计及验收记录见 openspec/changes/archive/2026-10-22-improve-invocation-reliability/。

## Global Constraints

- 默认 prompt 120 KiB，传输上限 450 KiB；八文件清单不变。
- 测试仅临时 state/project；外部 Orca 边界为隔离替身；不访问真实 registry/native config。
- 未知 create/send 不重试；receipt/身份漂移保护及两次提交上限不变。
- 用户已授权本轮提交、origin/master 推送与安装；无 force-push、reset/clean。
- strict 完整性证据：独立 Preflight、Implementation Review、Final Review 和安装核验。Review 仅提供证据，主控负责签收。

## Review Focus

- reconcile 只改既有消息 evidence 与改变 attempt_id 的不同分支：同意图合并，异意图拒绝；覆盖默认整任务 reconcile 与 export 回执交错。
- CLI CRLF/bare CR 经过 prepare/render/send 后仍字节一致，不能只测内存 send。
- 进程组内及逃离组的管道持有者：有限返回且不伤调用者或重发。
- Grok 在 foreign native env 下换 UUID：拒绝；旧 codex/claudex key 保持。
- 父目录 alias 指向项目内、已存在 leaf 或解析后 swap：不能覆盖或逃逸。

## Task 1 — Binding reliability

Files: scripts/session_binding.py；scripts/tests/test_session_binding.py。

Consumes: task_packet.validate_prompt_transport(text)，失败抛 ValueError；MAX_SEND_BYTES 为 450*1024。
Produces: 原有 CLI/registry schema 与字段不变。

- [x] 导入安装前像中的身份测试，补 foreign-env Grok 拒绝测试；运行观察 source RED 后移植并最小修复。
- [x] 新增并发 reconcile 先完成/随后 accepted 或 uncertain 回执的真实临时 Registry 回归，包含 main/export 同时观察；确认 RED 后仅容忍既有 task/message 的 evidence 差异，其余全行比较保持。
- [x] 新增 CLI prompt CRLF/bare CR 的真实传参回归；RED 后使用原字节解码和共享传输门禁。
- [x] 新增短超时与继承管道的本地子进程回归；RED 后自有 session/进程组及有限 communicate 回收。
- [x] 执行 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_session_binding.py -v，保留真实 intent 漂移拒绝、未知发送与旧绑定回归。

## Task 2 — Packet transport and format

Files: scripts/task_packet.py；scripts/tests/test_task_packet.py。

Produces: MAX_SEND_BYTES 与 validate_prompt_transport(text)；无新载荷文件。

- [x] 安装版 parent alias 回归先在 source RED，然后移植已审核的 realpath/FD/no-overwrite 路径。
- [x] 准备阶段 reserved marker、NUL、450 KiB 上限与超限零输出回归先 RED，再提供共享传输校验供 render/send。
- [x] 用最小无 Git metadata 的新增文件产物验证 check/Git apply；修订生产 prompt 为正向格式 recipe。窄 parser 不放宽。
- [x] 执行 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_task_packet.py -v。

## Task 3 — Documentation and release candidate

Files: SKILL.md、references/session-binding.md、references/final-patch-prompt.md、README.md、README.en.md、docs/troubleshooting.md、docs/engineering/engineering-invariants.md、VERSION、CHANGELOG.md、bundle-manifest.json、本 change 与本计划。

- [x] 旧 Skill 消费 probe 记录额外 ensure；更新后独立消费 probe 应选择直接 send，同时保留未知状态/新建确认边界。
- [x] 文档合并安装身份说明，明确传输/换行/格式限制与父目录 alias；版本 dev6，仅更新已知载荷 hash。
- [x] make check；openspec validate improve-invocation-reliability --strict；git diff --check；独立完整 diff 与行为探针 Review。
- [x] 修复同范围发现后执行新鲜最终检查，再由不同实例做 Final Review；必要经验落实到既有 invariants/回归。

## Task 4 — Publish and install

Files: 固定提交的八载荷；工程记录仅保留脱敏验收摘要。

- [x] 审核最终 diff/敏感内容及本轮文件清单；中文 Conventional Commits，分组正文。
- [x] 比较 source master、origin/master 和基线，安全 fast-forward/推送；核对远端 SHA 与适用 CI。
- [x] 读取并使用官方 installer 下载固定发布 SHA 到新 staging；make check。
- [x] 再核对安装前像、权限、发现入口和非载荷；rsync 只更新 bundle-files.txt 的八文件，无 --delete。
- [x] 验证安装 hash/入口/非载荷、安装版完整 unittest 与独立验收；保留前像供受控回退。

Stop conditions: 未知安装漂移、真实 registry/native/云端副作用需求、无法合并的他人变更或超出具体修复范围的架构变化。已授权同范围失败继续修复和重验，不请求重复授权。
