# 来源与许可

作者：elvis。

## 自有载荷

首次工程化基线来自作者当前使用的 grok-cc Skill。`bundle-files.txt` 仅列出自有的入口、展示配置、参考规则、两个 helper 和两个测试文件，共 8 个文件；导入时保留原字节，SHA256 记录在 `bundle-manifest.json`。

这里没有导入其他项目的任务补丁、会话记录或正式审核合同，也没有收录 Orca/Cursor/Claude 安装包源码。排障时读取第三方本机源码只作为本地调查，不赋予再分发权，本仓库不 vendor 那些内容。

## 外部工具

- helper 依赖 Python 标准库；部分操作调用用户已有 Git 和 Orca CLI。
- Skill 需要宿主当前版本的 `orca-cli` / `orchestration` guide；仓库只引用，不复制其整包或假定其 API 永远不变。
- 安装文档引用用户环境中已有的 `skill-installer`，不把其代码或原生配置打入本包。
- CI 使用上游 [actions/checkout](https://github.com/actions/checkout) 和 [actions/setup-python](https://github.com/actions/setup-python)，按固定提交引用，不 vendor。Checkout 使用只读权限并关闭凭据持久化。

## 分发边界

`bundle-manifest.json` 是载荷一致性清单，不是代码签名；可信性仍依赖实际批准的来源、revision 和审核。首次导入未创建远程或 release/tag。

本准备版保留全部权利。许可证由作者在发布前决定，不能根据工程目录名推断 MIT、Apache 或第三方开源授权。
