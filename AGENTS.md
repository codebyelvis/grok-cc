# grok-cc 工程规则

作者：elvis。

## 范围

本仓库维护 Mac 到 Grok Bot Claude Code 的 Skill、helper、回归及文档。安装目录是运行时副本，不作为 Git 源仓库。其他工程的源码、私有任务、治理状态和审核报告不迁入本仓库。

修改前读取当前宿主适用规则、[SKILL.md](SKILL.md) 与受影响代码。工程封装不授予新派发、安装、认证、网络或发布权限。作者署名按实际贡献保留，新建个人文件默认 `elvis`。

## 必须保持

- 一真实本地会话对应一个云端 CC，不扫描公共空闲池。
- 不确定 create/send 结果保留 intent，不盲目重试、不更换身份或终端。
- 保留真实草稿；未知提示、不可读屏幕、非 auto、身份漂移继续阻止发送。
- 不提供 legacy 认领、自动换绑、registry reset/delete 或会话清理捷径。
- 补丁必须完整、匹配原 packet 白名单及基线；在 Mac 验证，不能把云端声称通过当本地证据。
- `finish` 不是项目完成。模型安全拦截、网络故障和产物裁剪分别报告，不借重导出绕过拦截。

## 验证与来源

- 运行 `make check`；行为修复先有相应失败回归，再最小修复。使用现有测试，不另建调度或运行状态框架。
- 行为、安装、安全、恢复或生命周期改变先按适用治理确认具体范围；标准及更高风险工作保留独立审核。
- 载荷改变后审查并更新 `bundle-manifest.json`，清单以 `bundle-files.txt` 为准；不通过重算掩盖未知漂移。
- 测试须隔离 state/project，不操作本机共享 registry、云端会话或 native config。
- 不提交凭据、配对配置、模型设置、hooks、会话、SQLite、日志、缓存、packet/reply/patch、私有证据或第三方安装包代码；`.gitignore` 不是敏感审查的替代品。

## Git 与交付

- GitHub remote 由用户提供，提交/推送按当阶段明确授权执行；不擅自 add、commit、push、reset 或 clean。
- 提交使用中文 Conventional Commits 标题及分组正文，不添加未经要求的 `Co-authored-by`。
- 交付前核对工作区，说明本轮、既有和他人改动，以及保留原因、处理方式和下一步条件。
- active Skill 更新在批准的 source 发布之后执行；保留安装前像，拒绝并发漂移，不触碰 `~/.local/state/grok-cc` 或原生配置。
