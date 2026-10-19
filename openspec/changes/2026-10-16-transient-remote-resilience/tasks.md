# Tasks

作者：elvis。

## 1. Proposal

- [x] 完整阅读用户指定的源码、tests、references、OpenSpec 和 CHANGELOG，核对主工作区既有未跟踪任务提示，建立隔离 worktree。
- [x] 运行基线 make check：42 tests PASS，8文件载荷 PASS；不访问真实远端/state。
- [x] 检索指定离线 Skill 文档；记录官方错误码、cursor输入受理和原生 request retry 契约缺失，不猜参数。
- [x] 对齐 quota 建议：模型派发最多2次与只读预算退避分离；原未批准草案保留，新工作区从 resilience 分支建立。
- [x] 两份 change 严格校验并获得用户对具体合同的批准（本会话“批准”，含统一计划4项精度修订；同步后strict重验通过）。

## 2. Implementation after approval

- [x] 编写docs/superpowers/plans/2026-10-16-resilience-quota.md；独立native实例FULL_PREFLIGHT PASS，保留真实远端未验收边界。
- [x] RED：结构化异常/白名单回执、脱敏、启动失败可重试、timeout/nonzero/受理痕迹不可重发、重试前 verify/idle（子任务初轮RED有22未通过；恢复后保留回归，不重跑整轮派发）。
- [x] GREEN：最小实现异常分类、消息标识、持久化 not_sent/uncertain/accepted；父追加6项RED=4fail+2error，修复后绑定48项通过。
- [x] RED/GREEN：只读reconcile和旧记录；空闲/回显不解锁，裁剪即使有receipt也不推进，原生retry零Orca调用unsupported。
- [x] RED/GREEN：锁外只读/预算/超时/漂移与真实多进程最多一次；其他owner更新不丢失、旧回执不覆盖，send/create不重试。
- [x] RED/GREEN：显式rebind检查和扁平history；真实换绑未执行，开发批准不授权真实调用。
- [x] RED/GREEN：hashed patch及legacy显式兼容、回显/损坏/重复/截断拒绝，既有原字节CLI/Git链路保留。
- [x] RED/GREEN：render和秘密扫描；packet片RED=18fail+7error，修复后28项通过（后续quota扩展为34）。
- [x] 同步SKILL/references/受影响既有文档，决策表在原reference内，8文件清单不变。
- [x] dev2 make check通过76项和8文件载荷；两份strict和diff检查通过。后续quota顺延dev3，阶段证据保存在本会话检查点。
- [x] 旧批准范围独立Implementation Review首轮FAIL（4项确证），新增7项回归并最小修复后复审PASS；独立54+35项和原探针重放通过。此PASS不覆盖后追加的显式create，也不是Final Review。

## 3. Handoff and limits

- [x] dev2已验证产物供quota继续，并在同工作区完成dev3；阶段证据保存于本会话检查点，不提交/安装。
- [x] 原批准本地范围独立Final Review PASS：独立make check89、8payload dev3、两strict/diff、未知send负向probe通过；项目候选证据/边界已核对，非全局或schema6 promotion。
- [x] 2026-10-17交接时已核对：13个已跟踪改动和预期治理文件保留，主工作区材料未覆盖；当时新create明确BLOCKED、未批准/实现/验收，不将旧范围PASS扩大，Git/发布/安装仍待另授权。后续批准记录见第4节。

2026-10-18补充反馈：已读取用户提供的其他窗口截图；该窗口报告Grok Bot云端运行时已连接、就绪，同时明确未创建CC会话或发送消息。此项仅记录用户提供的连接就绪反馈，截图未展示原始runtime回执、所用helper路径/版本或创建/发送过程；不作为本窗口执行结果，也不覆盖CC创建、消息发送、补丁回收或新增explicit-create的验收。仅保留本摘要，截图及其中其他工程的信息不迁入仓库。

真实远端、共享registry、配置变更、add/commit/push/publish/install不在任务清单。未执行项不得勾选为通过。

## 4. Approved explicit-create amendment（本地最多一次提交）

