# 剪映 macOS 性能实验补丁

为 **剪映专业版 11.6.0、ARM64、特定原始库 SHA-256** 制作独立应用副本的开源工具。仅分发原创工具与研究摘要，不分发剪映、厂商库、媒体或工程。本仓库同时提供任务列表刷新 `taskcenter`、两任务调度的独立实验构建器，以及纯音频输入的研究与验证工具；没有证明这些实验能加快工程首次打开/解析或首次媒体预合成。

## 当前实操结论

后续一次完整迁移工程导出在等待超过一小时后由用户明确取消，已保存并正常退出，**没有产生新的最终成片**。此前小型 fixture 的成功导出属于独立运行，不能替代该次交付。

先遵从用户取消，以原生取消、Save、正常 Quit 停止长任务并保护必要稳定缓存。Home/重开可能自动清理派生文件，不能当作无成本队列 reset；硬链接也不是可变独立快照，不盲目还原未知有效性的缓存。再试优化时，先原生选中正确的当前时间线，核查其递归必要依赖与有效缓存；精确运行时依赖闭包仍未知，尚无已实现/验证的 active-film scope 修复。最多做一个代表复合的小试，以三分钟作为停止扩大范围、转入诊断的观察门槛；它不是三分钟完成 SLA，也不自动终止正在渲染的任务。不把等待全局队列一小时当作默认验证方法。

