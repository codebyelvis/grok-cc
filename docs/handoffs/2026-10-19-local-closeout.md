# grok-cc 本地源码与安装会话归档

作者：elvis。归档日期：2026-10-19。本文是静态会话摘要和续接入口，不是聊天转储、第二个进度账本或新的授权合同。

## 使用方式

先读 `/Users/elvis/file/develop/opensource/grok-cc/.claude/worktrees/quota-saving-a8e9002d/docs/handoffs/2026-10-19-local-closeout.md`，核对现状后继续已授权待办，不重复已完成事项。

归档位于本地仓库的原任务 worktree；不声称已合并到主工作区。未来若路径迁移，先按 Git 和用户指定位置核对，不能另建干净 worktree 冒充继承了旧成果。

## 已核实的三个位置

| 对象 | 本轮观察 | 解释 |
| --- | --- | --- |
| 主工作区 | `/Users/elvis/file/develop/opensource/grok-cc`，master 为 `350ec30` | 没有合并本轮功能；两份既有需求草稿保留 |
| 功能源码 | `.claude/worktrees/quota-saving-a8e9002d`，分支 `worktree-quota-saving-a8e9002d`，功能基线 `4e794a211f6c6044170b54d2b7c80ad4b5f0af34` | 已本地提交，后续文档归档提交以实际 Git log 为准，不能把短版本号当提交身份 |
| 共享安装 | `~/.agents/skills/grok-cc`，8 文件与功能基线一致，版本 dev3 | Codex 的 `~/.codex-account-a/skills/grok-cc` 和 Claude 的 `~/.claude/skills/grok-cc` 均链接至此 |

本地提交、主分支、远端发布、共享安装、原生窗口规则消费是不同状态。当前没有本轮推送/发布或真实云端 E2E 证据；旧窗口使用前须重新读取已安装 Skill，不因文件更新就宣称规则已热重载。

## 已完成，不重做

- 原 resilience/quota、原字节补丁完整性、预算/秘密/媒体门禁和任务累计两次保护已实现；基线 42，经旧范围 89，新增显式创建 23 项达到 112。
- 用户批准把缺失的原生 caller-key 要求改为本地最多一次提交；显式创建、ensure 去自动创建、reservation/candidate、旧任务和其他 owner 占用保护已完成。
- 新增实现的独立审核曾发现 IR-1 旧快照丢任务、IR-2 不完整 selector 触发创建、IR-3 忽略其他 owner pending candidate；逐项 RED/GREEN 后复审 PASS，单独 Final PASS。不能只引用首次绿色 109 项跳过这三项反例。
- 用户另行批准本地提交，26 个文件已提交为功能基线；又明确要求更新本地共享安装，本轮据此从固定本地提交离线同步 8 个载荷。该次授权没有修改默认发布顺序或授权推送。
- staging、实际安装路径均通过 112 项测试；独立安装就绪及安装验收 PASS，两入口实际路径 probe 均证明无绑定 ensure 零状态/零 Orca 调用。临时 staging 已清理，旧版保留供受控回退。

## 权威材料与入口

当前合同/任务进度仍在两个 active change 的 [resilience tasks](../../openspec/changes/2026-10-16-transient-remote-resilience/tasks.md) 和 [quota tasks](../../openspec/changes/2026-10-16-quota-saving/tasks.md)，执行计划仍是[原计划](../superpowers/plans/2026-10-16-resilience-quota.md)。本页不复制可变合同。两 change 因发布生命周期未完保留 active；本次归档的是会话与经验，没有移动 OpenSpec 或改写基准 spec。

已批准决策见 [ADR 0001](../adr/0001-local-at-most-once-create.md)；可复用机制和回归见[工程不变量](../engineering/engineering-invariants.md)；项目学习来源见[学习卡](../learning-candidates/2026-10-19-local-closeout.md)。接收端只读这些和当前适用规则，再决定下一步，不先加载整套实现流程。

| 所需 Skill | 当前用途 | 本窗口已读取的入口 | 接收端状态 |
| --- | --- | --- | --- |
| openspec-superpower-change | 续接的范围、授权与完成判断 | `~/.agents/skills/openspec-superpower-change/SKILL.md` | 在接收端按实际 runtime 发现并读取，不继承本窗口发现结论 |
| handoff-new-window | 冷启动核对，避免重复 | `~/.agents/skills/handoff-new-window/SKILL.md` | 同上；本页不授新角色 |

