# grok-cc 工程不变量

作者：elvis。

本页归纳已批准、已实现的不变量及其回归入口，不新增运行权限。调用规则以 [Skill](../../SKILL.md)、[会话绑定](../../references/session-binding.md) 和现行 OpenSpec 为准；本轮状态见[会话归档](../handoffs/2026-10-19-local-closeout.md)，决策原因见 [ADR 0001](../adr/0001-local-at-most-once-create.md)。

## 创建与发送分开计数

本地每个创建意图只提交一次新启动，只约束同一保留 registry、真实 owner 和目的地。Orca≥1.4.229新协议只在已保存原生operationId及unknown/retrySafe证据时，允许原host/context显式重放同ID一次；重放先持久消耗额度，不转为新启动。不承诺跨客户端、跨registry或exactly-once。持久预约之后即使子进程没有启动，也允许永远保持未知；旧无ID pending不能升级成重放权限。不得删除或切换状态目录来恢复“重试机会”。

发送的 task 累计上限另为两次，main、合法 export 和明确 not_sent 的重试共用；list/read/wait 的预算与计数不消耗模型派发额度。创建的“未启动也不重提”不能套成发送重试规则，发送的 not_sent 规则也不能反向用于创建。

## 看见回复不等于受理

宿主 status 列出 `agent.launch.v2` 只说明执行端宣称有该能力。Mac CLI 提交的 client capability 是另一层。客户端集合缺这项时，服务端可以在写出 operationId 之前拒绝 launch。没有 operationId 的 creating 保持 unknown：不能重放，不能改记成无副作用，也不能再新建。打印能力列表时被截断的前几项，不能当成能力缺失。grok-cc 不修改 Orca 安装包来补这项；那要单独授权。

每次原生调用都带上已保存的 `--environment`。不带该环境的 status 或 read 可能打到另一个 runtime，并对已绑定 handle 报 stale。先用同一 environment 复读，不新开终端。

屏幕正文、结束标记、`tui-idle` 和 `input_accepted` 都不是受理。reconcile 只有在 stream 可读，且已保存 receipt 证明 accepted 时，才把 `sending` 改成 `accepted`。receipt 为空或 stream 没有形成受理证据时保持 `sending`。任一消息未 accepted 时 finish 拒绝。同一消息再次 send 只 resume，不第二次提交。提问回显里可能先出现标记；可见正文取到最后一处标记，并且只作为可见证据。

启动提示是闭集。`Try "how does <filepath> work?"` 只在没有任务历史时视为空输入。bypass 或新的占位提示不能靠改权限、清空输入来放行。

本地 claudex 的 settings、网关和登录不复制到云端 CC。云端 CC 的家目录配置也不覆盖本地 claudex。安装只替换 bundle 的 8 个文件，并保留 native 配置。

## 存在性、所有权与完整快照

新预约只用`terminal create --command "claude --permission-mode auto"`，不传裸claude，不改全局agentDefaultArgs。先持久reservation，再保存同runtime精确handle，最后完整清单和auto/无bypass/草稿/归属核验。新terminal.create.claude-auto.v1没有operationId/replay，失败或丢回执继续pending；已有agent.launch.v2预约保留原协议，不因升级改写。具体命令和预览必须一致。对应回归为AutoLaunchTests及实际helper CLI确认/并发测试。

不可达、暂时断连、忙碌、非 auto、裁剪清单都不证明原实例消失。完整清单仍须有安全、唯一的 handle 和有效 runtime；云端 selector 要求非空 repo ID 与绝对路径。无绑定时 ensure 只核验失败，创建预览零落盘，真实新建仍须用户选择具体目标。

仅对既有agent.launch.v2预约，agent launch先保存原生operationId及outcome.kind/handle，再从完整清单取得精确handle的incarnation并保存pending candidate；任一回执都不等于bound。保存后经完整身份、存活、可写、空闲、auto 和输入核验，重锁检查同一意图及占用后才可bound。其他owner已保存handle但没有incarnation的launch outcome、以及精确pending candidate，同样占用目标；候选保存、恢复及最终绑定都要检查。structured聊天页与非auto终端保留pending，不改配置强制放行。

