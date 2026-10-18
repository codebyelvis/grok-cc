# 省额度与交接摘要设计

作者：elvis。

## 1. Shared prompt and budget

依赖片提供纯渲染入口；prepare 和 render 调用同一函数完成安全文本协议拼接、扫描及预算。预算对象是最终外发UTF-8提示，不是包含project_root/sha/JSON缩进的本地packet序列化。120KiB=120×1024字节；边界正好相等可接受，超过拒绝，--max-bytes须为正整数；MAX_FILE/MAX_TOTAL等现有安全上限保持，调大外发阈值不取消这些限制。

成功prepare/render JSON报告prompt_bytes、token_estimate和估算性质，prepare另可报packet_bytes，避免混淆。失败只报实际字节、阈值和缩小白名单建议，不写部分输出或回显内容。token_estimate=ceil(prompt_bytes/4)，不冒充provider tokenizer精确结果。

生产render包含最多10行非补丁结论、不复述、不贴整段测试日志。模板和SKILL引用同一合同；测试不仅grep文档，还检查真实函数/CLI输出。CC不运行云端项目测试，若已有合法日志则只报路径/计数且标记不是Mac验收；生成diff临时文件并计算SHA属于产物生成。

## 2. Message attempts and read attempts

task累计最多2次真实submission，main与合法export共用，同时保留每message次数。调用send前与intent原子保存；preflight失败不计次，accepted重复resume不计次。未知结果仍消耗一次且不重试；旧intent/receipt缺attempts时每message至少计1次，不重置为0。

同message重试只准明确not_sent且同task/message/sha，重新verify/idle；main已accepted后可显式提交仅修正格式的export消耗剩余一次，不重做开发或绕过模型拦截。第三次一律阻断，不换export-N绕过task总额。request retry在任何Orca调用前unsupported_contract。

BLOCKED的attempts字段指当前task累计提交次数；无task上下文为0，非法输入/完整性/模型拦截retryable=false。只读链路另报read_attempts，允许在预算内超过2次；预算耗尽则停止本次命令，下一次只读恢复不授权模型重发。不增加通用运行状态账本。文档把“最多2次模型派发”和“预算内只读调查”分开，避免把retryable=true误读成自动提交许可。

## 3. Evidence-based optional summary

handoff-summary是本地只读汇总加一次显式外部文件写入，不读取共享registry、云端handoff或其他会话，不执行测试。基础参数task-id/out产生未提供文件清单、未验证Mac测试等事实，绝不推断PASS。

可选--packet提供task身份与相对文件列表；task-id不符拒绝，读取显式UTF-8并验证schema/安全路径。可选--mac-test仅接受受限格式 `<label>:<pass|fail|not_run>:<passed>:<failed>`：label为短标识符，计数为非负整数且状态一致，不接受命令、日志、任意源码正文或可执行内容。--unverified接受短受控标签，--category用既有类别枚举。所有字段仍经secret扫描及长度/控制字符检查，防止任务名、路径或标签泄露token。

最多15个LF行：标题、task_id、来源、最多合并行的文件列表、明确标为主控提供而非helper执行的Mac测试结果、未验证项、阻碍类别；超长列表给计数及截断说明，不伪称完整文件清单。无证据不能生成“已通过”总体结论，摘要不能替代原packet、checked.patch或Review。

沿用write_external_output私有0600/no-overwrite/no-symlink。项目根优先来自显式packet；未提供packet时使用显式--project-root，缺省仅在能只读确定Git顶层时采用该顶层，否则要求--project-root，不盲用任意子目录。项目外限制不包含摘要内容中的project_root，摘要不输出绝对Mac路径。

云端追加是独立外部写入，必须另获目标文件和内容授权；不能从用户请求本地summary推断同意写 `/workspace/handoff/`。

## 4. Media extension gate without binary transport

默认拒绝常见图片/视频/扫描件扩展名（含png/jpg/jpeg/gif/webp/heic/svg/pdf/mp4/mov/webm等）；svg也是多模态资源，需文字摘要而非整图源码进入任务。--allow-binary名称仅兼容用户要求，帮助文字明确“仅放宽扩展名，仍只允许UTF-8文本”，不是二进制传输能力。

显式放宽后仍检查UTF-8/NUL、媒体magic、大小、敏感路径及secret；拒绝明确媒体data URL及有限大小Base64解码后命中magic的块，不声称识别任意编码媒体，不误报普通源码/正则/长文本。已知二进制始终拒绝，不自动编码/插入附件。来源摘要另行提供，不增加外部转码工具或云端操作。

## 5. Docs, version and validation

同一references决策表补充状态下一步，SKILL以小白名单首轮任务开始；禁止回执未知/补丁不完整/模型拦截后换ID重发、开新终端、重启网络。remote unreachable可触发只读恢复，不授权模型提交。

依赖片本地dev2检查通过后，本片顺延dev3；不commit也保留阶段命令结果。保留8文件bundle-files，先比较未改载荷，再更新当前明确变更hash。双语README仅改受影响能力、版本和命令说明，不顺手清理历史排版。

TDD在既有tests内覆盖：真实render短回复约束；prepare/render同预算边界与多字节UTF-8；过限无输出；secret不泄露；摘要<=15行/身份一致/未验证默认/输入受限/项目外输出；媒体扩展名与显式放宽后真实binary仍拒绝；attempt计数持久化/重复resume不增计数/第三次拒绝/read次数分离。回归沿用真实临时文件、Git及远端fixture，不运行真实Orca。

最终命令为两组focused unittest、make check、两份OpenSpec严格验证、git diff --check。独立实现Review和最终Review分开；无法取得官方契约或真实远端验收时如实保留未完成边界，不把全部原始需求记为完成。
