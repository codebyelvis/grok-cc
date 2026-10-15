# 安装、更新与校验

作者：elvis。

本文是发布后的可重复操作说明。实际仓库为 `codebyelvis/grok-cc`；每次 staging 安装都需要基于已推送且审核通过的真实 revision 验证，不能把本说明当作安装成功记录。

## 1. 固定来源

由用户提供真实 GitHub 仓库及推送指令。检查账号、remote、待提交范围、许可证和本轮测试/Review 后，才按授权提交、推送。不要猜 owner/repo 或提前建立远程。

发布后记录真实提交 SHA；安装固定该 revision，不能用移动中的 `main` 冒充已审核版本。`VERSION` 是工程版本标签，不能代替 Git revision。

## 2. 隔离 staging

复用当前环境已安装的官方 `skill-installer`。先阅读其当前 SKILL.md 及脚本参数；缺失时报告，不为本包编写第二个安装器。

以下变量均需维护者填写实际值。`GROK_CC_STAGE` 必须是新建的临时目录，不得指向任何 active Skill 或运行状态路径。

```sh
python3 "$SKILL_INSTALLER/scripts/install-skill-from-github.py" \
  --repo "$GROK_CC_REPO" --path . --name grok-cc \
  --ref "$GROK_CC_REV" --dest "$GROK_CC_STAGE"
cd "$GROK_CC_STAGE/grok-cc"
make check
```

`SKILL_INSTALLER` 是当前官方 Skill 的真实目录；`GROK_CC_REPO` 是已核对的 `owner/repo`；`GROK_CC_REV` 是已推送且审核通过的提交 SHA。已有安装器会拒绝覆盖现有目的目录，这里只使用其新目录 staging 能力。

staging 可能包含仓库工程文件。最终 active Skill 仅取 `bundle-files.txt` 列出的 8 个载荷文件，不同步 `.git`、CI、文档或本机状态。读取的清单、哈希和提交必须属于同一已批准 revision。

## 3. 安装前像和漂移

active 安装路径由实际宿主发现；已有共享安装通常位于 `~/.agents/skills/grok-cc`，Codex/Claudex 入口可能链接到它。不要把示例路径当发现结果，也不要重写已有链接。

更新前：

1. 在 Skill 发现目录之外保存现有载荷字节、权限、文件清单及入口链接目标。
2. 核对当前安装与本次接受的安装前像；有其他窗口的更新或未知差异则停止，不能反向覆盖。
3. 协调使用窗口，避免同步期间读取混合版本；复制前再次核对前像。本包不提供原子安装/并发协调器，不能声称具备该能力。
4. 源码/产物/hash/前像确认后，在该阶段明确授权内使用现有文件同步机制，仅替换载荷清单中的文件；不使用广泛 `--delete` 或整目录覆盖。

本文不提供直接写 active 目录的一键命令；实际同步必须使用当次已授权并核验的目标、前像和同步方式。每次升级保留完成这些检查的事实记录。

## 4. 安装后验证

- 按发布的 `bundle-manifest.json` 逐个核对 active 载荷 SHA256，确认期间没有版本漂移。
- 从 active 路径运行 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -v`，设置工作目录为该 Skill 目录。
- 验证实际 Codex/Claudex 入口解析到预期安装，并在原生窗口重新读取 Skill；已有 helper 调用会读取磁盘新版，但不能推断旧窗口的自然语言规则已重载。
- 不以目录存在、哈希匹配或单测代替真实调用验收。需要模型实测时，仅使用自己真实会话的固定绑定和仍需要执行的真实任务，不重放已完成任务。

始终保留 `~/.local/state/grok-cc` 的 bindings、receipts 和锁，不把它们搬入源码、staging 或其他安装。安装不能 reset 绑定或清理云端会话，也不改变 Claude/Codex 的账号、模型、hooks、MCP、代理或配对配置。

## 5. 回退

源码 revision 和 active 安装分别回退。先比较当前安装是否仍是本次安装后的版本；若已有其他更新，停止协调，不覆盖。仅在既有授权内恢复本次保存的载荷前像和原链接，重新验证入口与 suite，保留运行状态和回执。不得为回退删 registry、强制重派任务或恢复其他项目的旧备份。