创建前status/list必须同runtime、执行端ready/reachable且具备正式版本≥1.4.229和所需launch能力。原生JSON错误从stdout固定结构投影；operationId不从散文、stderr token或本地creation_id推断。只有kind/started、有限returncode/timeout、已知code及最小启动身份能落入安全诊断，launchRequest/cause/recoveryCommand等不保存。

替换绑定前，creation_previous 中的 tasks/active 必须与 reservation 保存的旧任务一致。带旧任务却缺快照、缩水或状态漂移时保留原文件并阻断。旧 task 身份、累计次数与未知消息不能随创建、rebind、finish 或历史归档归零。

远端等待不持 registry 锁；回来后重载同 owner 意图并合并其他 owner。晚回执不能覆盖变更后的意图，也不能用旧整库快照抹掉他人的更新。

send等待回执时，reconcile可能同时更新同任务的main/export，或旧任务的观察。仅既有消息的evidence不属于提交意图：容忍并保留其变化，再把回执写入最新行。其他字段仍须完全一致；不能因观察更新丢弃有效回执，也不能借合并观察放行新task/message、attempt、内容、次数、receipt或身份漂移。

原生CLI每次使用自有session/进程组，超时和读取异常只回收该组；communicate和wait均有界。只kill直接子进程仍可能被继承管道的后代拖住；即使后代逃离进程组，helper也不能无限等待EOF。清理失败、非法UTF-8或本地进程退出均不证明远端未执行，unknown仍不重发。

## 产物字节和证据边界

补丁只按 LF 识别结构，CR/CRLF 和其他 Unicode 分隔符保留原字节。PATCH_SHA256/PATCH_LINES 校验对象是原始 diff；损坏 hashed 产物不能用 allow-unhashed 降级，回显样板也不能遮掉损坏候选。之后仍须原 packet 的白名单、全部基线、路径和真实 Git 检查，云端声称通过不能替代 Mac 验收。

prepare/render 共用最终 UTF-8 prompt 预算，媒体扩展名 override 不放行二进制或已识别编码媒体。秘密扫描是辅助防线；不得外发凭据、原生配置、历史或其他项目材料。

原字节边界从prompt读取即开始：send不能用universal-newline读取把CR/CRLF变成LF；下游补丁hash正确不能补救上游快照已被改写。prepare/render/send共享450KiB、NUL和保留marker门禁，预算override不得超过传输上限。生产提示明确最小---/+++/@@格式，不靠放宽parser接受Git权限元数据。父输出路径可规范化解析别名，但解析后项目边界、逐组件O_NOFOLLOW和独占leaf写入仍须保持。

## 不把不同层的状态混成一个“已更新”

| 层 | 可接受证据 | 不能推出 |
| --- | --- | --- |
| 本地源码 | 精确分支/提交、工作区、对应测试与 Review | master 已更新、已推送或已安装 |
| 远端发布 | 实际获授权推送与远端 revision/CI | active Skill 已同步 |
| 本地安装 | 固定来源、8 文件 hash、实际入口、安装版回归及独立验收 | 旧窗口已重载规则、真实云端 E2E 通过 |
| 真实使用 | 正确身份下的真实任务、回执、完整产物和 Mac 验收 | 其他任务或环境整体通过 |

默认安装流程仍见[安装说明](../installation.md)。2026-10-18 用户在知道尚未发布的情况下明确要求本地更新，因此本轮从已审核本地提交离线同步；这是该次明确授权，不是今后默认跳过发布的许可。

仅替换 bundle-files.txt 的 8 文件。更新前保存字节、权限、文件清单和入口链接，复制前再次拒绝漂移；使用现有同步工具，不新增安装器、不广泛删除或整目录覆盖。单文件延迟替换不等于整个安装原子事务。回退前同样检查当前版本，不能覆盖后续更新。旧窗口使用前重新读取 Skill，不以磁盘更新宣称规则热重载。

以下只读校验可对当前源码与实际发现的安装目录比较全部载荷；它不运行 Orca，不读取 registry。两个参数分别是源码根与安装根，也可依次传多个实际入口。