接收端可以是用户指定的 Codex 或 Claude；新的原生实例须自行核对身份，不能复用历史 session ID、Reviewer task 名或本窗口的 control-plane 权限。历史 Review 是证据，不能让新接收端自评 PASS。仅维护源码文档时不运行 `$grok-cc`、真实 Orca 或云端派发。

## 证据摘要与回退位置

以下 SHA256 为本轮已实际读取的项目外报告指纹；摘要不等于原始报告仍可访问，也不是下轮的新鲜测试结果。

| 阶段 | 结果/范围 | 报告 SHA256 |
| --- | --- | --- |
| 显式创建 Full Preflight | PASS，仅允许进入实现 | `e295f75ceefd5669673afbb2df217a06b37f180e99b40e681bc065e956252f35` |
| Implementation attempt 2 | PASS，IR-1/2/3 闭环 | `d5777701b6b14c63341e8b2101c1d420714e902393a71dc390f193c60ba7f248` |
| 单独 Final Review | PASS，本地源码，112 项及独立故障交错 probe | `f72b8f6aba52ae52d21e457726df48fa43d9018c917195f15ef1ad6e767bd019` |
| 安装就绪 | PASS，固定来源/前像/命令范围 | `f6a806e14f7abf71e4d5d2efce56ea290099d218aef35e34418b0c85f80b2fd2` |
| 独立安装验收 | PASS，active 112 项、两入口 probe | `2878c1e3b7c92c167d4fe5e17c3a5a3d8610131dc57ec939f56e1f9b4faad78a` |

安装和回退记录位于本机 `~/.local/share/grok-cc-install-backups/20261018-234935-4e794a2/`：`install-result.json` SHA256 为 `8148a4db4b412b2aad41067bc225dc31ace588f6cc532426ed009626e28154ac`，`before/` 保存旧 8 文件。回退必须先核对当前仍为这次安装，拒绝后续漂移，只恢复这 8 文件并保留链接/registry/原生配置。原始源码 Review/RED 日志仍在项目外；不搬入本仓库，不声称读取了缺失文件。

## 未完成事项与唯一下一步

本地实现和本地安装无阻塞项。下一窗口先核对 Git、入口和 8 文件 hash；随后只推进用户实际授权的待办。没有新待办时停止，不重跑已完成云端任务或重复开发。

| 待办 | 负责人/恢复条件 |
| --- | --- |
| 主分支整合、推送/发布、对应远端 CI | 用户决定；取得该阶段授权并核对实际范围、remote 和 revision 后执行 |
| 真实远端恢复/业务 E2E | 用户给出仍需执行的真实任务与有效授权，沿真实 owner 的固定绑定取证；截图仅能说明当时被展示的状态 |
| 原生 request retry | 等待版本匹配的正式公共契约；当前在任何 Orca 调用前 unsupported，不猜参数 |
| collect | 本轮延后；另行明确范围和验收，不以 screen 或裁剪内容冒充完整产物 |

真实 Orca（包括 help/version）、共享 `~/.local/state/grok-cc`、原生配置/凭据、网络/模型/代理修改仍不在源码续接授权内。不自动换绑、不清理 registry、不覆盖主工作区草稿。该目录两份草稿为 `docs/review:requirement/grok-cc-local-optimize.md` 与 `docs/review:requirement/grok-cc-optimize-prompt.md`，由所属任务后续处理。

## 必要复核与已踩坑

源码或测试变化时运行 `make check`、两 change 的 `openspec validate <change-id> --strict` 和 `git diff --check`；仅文档变化按影响验证链接、状态、术语和所引用回归。真实远端、旧窗口规则消费及新修改不能用本轮历史 PASS 代替。

- 旧外部交接快照中“caller-key 仍 BLOCKED/ensure 仍自动创建”的状态早于用户批准及功能提交；不要把它当当前阻塞，也不要仅凭文档日期认定新的授权。
- 官方 1.4.227 的公开路径静态核验已经完成；内部 schema 不是公共 CLI，缺新证据时不要再泛搜同版本或换入口绕过。
- 测试路径先 resolve：Mac 的 `/var` 别名会触发 no-follow 保护；路径准备错误不应被误当产品故障或计入有效 probe。
- Shell 多行正文使用文件/结构化参数，不把 JSON 转义当 shell 引号；zsh 不用保留变量 status 承接 exit code。
- 运行时已连接、input_accepted、tui-idle、完整 hash、单测和独立意见一致分别只证明各自事实；任何一个都不能单独升级为项目/E2E PASS。

归档未启动服务或访问真实远端，不判断其他窗口服务状态。启动指令：先读本文件，按当前合同继续已授权待办，不重复已完成事项。
