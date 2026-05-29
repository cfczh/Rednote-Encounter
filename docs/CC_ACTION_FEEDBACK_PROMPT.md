# CC Prompt: Hardware Action And Feedback Loop

Copy the text below into CC as plain text. Do not attach images.

```text
项目背景：
我们在做一个 M5Stack CoreS3 的线下“人格相遇”硬件原型。两台或多台 M5 设备代表不同人格，例如小红、张总、Bella、Zhangsheng。设备之间通过 BLE 广播发现彼此，根据距离/RSSI 进入不同互动状态。PC 端 bridge 扫描这些 BLE peer，在合适状态下调用人格 agent/LLM，然后把一句短回复写回对应 M5 屏幕。

我的分工不是 UI 设计。我主要负责硬件端和后端 bridge/agent。UI/动画资源会由别人提供，所以你不要重点做视觉设计，而是帮我把硬件和后端的动作反馈闭环搭好，并明确资源接口。

请读取当前项目代码，重点看：
- cores3_encounter/cores3_encounter.ino
- pc_ble_agent_bridge.py
- RUNBOOK.md
- flash_xiao_hong.ps1
- flash_zhang_zong.ps1
- run_bridge.ps1
- xiao_hong/xiao_hong/
- zhang_zong_skill/

当前代码大致现状：
1. M5 固件已经能通过 BLE 广播 persona/state/gift。
2. M5 固件已经能扫描附近 REDNOTE/M5 peer，根据 RSSI 显示 CLOSE/NEAR/FAR。
3. M5 固件已有屏幕显示、声音反馈、SD 卡资源读取的基础。
4. PC bridge 已经能扫描 peer，解析 manufacturer data，调用 LLM，然后通过 BLE GATT 写一句回复回 M5。
5. 但当前代码还不是完整的“动作和动画反馈”系统：
   - 没有清晰的 action state machine。
   - 触摸交互只是简单切换 filter/video。
   - bridge 调用 LLM 的时机比较粗糙。
   - pc_ble_agent_bridge.py 里中文 prompt 明显乱码，需要修复。
   - SD 卡动画资源路径还不够规范。
   - UI/动画文件目前还没提供，所以硬件端必须有 fallback 逻辑。

核心目标：
不要重写整个项目。请保留现有 BLE 协议、UUID、烧录脚本、persona slot、bridge 主流程。重点改硬件端状态机、bridge 调用规则、agent prompt 编码、资源接口和 fallback。

需要你完成的事情：

1. 代码评估
- 判断哪些现有代码应该保留，哪些应该重构。
- 默认保留：
  - BLE service UUID 和 characteristic UUID
  - manufacturer data 协议
  - LOCAL_PERSONA_SLOT=0/1 的烧录方式
  - flash_xiao_hong.ps1 / flash_zhang_zong.ps1
  - run_bridge.ps1
  - PC bridge 扫描和写回 M5 的主链路
- 可以重构：
  - M5 端状态判断逻辑
  - M5 端触摸交互逻辑
  - M5 端资源路径和加载逻辑
  - bridge 调用 LLM 的触发条件
  - prompt/fallback 文案

2. 实现硬件动作状态机
请在 M5 固件里增加明确的动作状态，至少包括：
- ACTION_SEARCHING：没有发现活跃 peer
- ACTION_NEAR：发现 peer，但还没触发正式相遇
- ACTION_ENCOUNTER：距离足够近或 repeated nearby，触发相遇动作
- ACTION_THINKING：已经触发 bridge/agent，等待回复
- ACTION_REPLY：收到 bridge 写回的 agent reply
- ACTION_COOLDOWN：互动结束后的冷却期，避免重复触发

建议转换规则：
- active peer 数量为 0 -> SEARCHING
- bestRssi >= visitingRssi -> NEAR
- bestRssi >= socialRssi 或 seenCount >= 3 -> ENCOUNTER
- 进入 ENCOUNTER 后可以进入 THINKING，等待 bridge 回复
- BLE GATT 收到 agent text -> REPLY
- REPLY 展示 8-12 秒 -> COOLDOWN
- COOLDOWN 结束后根据当前 peer 距离回到 NEAR 或 SEARCHING

3. 优化 bridge 调用规则
目前 bridge 看到两个 active peer 就可能调用 LLM。请改成更适合硬件互动的规则：
- SEARCHING/NEAR 不频繁调用 LLM
- 只有 ENCOUNTER 或明确触发事件时调用 LLM
- 同一对 peer 要有 cooldown，例如 20-30 秒内不重复调用
- 如果设备处于 COOLDOWN，不调用 LLM
- bridge 日志要清楚打印：
  - 当前 active peers
  - 每个 peer 的 persona/state/rssi
  - 为什么调用或跳过 LLM
  - 写回哪台设备、写入什么文本

4. 修复 pc_ble_agent_bridge.py 中文乱码
这个文件里现在很多中文 prompt、event、fallback 文案是乱码。请改成正常 UTF-8 中文。
要求：
- 小红 prompt：慢热、有边界感、简短、不要突然热情。
- 张总 prompt：直接、有压迫感但不要长篇训话。
- 每次回复限制为适合 M5 小屏的一句话，建议 10-16 个中文字符以内。
- fallback 回复也必须是正常中文或可读 ASCII。
- 保存文件为 UTF-8。

5. 规范人格/agent 文件接口
请检查现有：
- xiao_hong/xiao_hong/
- zhang_zong_skill/
并整理 bridge 如何读取这些人格文件。
如果当前文件可用，就继续使用。
如果有路径混乱或编码问题，请修复。
请保留 persona id 映射：
- 1 = xiao_hong
- 2 = zhang_zong
并预留扩展：
- 3 = bella
- 4 = zhangsheng

6. 规范 UI/动画资源接口，但不要重点做 UI
UI 动画资源会由别人提供。请只在硬件端定义清楚资源目录和 fallback。
建议 SD 卡目录：
- /cores3_assets/personas/xiao_hong/avatar.png
- /cores3_assets/personas/zhang_zong/avatar.png
- /cores3_assets/animations/searching/frame_0001.jpg
- /cores3_assets/animations/near/frame_0001.jpg
- /cores3_assets/animations/encounter/frame_0001.jpg
- /cores3_assets/animations/thinking/frame_0001.jpg
- /cores3_assets/animations/reply/frame_0001.jpg
- /cores3_assets/animations/cooldown/frame_0001.jpg
- /cores3_assets/audio/close.wav
- /cores3_assets/audio/reply.wav
- /cores3_assets/audio/error.wav

要求：
- 没有 SD 卡或没有动画文件时，M5 仍然能跑完整状态流程。
- fallback 可以是简单文字、色块、像素方块、基础 tone 声音。
- 不要因为资源缺失导致黑屏或卡死。
- 串口要打印哪些资源加载成功/缺失。

7. 触摸交互
请重写触摸逻辑：
- 单击：手动触发一次 ENCOUNTER 或重新聚焦最近 peer
- 双击：打开/关闭 debug overlay
- 长按：切换 peerOnlyMode
如果双击实现复杂，可以先实现单击和长按，但要把结构留好。

8. 声音反馈
保留现有 close.wav/repeat.wav 或迁移到新 audio 路径。
每个动作状态有不同声音策略：
- SEARCHING：默认不响
- NEAR：轻提示，可限制频率
- ENCOUNTER：短促确认音
- REPLY：明显提示音
- ERROR：错误提示音
必须有 cooldown，避免一直响。

9. Debug overlay / 串口调试
请增加或整理调试输出：
M5 屏幕 debug overlay 至少显示：
- persona
- device id
- current action state
- best peer
- best RSSI
- peerOnlyMode
- sdReady
- last agent reply

串口日志至少显示：
- BLE scan round
- self persona/state/action
- active peers
- state transition
- resource load result
- received agent command

10. 验证
现在不一定有 CoreS3 硬件在身边。请尽量做到：
- 不依赖硬件实测也能完成代码层修改
- 如果 arduino-cli 可用，尝试 compile：
  - LOCAL_PERSONA_SLOT=0
  - LOCAL_PERSONA_SLOT=1
- 如果不能编译，说明原因和需要的命令
- 不要破坏现有 flash 脚本

最终输出：
- 修改了哪些文件
- 保留了哪些旧逻辑
- 新增了哪些 action states
- bridge 什么时候调用/跳过 LLM
- UI/动画同学需要提供哪些资源文件
- 硬件实测 checklist

注意：
- 不要把任务变成做手机 UI。
- 不要依赖图片输入。
- 不要删除现有 BLE/bridge 主链路。
- 不要大改无关文件。
- 中文文件保存为 UTF-8。
- 核心目标是：在 UI 动画资源尚未到位、硬件暂时不在身边的情况下，先把硬件动作状态机、后端调用规则、资源接口和 fallback 跑通。
```