- [x] 复用当前worktree/change，保持dev3；原实现和Review证据仅限原批准范围。
- [x] 官方包静态证据：Mac 1.4.227公开terminal create和精确worktree/command等参数，不支持首次caller-key；未执行Orca/Node或读取配置/共享state。
- [x] 2026-10-18用户批准explicit-create范围，并明确批准将原生caller-key去重改为本地最多一次提交；现行proposal/design/spec已同步，原native-key接口依赖按此批准解除，未声称发现新的native去重能力。
- [x] 本地可行性：重复ensure、回执丢失、真实多进程最多一次三个既有回归3 PASS/0 skip；仅为基础机制证据，不是新create验收。
- [x] 原计划已追加Task 9，实际独立Codex实例`/root/explicit_create_review`的FULL_PREFLIGHT PASS，无阻塞发现；plan SHA256 `caba091ff1ebaf972cd69cbb874c772f10b3628254190550dd1566a9af49e02d`，私有报告SHA256 `e295f75ceefd5669673afbb2df217a06b37f180e99b40e681bc065e956252f35`。独立8项基础回归、两strict、manifest/diff及fsync/晚回执漂移probe通过；root当前实现前make check89 PASS。仅准进入实现，不是新增能力验收或Final Review。
- [x] RED/GREEN：dry-run/ensure零创建/零落盘；实际CLI project/confirm门禁及确认后完整核验绑定。
- [x] RED/GREEN：持久reservation最多一次native提交；保存失败零调用，未启动/未知/损坏回执保留，candidate只读重入核验，旧creating不重置。
- [x] RED/GREEN：live/active/uncertain/不可达/身份漂移拒绝；并发重读、晚回执、其他owner合并、旧history/task去重及累计额度。新增20个测试方法分两轮先RED：首批16项及自审4项；自审曾复现无效intent仍可绑定、畸形/重复清单可误证消失、无效runtime过早reservation、不可达建议缺失，分别修复后绑定74项/packet35项通过。
- [x] 取消ensure首次隐式创建；AGENTS仅新增不自动新建一条，SKILL/原reference及受影响README/troubleshooting同步；CHANGELOG/manifest保持dev3与8文件清单。writing-skills独立消费测试先用旧指引复现“ensure创建，无需用户选择”，更新后由新实例正确选择无confirm预览并等待明确创建选择；未执行建议命令。载荷仅更新本片4项hash，另4项与私有前像一致。
- [x] 实现阶段本地验证：绑定74、packet35、make check109及8payload dev3、两strict与diff检查均通过，无skip/failure/error；不是最终Review或真实远端验收。
- [x] 首轮独立Implementation Review FAIL（报告SHA256 `076533b6104a2f2e71cf57bf6dadcd6b90686a6c45e6b1cfc334ba3e8a9c50e3`）：IR-1旧任务快照损坏可丢失去重、IR-2不完整project仍触发创建、IR-3其他owner的pending candidate占用遗漏。已逐项RED/GREEN补3个方法并修复；当时绑定77项通过，完整验证及同阶段复审另见下一项，不将首轮绿色109项作为缺口通过证据。
- [x] 独立Implementation attempt 2 PASS：三个原finding全部闭环，原独立probe全部重放通过；独立make check112/8payload及两strict/diff通过，无skip/failure/error。报告SHA256 `d5777701b6b14c63341e8b2101c1d420714e902393a71dc390f193c60ba7f248`；control-plane已逐项核对source/evidence哈希，未以模型共识代替验证。
- [x] Project Learning Closeout：高严重性创建证据/旧task/候选占用问题已按design内Candidate Card提升到现有reference与确定性回归；不变量和修复证据随独立实现复审签收，入口已有reference链接，无需新增全局规则或第二套文档。最终验证与单独Final Review仍独立进行。
- [x] 学习签收后新鲜最终验证：绑定77、packet35、make check112/8payload dev3、两strict/diff全部通过，无skip/failure/error；最终证据manifest SHA256 `9d653f52e4b4773f8cfea246b67ef5cadfb6f26c646e172678a4caea1be251b7`。Implementation PASS后产品/载荷零变化，仅阶段治理记录更新。
- [x] 单独Final Review由实际不同实例`/root/explicit_create_final_review`完成PASS；完整14项tracked diff和12项未跟踪治理文件已审读，独立77/35/112、8payload、两strict/diff及两个新增故障交错probe通过，无未解决发现。报告SHA256 `f72b8f6aba52ae52d21e457726df48fa43d9018c917195f15ef1ad6e767bd019`，metadata SHA256 `521d5486b7c37d42a928a20025be32facdf4fb1c10220a666faf5bd6b676bbbc`。
- [x] 绑定Codex control-plane核对Final报告、metadata、全部source/evidence哈希及实际diff后接受本地源码验收；仅核销两份tasks事实，产品/合同不再变更。真实远端、Git、发布/安装未执行；原生request retry仍unsupported、collect延后，不提升为相关能力或E2E通过。