单个复杂复合跨工程粘贴的小试在“复制后正常退出/重开”和“同进程回 Home”两条路径均未得到粘贴内容，观察到 Edit → Paste 禁用。**结论为 INCONCLUSIVE**：尚未正向验证 Copy 命令是否生效，剪贴板内容未诊断，不能据此判定原生迁移路线不可行；目前没有可用于提速测量的有效候选。先在同一自有测试工程验证选中目标、Copy 菜单启用、执行原生 Copy，并能在同工程 Paste 后撤销，再测跨工程复制。两任务 cap 未测到提速，分离音频未通过等价验收，不能称未响应问题已全修复；详细结果见 [受控停止与小试边界](EVIDENCE.md#later-full-project-stop-and-bounded-canaries)。

## 未响应问题的修复范围

**没有证据表明所有“未响应”问题都已修复。** 当前发布的是有版本限制的实验与研究；界面刷新、目录访问、后台队列等待和外部存储中断分别处理。

| 现象 | 已验证内容 | 仍未解决/不能宣称 |
|---|---|---|
| 任务弹窗完成刷新压力 | `taskcenter` 窄回调补丁运行 smoke 通过 | 其他刷新路径仍在；不是通用卡死修复，弹窗行可能暂时不更新 |
| 记忆的外置导出目录访问阻塞 | 原生选择可访问本地目录后，观测症状恢复 | 是配置绕行，没有修补导出代码；OS 层根因未知 |
| 导出等待复合准备 | 有界静态路径等待 EditorMode 共享 helper 整个视频队列，未见活动成片过滤 | **尚未修复**；还未映射哪些工作无关或不必要，不能凭全局队列数裁任务 |
| USB/卷断连 | 后续运行有独立外部存储中断事件 | 不是已建立的补丁回归，也没有被本仓库补丁修复 |
| 两个进度条相同 | 两路物理渲染已证实；共享行回调缺少任务身份筛选的静态机制已找到 | **我们的 Parallel2 适配缺口，尚未修复**；progress 可串扰，state 也有静态风险；不能仅据每行显示精确判断任务完成 |
| 两任务并行与纯音频替代 | 并发路径有原生证据；音频快准备有单次观察 | [ABBA 未测到提速](EVIDENCE.md#cold-derived-cache-abba-two-job-scheduling)，纯音频输出等价失败；保留串行默认，不自动改用户音轨 |

完整证据与每项限制见 [EVIDENCE.md](EVIDENCE.md#responsiveness-status-bounded-fixes-workarounds-and-open-issues)。 本轮独立核查的已启动应用磁盘库与签名构建 manifest 一致。并发钩子虽不直接创建/克隆任务或写进度，但改变了原有单活动任务假设，尚未适配共享信号到各行的身份检查。不能据相同百分比去重或删缓存；语义任务是否等价/必要与实际行到任务映射仍未查清。后台还在准备不自动等于界面卡死；也不能把局部 smoke 通过当作整个应用已无卡顿。

## 支持范围与实测状态

| 实验 | 离线构建/静态检查 | 本地运行 | 导出/取消 | 同一冷缓存受控 A/B |
|---|---|---|---|---|
| `taskcenter` | 四字节补丁及签名验证已完成 | 一个 300 秒复合片段预合成/响度 smoke 通过 | 一份约 4 分 8 秒工程导出并完整解码；12 帧抽查、取消测试通过 | **未完成** |
| `none` | 构建同样重签名的无语义补丁对照副本 | 本工具不自动运行 | 待具体比较实验 | 未完成 |
| 两任务并行 | 独立 builder、精确指令/映射/代码洞检查、ARM64 hook 测试与安全副本 | 两路独立预合成及响度完成 | 20 分 55 秒原生导出及完整解码、保存复开缓存保持通过；单项取消/稍后重试通过 | **ABBA 完成，未测到提速** |
| 纯音频响度输入 | 研究阶段，未找到已验证安全补丁 | 原生分离音频冷缓存约 5.25 秒完成一个约 628 秒片段的响度处理 | 无响度 WAV 对照有样本差异，**未通过等价验收** | 单次路径观察，不能作为默认替代 |

历史 smoke 与导出来自本机同版本实验，不是此公共 CLI 在其他 Mac 上的验收。CPU 空闲、单次无卡顿、已缓存工程的导出，都不能证明首次预合成提速。详细边界见 [EVIDENCE.md](EVIDENCE.md) 与 [DESIGN.md](DESIGN.md)。

## 使用前

需要 Apple Silicon Mac、Python 3.9 或更新版、macOS 自带 `/usr/bin/codesign`、自己合法安装且匹配的剪映应用，以及足够的副本空间。无需 pip 包。应用更新后哈希通常改变，工具会拒绝，不要绕过检查。脚本不修改系统安全设置、不删除隔离属性、不修改权限数据库、不启动/退出任何应用、不修改用户偏好或缓存。

先在剪映中保存工程；迁移工程先重链并确认全部素材、字幕及图片，再保存快照，正常退出剪映。测试副本仍可能读取同一账号、偏好和工程目录，应仅用另存的工程做测试，并保留有效缓存和原工程备份。复制应用本身不构成工程隔离。

```bash
git clone https://github.com/JackLee992/jianying-macos-performance-patches.git
cd jianying-macos-performance-patches
python3 jianying_patch.py --help
```

仅检查与显示计划，不创建副本：

```bash
python3 jianying_patch.py \
  --source-app /Applications/VideoFusion-macOS.app \
  --output-app "$HOME/Applications/JianyingTaskCenter-test.app" \
  --patch taskcenter
```

输出父目录须已存在。确认目标路径是新的独立目录，再执行：

```bash
python3 jianying_patch.py \
  --source-app /Applications/VideoFusion-macOS.app \
  --output-app "$HOME/Applications/JianyingTaskCenter-test.app" \
  --patch taskcenter --apply
```

公平对照需用同一工具制作 `--patch none` 副本，例如目标 `JianyingControl-test.app`，同样 ad-hoc 签名。比较两个副本才能减少原厂签名与重新签名差异的混淆。官方安装保留用于回退。不要同时打开两个应用操作同一工程。

`--apply` 先完整校验，再复制、检查副本逐文件哈希、仅修改指定指令、核对完整库差异，随后重签副本库和应用并验证签名，最后复核源应用清单。优先 APFS 克隆复制，失败后使用保留资源叉、扩展属性和 ACL 的 `ditto` 常规复制。没有原地修改模式；已有目标、源内目标、外逃符号链接、不匹配哈希或指令均拒绝。失败时新建副本可能留在目标供检查，脚本不会自动清理用户目录；修复原因后使用另一个新目标。

## 两任务与纯音频实验也在本仓库

两任务候选使用单独入口，输出同样带 UI 补丁的对照副本和候选副本，避免把 UI 刷新差异混入调度比较：

```bash
# 只读计划，不创建文件
python3 experiments/parallel2/build_parallel2.py --source-app /Applications/VideoFusion-macOS.app
# 输出目录必须是新的，父目录已存在
python3 experiments/parallel2/build_parallel2.py \
  --source-app /Applications/VideoFusion-macOS.app \
  --output-dir ./parallel2-build --build-apps
```

**当前 Parallel2 有未修复的行显示适配缺口。** 各运行行订阅同一个 helper 的进度信号，回调读取事件任务进度后写入捕获行，未核对任务身份；两任务时可能镜像最后一次进度，state 回调也有类似静态缺口。这是我们的实验并发适配问题，不是 Qt 不会并行或普遍厂商缺陷。当前发布候选未包含身份筛选修复，对应原生验收未完成，不能把当前每行进度/状态当作精确完成证据；详见 [回调证据与边界](EVIDENCE.md#parallel2-row-callback-identity-gap-not-fixed)。

需要已有 Xcode Command Line Tools。本机冷派生缓存 ABBA 约 267.9 秒对 268.9 秒，未测到吞吐提速；详见 [EVIDENCE.md](EVIDENCE.md) 和 [parallel2 README](experiments/parallel2/README.md)。上限只针对既有串行变更契约下同一 helper 视频队列的 active 项；不保证整个程序线程安全，不改变音频队列。单项原生取消时另一任务继续并完成，稍后重试通过；取消全部、立即重试、错误恢复与全片内容等价仍未验收。取消释放 active 标记也不证明底层渲染器已退出。保留串行默认，不宣称倍速。

纯音频输入当前是**研究，不是可激活补丁**。可在自己安装的原始库上只读核查静态路径：

```bash
python3 experiments/audioonly/inspect_audio_route.py \
  /Applications/VideoFusion-macOS.app/Contents/Frameworks/libVECreator.dylib
```

[研究结果](experiments/audioonly/RESEARCH.md) 解释为什么改文件名、绕过依赖检查或伪造完成不成立。[原生分离音频对照协议](experiments/audioonly/AUDIO_BENCH_PROTOCOL.md) 是显式编辑流程实验，须先证明混音/时间/效果等价再比较响度速度。`compare_audio.py reference.wav candidate.wav` 需要现有 FFmpeg/FFprobe，只解码读取两个输入，以固定 48 kHz PCM 比较；不作增益/时间对齐，不替代人工听检或所有格式的位级等价证明。

原生分离路径确实绕过了本轮冷视频/alpha 预合成，但相同时长的无响度 WAV 对照出现约 1.07% 相对 RMS 样本差异，且 WAV 未声明通道布局。因此这条快路径仍属研究，不能自动改用户工程、放宽阈值或把局部准备耗时包装成最终导出倍速。工程迁移/首次打开/解析也没有提速验收；操作流程见独立技能 [jianying-performance-operator-skill](https://github.com/JackLee992/jianying-performance-operator-skill)。

## 签名和实际操作风险

ad-hoc 签名替代**副本**的厂商签名；工具尽量保留现有标识符、entitlements、flags、runtime，签名元数据仍会变化。Gatekeeper、钥匙串、媒体/文件夹访问、账号、插件、网络功能可能有不同表现。签名验证不等于 Apple 公证、可用性或兼容性验证。若 macOS 要求确认，请由用户通过正常系统界面决定；工具不削弱安全策略。

`taskcenter` 将 `libVECreator.dylib` 文件偏移 `0x5f4df0c` 的 `289bff17` 改为 `c0035fd6`（ARM64 `ret`），只跳过完成回调尾部的一次任务列表刷新。其他刷新路径保留，任务弹窗行可能到下次重开才更新。普通工作优先保持任务弹窗关闭。回退时保存工程、正常退出实验副本，再打开保留的官方应用。

曾观察到导出面板同步枚举记忆的目录时阻塞。经官方应用的原生导出目录选择器改为可访问的本地目录后，副本导出恢复；OS 层根因未知。遇到类似情况，在原生界面选择新的本地导出目录，导出成功后复制到外置盘。不要盲目修改全局 plist，也不要将此配置绕行称为机器码补丁修复。

## 验证与发布范围

```bash
python3 -m unittest discover -s tests -v
```

单元测试使用临时假 `.app`，覆盖只读计划、源完整性、精确修改、无补丁对照、硬链接、符号链接、目标拒绝和额外字节损坏；音频比较测试还覆盖大于管道容量的损坏流诊断、错误输出限长、相同音频通过及改变增益拒绝。它们不模拟 Qt、原生任务调度或真实 codesign，不能替代运行和导出验证。

公开仓库只允许明确列出的原创 Python、ARM64 汇编、C 测试 harness、单元测试、Markdown、许可证与 `.gitignore`。生成 app、payload、manifest、对象文件与反汇编均留在本地输出目录，不发布。发布者应明确列出待提交文件并检查 staged tree；不加入应用包、动态库、项目、缓存、视频、原始采样日志、偏好文件或私人路径。MIT 仅覆盖本仓库原创内容，不授予第三方软件权利。