```sh
python3 - <源码根> <实际安装根或入口> <<'PY'
from pathlib import Path
import hashlib, json, sys
source = Path(sys.argv[1])
names = (source / 'bundle-files.txt').read_text().splitlines()
manifest = json.loads((source / 'bundle-manifest.json').read_text())
assert len(names) == len(set(names)) == 8 and set(names) == set(manifest['files'])
assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
for root in [source, *map(Path, sys.argv[2:])]:
    bad = [n for n in names if not (root / n).is_file() or
           hashlib.sha256((root / n).read_bytes()).hexdigest() != manifest['files'][n]]
    if bad:
        raise SystemExit('Payload mismatch: ' + str(root) + ': ' + ', '.join(bad))
    print('Payload matches:', root.resolve())
PY
```

## 回归入口

外部进程替身必须形成闭合的执行边界：fixture用绝对路径和绝对Python shebang，helper子进程的PATH仅指向临时目录，ORCA_CLI_COMMAND默认指向不存在的哨兵文件。相对路径用字面量`./orca`测试，不能经`str(Path('./orca'))`变成会搜索系统PATH的`orca`。选定child cwd中的相对executable和相对PATH条目，必须在首次预检前解析/pin为同一绝对文件，预检与提交不能换程序。机械回归及来源见[执行上下文学习卡](../learning-candidates/2026-10-19-orca229-execution-context.md)。

保存字段的类型检查须区分缺省与显式null；数值先校验边界，再交给可能转换float的有限性函数。合法JSON整数也可能大到令math.isfinite抛OverflowError。畸形outcome/diagnostic、超大或无限timeout均应在查询前返回结构化integrity_failure，保持原state，不让其他owner因同库坏记录收到traceback。

下表是机制映射，不是新的测试框架。函数位于 [binding tests](../../scripts/tests/test_session_binding.py) 或 [packet tests](../../scripts/tests/test_task_packet.py)。