## 5. Workspace preservation and publication boundary

源码验收时，本增量与私有前像对账的10个已跟踪修改为：`AGENTS.md`、`scripts/session_binding.py`、`scripts/tests/test_session_binding.py`、`SKILL.md`、`references/session-binding.md`、`README.md`、`README.en.md`、`docs/troubleshooting.md`、`CHANGELOG.md`、`bundle-manifest.json`。旧成果的`VERSION`、`references/final-patch-prompt.md`、`scripts/task_packet.py`及其`test_task_packet.py`保持接手时字节；其中VERSION继续dev3。原13个已跟踪修改没有丢弃，叠加本轮AGENTS后共14项。

源码验收时未跟踪的`CONTEXT.md`原样保留；原`docs/superpowers/plans/2026-10-16-resilience-quota.md`及本change、quota change继续保存批准、实施与阶段证据，不另建任务账本。所有报告/原像/RED日志在项目外私有目录，源码内只有脱敏摘要与哈希，没有packet/reply/patch、凭据或运行状态。

源码验收阶段未获Git暂存/提交授权，因此先将成果保留在原worktree。2026-10-18用户明确授权“该提交提交”，本阶段将已验收的14项修改和12项治理文件收敛为原分支上的本地提交；实际结果以Git提交记录为准，不包含主工作区的两份既有需求草稿，也不包含项目外私有证据。

上述为源码提交阶段的边界。其后用户明确要求更新共享本地安装，已从固定提交`4e794a211f6c6044170b54d2b7c80ad4b5f0af34`离线同步8文件；active与两入口匹配，112项安装版测试和独立安装验收PASS，报告SHA256 `2878c1e3b7c92c167d4fe5e17c3a5a3d8610131dc57ec939f56e1f9b4faad78a`。旧版备份保留，临时staging已清理，未改入口/registry/原生配置。该次明确本地更新授权不改变默认发布顺序；推送/发布及真实远端E2E仍未执行，两change继续active等待对应阶段授权。

## 6. 2026-10-19 repository-local archive and distillation

Gate 0：本轮为仓库内静态归档/项目学习的 Direct Change，已读 Router、direct-change-rule、project-learning-closeout、learning-candidate-pipeline 和 handoff-new-window；不改变现有两份 OpenSpec 合同，不新增 proposal/实现计划或运行行为。文档编辑风险低，历史 integrity/false-PASS 经验仍保留独立学习与单独 Final Review；本阶段只使用 verification-before-completion 方法，不重做实现 TDD/Preflight。已有归档及本地提交授权内继续校验和审核，无需重复确认，发布等边界保持原状。

- [x] 用户明确要求归档并蒸馏到本仓库。归档为静态会话与接力摘要，未移动OpenSpec change或重写基准spec；原合同/旧Review保持历史。
- [x] 已创建工程不变量、ADR、仓库内会话归档和项目学习卡；AGENTS/双语README提供入口，CONTEXT仅补术语。机制复用既有回归，不新增安装器、状态框架或运行行为。
- [x] 112项现有回归、文档原样校验正反例、51链接/23回归入口及范围/来源/敏感审查通过；独立学习Review PASS后由主控提升3张项目学习卡。Review报告SHA256 `42878bda13fa8d7f8606a09878e49e3c613a43f2256137ab37e91e561cc42b47`，卡片保留来源与实际签收边界。
- [x] 学习提升后的新鲜最终验证通过：112项、两份strict、diff及文档正反例；验证清单SHA256 `48653acc57269e9e8e828562524616ab9922b92baeb6db90d78545cff5fa14ad`。不同实例的单独Final Review PASS、无可操作发现，报告SHA256 `01999a23712b9d2c08208db8c1241d6d70bbb5e7239003a812c41913e43cb196`；主控核对实际文件和证据后签收本地归档/学习范围，10份文档收敛本地提交，实际提交身份以Git记录为准。运行载荷未改，主工作区两份既有草稿保留，未发布/真实远端的边界不变。

详细当前快照、未完成事项负责人和恢复条件见[会话归档](../../../docs/handoffs/2026-10-19-local-closeout.md)。本轮仅本地归档与提交，推送/发布、主分支整合和真实远端任务仍须对应授权。
