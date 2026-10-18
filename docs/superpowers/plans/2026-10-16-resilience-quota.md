# grok-cc 韧性与省额度执行计划

作者：elvis。

> 当前增量由Codex在本会话内执行，使用`superpowers:executing-plans`的Router-governed变体；任务进度只记现有OpenSpec tasks。Git写入/提交步骤已按用户授权边界移除。

**Goal:** 在既有韧性/quota实现上增加显式create，保留同一受管registry下每intent最多一次native创建调用。

**Architecture:** 复用Registry的FD/no-follow、flock、fsync/replace及原terminal调用边界；增加只读快照、创建reservation/candidate与核验后绑定，不新增调度或运行状态框架。

**Tech Stack:** Python标准库、现有unittest/隔离Orca fixture、OpenSpec及Makefile。

**Spec:** `openspec/changes/2026-10-16-transient-remote-resilience/specs/explicit-terminal-create/spec.md`及同change proposal/design；quota change继续作为依赖。

## Approval and scope

用户在本会话明确回复“批准”，ExitPlanMode确认通过。合同为2026-10-16-transient-remote-resilience与2026-10-16-quota-saving，加`/Users/elvis/.claude/plans/typed-singing-crayon.md`列明的4项修订。批准后先同步OpenSpec并重验，再独立Preflight，不在未通过时实施。

Worktree `.claude/worktrees/quota-saving-a8e9002d`，branch `worktree-quota-saving-a8e9002d`，base `350ec30d2890deff7ce591f15c497e4b019b1f7f`。主工作区既有未跟踪任务提示和旧resilience草案保留。不运行真实Orca、不触碰共享state/云端/配置/安装，不add/commit/push/publish。仅既有两个helper/tests、SKILL、两个references、版本/manifest/CHANGELOG、受影响双语README/troubleshooting和本轮治理文件可改。

风险strict；本地真实文件/锁/Git验证，不把remote fixture当真实云端验收。一次最多一个模型子任务。原生retry在任何Orca调用前unsupported；远端错误字符串/marker/idle不能证明未送达；collect延后。最终交付必须明确这些未完成原始需求。

## Contract corrections

- task累计模型提交最多2次，main/合法export共用；同message重试只准明确not_sent且同文，未知状态不重发。
- retry-request在任何远端调用前阻断。
- 正预算为整条命令共享deadline；0关闭重试但每个必要查询有有限timeout。
- 媒体扫描只承诺magic/data URL/有限解码后magic等可验证识别，不声称万能检测。

## Implementation sequence

1. 同步上述已批准修订到两份OpenSpec，记录批准，strict验证；独立Preflight审查本计划及实际源码，检查验收、允许文件、命令和停止条件。规划advisory不算PASS。
2. 先在`test_session_binding.py`添加RED，覆盖NativeOrca的launch/nonzero/timeout/invalid result、白名单receipt与脱敏、retry-request零调用；最小修复生产边界。
3. RED锁外退避/共享deadline/0预算/60秒send timeout、并发重载/其他owner不丢失/旧回执不能覆写、未知create/send不重试；保留真实多进程最多一次测试。复用Registry的FD/no-follow/flock/fsync/replace，不引入运行状态框架。
4. RED/GREEN同ID同文not_sent显式重试、稳定marker、reconcile只读且回显/空闲不可解锁、已保存有效receipt恢复、显式rebind检查及history保留。原生request retry不伪造实现。
5. RED/GREEN hashed patch、回显模板、损坏/重复/截断、legacy显式兼容、原始CR/CRLF/Unicode字节链路；复用diff_paths/verify_baseline/git apply检查。CLI packet显式UTF-8，reply保留原字节。
6. RED/GREEN render内容脱敏/输出边界、secret正例与前缀/正则源码负例；复用read_selected/write_external_output。准备dev2文档/manifest并执行本片检查。
7. quota片RED/GREEN prepare/render共享字节预算与UTF-8阈值、真实短回复约束、task累计attempts/合法export/第三次拒绝、summary显式证据与<=15行、安全输出、媒体后缀override不允许真实binary/已识别编码媒体。
8. 同步决策表和Skill，版本dev3及本片已审查hash。独立实现Review实际diff/调用链/关键重跑及负向探针；所有可操作发现修复→验证→复审。随后新鲜最终验证、独立最终Review和状态核对，交付但不发布。

