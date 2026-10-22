# Tasks

作者：elvis。主控：Codex /root。用户授权来源：本轮 review 后明确要求优化、推送 Git 与更新安装。

- [x] 复现调用问题，核对源码/安装差异与既有工程规则；保留主工作区未跟踪需求文件。
- [x] 平台隔离 worktree 与安装前像已建立；范围、设计及验证计划已记录。
- [x] OpenSpec strict 与独立 Preflight。Codex独立实例review_install_drift在修正整任务reconcile观察范围后PASS；计划SHA256为a7a96fe27d6303155b16a7e45774b6d2a1c692019ab4c47c6706d677289ca339。
- [x] 绑定 helper：安装身份能力导入、证据并发回执、原始字节发送、有限进程回收及失败回归。binding 123/123通过；真实CLI链、24个非evidence漂移场景及组内/逃组/非法UTF-8回收均覆盖。
- [x] packet helper：父路径兼容、共享传输门禁、最小 diff 指令及失败回归。先观察4 failures及路径拒绝，再focused 4/4和packet 38/38通过；新增文件补丁经真实Git应用验证，未放宽parser。
- [x] Skill/reference/工程说明一致化；agent 消费验证，版本与八文件 manifest。dev6，八文件范围不变。
- [x] 完整本地检查、独立 Implementation Review，修复同范围发现。主控161项/12.792s，独立review161项/12.811s；6个额外反例通过，strict及diffcheck通过。修正既有runpy测试包装器模块路径，真实CLI入口未改。
- [x] 新鲜最终验证与独立 Final Review、工程经验归纳。Learning Review PASS，主控提升三项项目内不变量；主控fresh161项/12.776s，另一独立Final reviewer 161项/12.751s及额外5反例通过，strict/diffcheck通过。OpenSpec在发布与安装完成后归档。
- [x] 授权提交、主分支安全整合、推送及远端 revision/CI 核对。发布63ea82cedaa8c1462846945b536536f897e091d6，主分支fast-forward后161项通过，ls-remote一致；[CI 39763619836](https://github.com/codebyelvis/grok-cc/actions/runs/39763619836)四矩阵全部success。
- [x] 固定发布提交 staging、漂移检查、八文件安装同步及独立安装验收。官方installer固定发布SHA，staging161项/12.926s；仅同步清单八文件。主控active161项/12.925s，独立安装审核161项/12.735s及两个实际入口零原生调用探针通过；权限、11个非载荷entry、两入口链接和八文件前像全部核对保留。

真实云端任务未纳入本次验收；不操作共享 registry、已有云端会话或 native 配置。

交付边界：本轮只包含已审核修复及对应文档/回归；原主工作区三份未跟踪需求资料原样保留，不提交。隔离worktree、安装staging与安装前像保留，不清理其他会话或恢复旧unknown。主控已重新读取安装Skill，其他旧窗口仍须重新读取/加载。安装以发布提交为来源，后续归档提交不改变八文件载荷。

Skill消费证据：独立旧版probe选择ensure→send；独立新版probe选择直接send，并保留无绑定dry-run、未知结果不重发/不finish、最小新增文件diff和foreign native env拒绝Grok。仅方案演练，没有实际远端调用。
