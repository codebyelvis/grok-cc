# grok-cc 工程不变量

作者：elvis。

本页归纳已批准、已实现的不变量及其回归入口，不新增运行权限。调用规则以 [Skill](../../SKILL.md)、[会话绑定](../../references/session-binding.md) 和现行 OpenSpec 为准；本轮状态见[会话归档](../handoffs/2026-10-19-local-closeout.md)，决策原因见 [ADR 0001](../adr/0001-local-at-most-once-create.md)。

## 创建与发送分开计数

本地最多一次创建提交只约束同一保留 registry、真实 owner 和目的地内的每个创建意图。它不是原生 caller-key 去重，也不是跨客户端、跨 registry 或 exactly-once；持久预约之后即使子进程没有启动，也允许永远保持未知。不得删除或切换状态目录来恢复“重试机会”。

发送的 task 累计上限另为两次，main、合法 export 和明确 not_sent 的重试共用；list/read/wait 的预算与计数不消耗模型派发额度。创建的“未启动也不重提”不能套成发送重试规则，发送的 not_sent 规则也不能反向用于创建。

## 存在性、所有权与完整快照

不可达、暂时断连、忙碌、非 auto、裁剪清单都不证明原实例消失。完整清单仍须有安全、唯一的 handle 和有效 runtime；云端 selector 要求非空 repo ID 与绝对路径。无绑定时 ensure 只核验失败，创建预览零落盘，真实新建仍须用户选择具体目标。

create receipt 仅能产生 pending candidate。保存后经完整身份、存活、可写、空闲、auto 和输入核验，重锁检查同一意图及占用后才可 bound。其他 owner 的精确 pending candidate 同样占用目标；在候选保存、恢复及最终绑定阶段都要检查。

替换绑定前，creation_previous 中的 tasks/active 必须与 reservation 保存的旧任务一致。带旧任务却缺快照、缩水或状态漂移时保留原文件并阻断。旧 task 身份、累计次数与未知消息不能随创建、rebind、finish 或历史归档归零。

远端等待不持 registry 锁；回来后重载同 owner 意图并合并其他 owner。晚回执不能覆盖变更后的意图，也不能用旧整库快照抹掉他人的更新。

## 产物字节和证据边界

补丁只按 LF 识别结构，CR/CRLF 和其他 Unicode 分隔符保留原字节。PATCH_SHA256/PATCH_LINES 校验对象是原始 diff；损坏 hashed 产物不能用 allow-unhashed 降级，回显样板也不能遮掉损坏候选。之后仍须原 packet 的白名单、全部基线、路径和真实 Git 检查，云端声称通过不能替代 Mac 验收。

prepare/render 共用最终 UTF-8 prompt 预算，媒体扩展名 override 不放行二进制或已识别编码媒体。秘密扫描是辅助防线；不得外发凭据、原生配置、历史或其他项目材料。

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

下表是机制映射，不是新的测试框架。函数位于 [binding tests](../../scripts/tests/test_session_binding.py) 或 [packet tests](../../scripts/tests/test_task_packet.py)。

| 不变量/错误反例 | 已有确定性回归 |
| --- | --- |
| 预约同步失败零调用；未启动、丢回执、旧 creating 不重提 | test_explicit_reservation_sync_failure_prevents_native_create；test_explicit_failed_native_launch_is_not_resubmitted；test_explicit_lost_receipt_does_not_infer_owner_or_recreate；test_explicit_legacy_creating_blocks_every_mutating_entry_point |
| 无效 intent/runtime/清单不能升级为证据；不完整 selector 零副作用 | test_explicit_candidate_requires_valid_saved_intent_identity；test_explicit_invalid_runtime_is_rejected_before_reservation；test_explicit_malformed_inventory_never_proves_prior_absence；test_explicit_incomplete_project_cli_is_rejected_before_any_side_effect |
| 旧任务完整保留、历史禁止重放、同目标 rebind 不归零 | test_explicit_recovery_rejects_missing_or_inconsistent_previous_tasks；test_explicit_replacement_preserves_archived_task_identity_and_attempts；test_archived_task_cannot_replay_after_rebind；test_same_target_rebind_cannot_reset_task_history |
| 精确 pending candidate 占用；并发和晚回执不能覆盖 | test_explicit_other_owner_pending_candidate_reserves_exact_target；test_other_owner_updates_survive_create_and_send_merge；test_late_receipt_does_not_overwrite_changed_intent；test_parallel_processes_create_and_submit_at_most_once |
| 原始字节、坏 hash/截断和 legacy 降级继续阻断 | test_non_lf_hunk_payload_checks_and_applies；test_cli_preserves_patch_newlines；test_bad_hash_count_truncation_and_damaged_candidate_block；test_legacy_is_opt_in_and_cannot_downgrade_corruption |
| 外发预算、媒体 override 与证据型摘要 | test_prepare_frontloads_same_utf8_budget_as_render；test_media_override_is_only_an_extension_override；test_summary_explicit_evidence_is_short_and_not_a_verdict |

状态分层还有机械边界：上面的校验能证明文件一致，但不能证明原生窗口已消费规则、远端已发布或真实任务通过。这些跨进程/外部事实必须另取实际证据；没有通道时保持未验证。对应反例和审查场景见[学习卡](../learning-candidates/2026-10-19-local-closeout.md)。