| 不变量/错误反例 | 已有确定性回归 |
| --- | --- |
| evidence与提交意图区分；main/export观察可合并，其他字段漂移拒绝 | test_reconcile_during_send_preserves_accepted_main_receipt；test_reconcile_during_send_preserves_main_and_export_evidence；test_reconcile_during_send_preserves_uncertain_error_and_receipt；test_late_receipt_rejects_every_non_evidence_intent_change |
| 自有组回收、逃组持管道及读取失败有界；unknown不重派 | test_native_timeout_kills_only_owned_process_group；test_native_timeout_is_bounded_when_descendant_escapes_with_pipes；test_native_read_failure_is_bounded_when_descendant_escapes_with_pipes；test_native_invalid_utf8_returns_structured_failure_after_cleanup；test_native_cleanup_timeout_retains_sending_intent_without_resubmit |
| 真实CLI保留prompt CR/CRLF；传输门禁提前拒绝且零输出 | test_prepare_render_send_cli_preserves_crlf_and_bare_cr_bytes；test_prepare_and_render_reject_unsupported_transport_without_output；test_transport_boundary_counts_utf8_bytes_before_render_output；test_send_transport_rejection_preserves_state_before_native_calls |
| Grok不借外来宿主换UUID；父路径别名不突破项目边界或覆盖输出 | test_grok_rejects_foreign_native_env_even_with_unrelated_uuid；test_output_parent_symlink_like_macos_tmp_is_resolved；test_output_never_writes_project_during_parent_symlink_swap |
| 新预约准确的每实例auto命令与零落盘预览；失败后不重创/重放 | AutoLaunchTests；test_explicit_create_cli_dispatch_and_confirmation_boundary；test_parallel_processes_create_and_submit_at_most_once |
| 精确八提示仅限首次；显式draft、相似文本、非auto或身份漂移均阻断 | test_claude_2_1_303_static_placeholders_bind_new_create_once；test_typed_try_text_reported_as_native_draft_is_never_a_placeholder；test_placeholder_lookalikes_and_drifted_or_non_auto_candidates_stay_pending |
| 预约同步失败零调用；未启动、丢回执、旧 creating 不重提 | test_explicit_reservation_sync_failure_prevents_native_create；test_explicit_failed_native_launch_is_not_resubmitted；test_explicit_lost_receipt_does_not_infer_owner_or_recreate；test_explicit_legacy_creating_blocks_every_mutating_entry_point |
| 无效 intent/runtime/清单不能升级为证据；不完整 selector 零副作用 | test_explicit_candidate_requires_valid_saved_intent_identity；test_explicit_invalid_runtime_is_rejected_before_reservation；test_explicit_malformed_inventory_never_proves_prior_absence；test_explicit_incomplete_project_cli_is_rejected_before_any_side_effect |
| 旧任务完整保留、历史禁止重放、同目标 rebind 不归零 | test_explicit_recovery_rejects_missing_or_inconsistent_previous_tasks；test_explicit_replacement_preserves_archived_task_identity_and_attempts；test_archived_task_cannot_replay_after_rebind；test_same_target_rebind_cannot_reset_task_history |
| 精确 pending candidate 占用；并发和晚回执不能覆盖 | test_explicit_other_owner_pending_candidate_reserves_exact_target；test_other_owner_updates_survive_create_and_send_merge；test_late_receipt_does_not_overwrite_changed_intent；test_parallel_processes_create_and_submit_at_most_once |
| 既有agent协议先存handle再查incarnation；未有candidate也占用；structured不绑定 | test_launch_receipt_is_durable_before_inventory_and_incarnation_lookup；test_receipt_handle_without_candidate_already_reserves_other_owner_target；test_structured_outcome_stays_pending_without_terminal_verification_or_replay |
| 同ID重放先持久计数、并发限一次；runtime/context/无ID不能绕过 | test_real_cli_replays_stdout_unknown_once_under_concurrent_callers；test_replay_reservation_fsync_failure_prevents_native_replay；test_replay_requires_saved_id_confirm_original_context_and_budget；test_legacy_no_id_pending_is_unchanged_after_upgrade_even_with_retry_flag |
| stdout安全投影；错误ID/能力/版本不能新建或扩大权限 | test_stdout_native_error_contract_is_minimized_not_parsed_from_prose；test_mismatched_replay_receipt_cannot_replace_original_operation_id；test_status_inventory_runtime_mismatch_never_reserves_creation；test_launch_preflight_rejects_old_missing_capability_and_unready_before_reservation |
| 预检与启动同一child-cwd executable；fixture不回退真实CLI；畸形null先结构化阻断 | test_relative_executable_is_pinned_from_child_cwd_before_every_native_call；test_fixture_environment_disables_unselected_native_cli；test_null_saved_outcome_is_blocked_as_json_before_other_owner_queries |
| 原始字节、坏 hash/截断和 legacy 降级继续阻断 | test_non_lf_hunk_payload_checks_and_applies；test_cli_preserves_patch_newlines；test_bad_hash_count_truncation_and_damaged_candidate_block；test_legacy_is_opt_in_and_cannot_downgrade_corruption |
| 外发预算、媒体 override 与证据型摘要 | test_prepare_frontloads_same_utf8_budget_as_render；test_media_override_is_only_an_extension_override；test_summary_explicit_evidence_is_short_and_not_a_verdict |
| 无 receipt 的可见屏幕和标记不能受理、不能 finish、不能重发；调用带已保存 environment | test_visible_screen_marker_without_receipt_stays_unaccepted；test_started_failure_never_becomes_not_sent |
| 精确启动提示只在无任务历史时放行，含 how does 提示 | test_how_does_filepath_startup_hint_is_allowed_only_without_task_history；test_native_empty_startup_hint_with_nbsp_is_not_a_user_draft；test_fix_typecheck_startup_hint_is_allowed_only_without_task_history |

状态分层还有机械边界：上面的校验能证明文件一致，但不能证明原生窗口已消费规则、远端已发布或真实任务通过。这些跨进程/外部事实必须另取实际证据；没有通道时保持未验证。对应反例和审查场景见[学习卡](../learning-candidates/2026-10-19-local-closeout.md)。宿主能力列表与客户端提交能力、以及可见屏幕冒充受理的对抗场景见[可见回复学习卡](../learning-candidates/2026-10-19-recovery-visible-reply.md)；该卡已由主控依据独立实现 Review 和确定性回归提升为项目内规则，真实云端事实仍单独取证。