## Verification commands

所有命令从当前worktree运行。RED先跑对应focused case，GREEN跑本组；dev2和dev3各跑完整必要检查。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_session_binding.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_task_packet.py -v
make check
OPENSPEC_TELEMETRY=0 openspec validate 2026-10-16-transient-remote-resilience --strict
OPENSPEC_TELEMETRY=0 openspec validate 2026-10-16-quota-saving --strict
git diff --check
```

先验证原8文件载荷未发生未知漂移，再只更新本轮明确修改项。失败证据及摘要保留在会话私有检查点，非源码日志不入库。任务进度仅由OpenSpec tasks记录，执行步骤不充当另一本状态账本。

## Stop and rollback

权限拒绝不换shell/agent绕过；未知源码或manifest漂移不重算掩盖；关键测试/Review失败不签收。所有回滚仅针对本worktree本轮已知改动人工反向补丁，不reset/clean，不覆盖既有用户文件。CodeIsland诊断与产品修改分离，不修改其hook/settings；已批准范围不自动授予真实运行、Git或发布权限。

## 2026-10-18 explicit-create增量（已批准，新Full Preflight后执行）

用户明确批准将原生caller-key去重改为本地最多一次提交。此节替代旧create接口阻塞；原1–8步骤和已通过的旧Review保持历史，不重做。spec SHA256为`52b3a9098c56c02596f5457f05ba69f67834aa9fa203d3f75ff3620e1a854c1d`。

本轮control-plane/local executor绑定为product `codex`、instance `01a148d8-05d8-7722-a00c-641f2fba68a6`、role `control-plane`、profile `control-plane-high`，合同为本计划引用的现行OpenSpec。实例来自当前原生CODEX_THREAD_ID，不继承发送端身份。独立Preflight/Implementation Reviewer为实际另一个Codex实例、independent-reviewer/control-plane-high，Review purpose为审核本增量是否可执行/符合批准合同，结果权限仅governed-review-evidence；Final Reviewer必须另一个独立实例并与执行者及Implementation Reviewer均不同。具体实际实例在派发后记入本节，不预填PASS。

已实际派发的Preflight/Implementation Reviewer绑定：agent_product=`codex`，agent_instance_id=`/root/explicit_create_review`（原生collaboration返回的独立任务实例），agent_role=`independent-reviewer`，capability_profile=`control-plane-high`；review_purpose.object=`本change的explicit-create本地最多一次提交增量`，review_purpose.decision=`FULL_PREFLIGHT是否可执行及后续Implementation是否符合合同`；independence_requirement.mode=`distinct-contract-instance`，独立于上述control-plane/local executor；result_authority=`governed-review-evidence`。此绑定不代替实际Review结果，Final Reviewer于该阶段实际派发后另行绑定。

2026-10-18已由collaboration创建Final Reviewer实际实例`/root/explicit_create_final_review`：agent_product=`codex`，agent_role=`independent-reviewer`，capability_profile=`control-plane-high`；review_purpose.object=`本增量完整源码、合同、项目学习与最终证据`，review_purpose.decision=`本地源码最终验收是否就绪，不含发布/安装/真实远端`；independence_requirement.mode=`distinct-contract-instance`，独立于control-plane/local executor及`/root/explicit_create_review`；result_authority=`governed-review-evidence`。此行仅记实际最终阶段绑定，不改变已批准设计、范围和验证命令；Full Preflight及Implementation报告所绑定的原plan SHA256 `caba091ff1ebaf972cd69cbb874c772f10b3628254190550dd1566a9af49e02d`保留为历史，最终验证/Review绑定加入此行的现行plan，不以实例创建代替Review结果。

### Global constraints and Review focus

- 仅原允许产品文件及AGENTS的一条不自动新建不变量；VERSION保持0.1.0.dev3，bundle-files/Makefile/CI/安装器不改。原计划“不改AGENTS”仅对旧范围有效。
- 不执行真实orca（含help/version）、不读共享registry/native配置、不网络/云端/安装/Git写入；测试只用临时state/project和fixture executable。
- 五项重点风险：dry-run/ensure无绑定时不得建立目录/lock；进程中断或回执丢失不得重提；legacy creating/畸形candidate不得升级重置；替代创建不得重放归档task/重置额度；锁外等待时其他owner更新及同owner漂移不得丢失。
- 本地最多一次只覆盖保留同一受管registry的helper，不宣传原生去重；完全丢失回执保持create_unverified。原retry-request unsupported、collect延后及真实远端未验收边界继续保持。

### Task 9: 显式创建完整业务片

**Files:** `scripts/session_binding.py`、`scripts/tests/test_session_binding.py`；同步`AGENTS.md`一条、`SKILL.md`、`references/session-binding.md`、受影响`README.md`/`README.en.md`/`docs/troubleshooting.md`、`CHANGELOG.md`/`bundle-manifest.json`；其余产品文件应保留当前hash。治理仅现有plan/两个change。

**Interfaces:** 复用`BindingManager(...).create(confirm=False)`作为新入口，`Registry`增加无创建的只读快照方式；`create --project <完整worktree> [--confirm]`复用其余身份/环境参数，可选worktree须相同。返回dry_run的精确计划/至多20项同项目白名单inventory及总数，或核验成功的binding；保存candidate后失败及legacy creating返回create_unverified。ensure仅验证已有binding。

- [ ] 先添加新入口/只读dry-run/ensure无绑定失败回归并运行到RED；为旧行为测试的初始化改用显式create(confirm=True)，保留真正的ensure验证断言，不能删旧安全覆盖换取全绿。
- [ ] 添加每种独立机制的RED：文件/目录fsync失败零native调用；确认创建并完整核验；未启动/回执丢失/损坏不重提；candidate核验失败后重入不create；live/active/unknown/legacy creating/身份漂移拒绝；真实CLI参数/多进程与其他owner合并；替代创建后历史task禁止重放、累计额度不归零。测试沿用现有RemoteOrca和真实临时state/锁/CLI，无真实Orca。
- [ ] 最小实现：只读FD打开现有registry且不落lock；确认前完整list和资格检查；锁内重读/比对并fsync保存state=creating/稳定creation_id及旧绑定快照；锁外一次native create；锁内保存白名单candidate后锁外_verify/_idle；重锁比对/占用检查并扁平归档后bound。任何pending不得经ensure/send/rebind绕过。
- [ ] 将新业务片运行到GREEN，再运行两组focused unittest；同步Skill/reference/受影响说明与AGENTS单条，说明本地保证范围和用户选择confirm边界。编辑Skill采用writing-skills，行为证据来自本片RED/GREEN而非文案自证。
- [ ] 先核对未改的8文件manifest基线，再仅更新实际修改载荷hash；VERSION不升号。执行原Verification commands全部六项及新命令CLI/并发负向探针，要求无skip/failure/error。
- [ ] 独立Implementation Review检查实际完整diff和调用链，重跑关键命令并独立对抗probe；发现均修复→验证→同阶段复审。随后持久记录最终验证结果，再由不同实例执行单独Final Review；最后仅交付本地成果，不提交/安装/发布。

**Acceptance:** dry-run/ensure零自动创建；用户confirm一次创建且核验后绑定；重复/并发/恢复/未知结果无第二次native create；旧绑定/history/task保护不退化；保存/核验/身份失败fail closed；两组测试、make check、两strict、diff及两阶段独立Review均通过。仅本地验收，不提升为真实远端E2E。

**Rollback/stop:** 新增实现前保留原有13项及AGENTS的私有前像；发现未知并发漂移立即停写，按前像只人工恢复本轮增量，不动既有成果。任何需真实Orca/配置/Git/发布、改变合同保障或降低证据等级的操作停在已有授权边界。
