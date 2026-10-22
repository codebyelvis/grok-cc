# 云端最终补丁请求示例
作者：elvis

优先使用task_packet.py render生成生产prompt；以下为同一产物协议的人工审查示例。只传当前task必要资料，不附其他会话或整个仓库。任务编号单独出现，说明包装方式时不把它展开成完整标记行，避免TUI回显被误识别为产物。

```text
请仅根据给定Mac源码快照提出当前任务的最终补丁。
任务编号：<task_id>
允许修改：<白名单相对路径>
目标与Mac验收条件：<具体需求>

你无法访问Mac项目。不要读取或修改云端项目、安装、运行云端项目测试来冒充Mac验证。
可将建议diff写入云端临时产物文件，仅用于计算完整性，不改云端工程。
补丁块外正文最多10行结论；不复述任务、不贴完整测试日志。
仅已有合法日志报路径与通过/失败计数，并明确它不是Mac实测证据，不为此新跑项目测试。

产物为最小unified diff，无Markdown围栏，保留所有空格与UTF-8原字节。
每个文件直接从--- a/相对路径和+++ b/相对路径开始，随后是@@及hunk。
新增文件的旧路径为/dev/null。仅文本修改/新增，不改变文件权限。
不输出diff --git、index、new file mode、old mode或new mode元数据。
开头独立行由BEGIN_PATCH、一个ASCII空格、上面的任务编号拼接而成。
其后是以LF结尾的diff；仅支持白名单文件的文本修改/新增。
请用工具对这个diff文件的原始字节计算SHA256与LF字节数，不要猜摘要或行数。
在diff后、结束行前，依次输出PATCH_SHA256、空格、64位小写十六进制摘要；
再输出PATCH_LINES、空格、十进制LF行数，每项各占独立一行。
结束独立行由END_PATCH、一个ASCII空格、任务编号拼接而成。
计算对象只有diff，不包括两项完整性元数据或包围标记；CRLF算一个LF，裸CR/Unicode分隔符是内容。

源码快照：
<经审查的任务文件内容>
```

check默认要求唯一完整且hash/行数有效的产物候选。无元数据的提示样板不算第二个真实产物；损坏hash、错误行数、截断或多个有效块都阻断。显式`--allow-unhashed`仅兼容唯一、完整、完全无完整性元数据的旧回复，不能把损坏hashed回复降级。SHA保证传输一致性，不证明代码安全、正确或测试通过；原packet白名单/基线/路径及Mac Git检查仍必需。

## 长回复与降级

优先以原绑定cursor读完整stream。必要时先读官方orchestration，仅对既有绑定worker用其版本匹配的transcript能力；sourceExact不等于contentComplete。若缺少ORCA_AGENT_LAUNCH_TOKEN等必要能力，应报告transcript不可用，不修改配置补token。

云端jsonl只能由有权限的云端侧既有只读渠道回收当前任务最终产物，并由Mac原packet及hash检查；Mac helper不新建shell/终端、不读其他会话。screen回退、裁剪、缺页、缺END或空格丢失时停止，不拼凑、不重新执行任务换输出通道。此版本没有collect自动完整回收功能。

格式修正仅在main已accepted、无unknown、还有一次task提交额度且用户明确要求时，使用同task的export消息要求重导出既有最终补丁。禁止循环export-N、索取整个原始回复/对话/内部推理，或借重导出绕过模型安全拦截。可靠文件回收同样不能取代hash、基线、测试或Review。

## 准确解释阻碍

- `reasoning_extraction` / safeguards：记录模型、task_id、请求标识和实际错误类别，按模型拦截报告，保留未完成状态。标签不能证明请求违规或上下文过长；不编码、换身份/模型或连续改写绕过。官方渠道：/feedback 或 [Anthropic安全说明](https://support.claude.com/en/articles/8106465-our-approach-to-user-safety)。
- 本机`Could not read Orca environments ... file is invalid`：本机配置读取错误，权限也可能影响读取；不导出配置、不擅自重写配对文件，不直接推断云端掉线。
- `remote_runtime_unavailable` / host did not answer：远端不可达不证明未送达。保留intent和白名单receipt，走既有绑定只读调查；不能凭此重发。
- 截断/空格丢失/hash或行数不符/任务编号不符：产物完整性失败，停止应用；不当作模型成功或Mac测试通过。

完整决策表与次数/换绑门禁见[会话绑定](session-binding.md#错误--下一步)。普通代码请求也可能被过滤误判；[公开用户报告](https://github.com/anthropics/claude-code/issues/97560)只是旁证，不是本次根因的官方判定。
