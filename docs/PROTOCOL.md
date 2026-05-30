# 通信协议契约 (PROTOCOL.md)

本文件是硬件端(`cores3_encounter.ino`)与后端(`pc_ble_agent_bridge.py`)之间的**接口契约**。
两人分工开发时，任何一方要改这里的字段/常量，必须先在本文件改并通知对方，否则会扫不到 / 连不上。

- 标 ✅ **已实现** 的部分：当前代码就是这样，可直接联调。
- 标 🚧 **计划中** 的部分：尚未实现，是后续扩展的设计目标。

---

## 0. 整体架构

```
        BLE 广播(互相发现 + 测距)
   板子A  <-------------------->  板子B
     |                              |
     |  BLE 广播被后端扫描           |
     +--------------+---------------+
                    |
                后端 bridge (PC)
                    |
        BLE GATT 写回(文字 / #ACT 指令) / 🚧 WebSocket 推送
```

**两条链路，各司其职：**

| 链路 | 技术 | 方向 | 用途 |
|------|------|------|------|
| 设备发现 / 测距 | **BLE 广播** | 板子 ⇄ 板子，板子 → 后端 | 靠近感应、身份识别（**必须 BLE，WiFi 测不了物理距离**） |
| 指令 / 对话回传 | **BLE GATT** ✅ / **WebSocket** 🚧 | 后端 → 板子 | 把生成的一句话 / 动画指令推回板子 |

> 设计原则：**BLE 永远保留作为兜底**。WebSocket 是为了降延时的主通道，但线下现场 WiFi 不稳时要能退回 BLE。

---

## 1. BLE 基础常量 ✅

两端写死，必须完全一致。

| 名称 | 值 | 代码位置 |
|------|----|----|
| Service UUID | `7f1d2b10-7b6a-4f5d-9a46-202605260001` | `.ino` `peerServiceUuid` / `.py` `PROJECT_SERVICE_UUID` |
| Command Char UUID | `7f1d2b11-7b6a-4f5d-9a46-202605260001` | `.ino` `agentCommandCharUuid` / `.py` `AGENT_COMMAND_CHAR_UUID` |
| Company ID | `0xFFFF` | `.ino` `projectCompanyId` / `.py` `PROJECT_COMPANY_ID` |
| 协议魔数 | `"RN"` (0x52 0x4E) | manufacturer data 第 3-4 字节 |
| 协议版本 | `1` | `.ino` `projectProtocolVersion` |
| 设备名前缀 | `REDNOTE-` | `.ino` `peerNamePrefix` |

---

## 2. BLE 广播包格式（板子 → 外界）✅

板子通过 manufacturer data 广播自己的身份和状态，共 **11 字节**。

| 字节 | 字段 | 说明 |
|------|------|------|
| 0-1 | Company ID | `0xFF 0xFF`（小端） |
| 2-3 | 魔数 | `'R' 'N'` |
| 4 | version | 协议版本 = `1` |
| 5-6 | device_id | 设备 ID（小端，由 MAC 派生） |
| 7 | persona_id | 人格 ID（见 §3） |
| 8 | state | 社交状态 PeerState（见 §4） |
| 9 | gift_id | 特产 ID（见 §5） |
| 10 | flags + counter | 低 4 位 = 性格标志位；高 4 位 = 广播计数器 |

**flags 低 4 位定义：**
- bit0 = talkative（健谈）
- bit1 = slowWarm（慢热）
- bit2 = boundarySensitive（有边界感）

> 后端解析见 `parse_project_payload()`。注意后端拿到的 payload 可能已去掉前 2 字节 company id，解析时从 `RN` 开始对齐。

---

## 3. persona_id 映射 ✅🚧

| ID | 代号 | 状态 |
|----|------|------|
| 1 | xiao_hong（小红） | ✅ 已实现 |
| 2 | zhang_zong（张总） | ✅ 已实现 |
| 3 | bella | 🚧 预留 |
| 4 | zhangsheng | 🚧 预留 |

固件烧录槽位：`LOCAL_PERSONA_SLOT=0` → 小红，`=1` → 张总。
（slot 是数组下标，persona_id 是协议字段，**两者不要混用**。）

---

## 4. PeerState 社交状态（广播字段，state 字节）✅

这是板子**对外广播**的"我处于哪个社交阶段"，由 RSSI（距离）自动推算。

| 值 | 名称 | 含义 |
|----|------|------|
| 0 | idle | 空闲 |
| 1 | searching | 扫描周围 |
| 2 | visiting | 有人靠近 |
| 3 | social | 进入社交距离 |
| 4 | review | 互动回顾 |

**后端相遇触发规则** ✅：只有当 **双方** `state >= 3 (social)` 时才开始一段相遇，避免路过就浪费 API。

---

## 5. gift_id 特产映射 ✅

| ID | 名称 |
|----|------|
| 1 | game_snack |
| 2 | coffee |
| 3 | badge |

---

## 6. 后端 → 板子：GATT 写入（文字 + 动画指令）

后端连接目标板子，向 Command Char 写入。写入内容分**两类**，板子靠前缀区分。

### 6.1 普通对话文字 ✅
- 不带前缀的纯文本 = 要显示的一句话
- **编码**：UTF-8；**最大长度**：板子侧截断到 96 字节（约 30+ 汉字）
- **方向**：后端主动连接 → 写入 → 断开（write without response）
- 板子收到 → 切到 `ACTION_REPLY`，显示文字

### 6.2 动画指令（前缀 `#ACT:`）✅ 后端已发送 / 🚧 板子待解析
后端用 `#ACT:<name>` 告诉板子切到某个动作状态，**不当文字显示**。

| 指令字符串 | 含义 | 对应 ActionState |
|------------|------|------------------|
| `#ACT:encounter_gift` | 相遇·好感高·亮特产 | ACTION_ENCOUNTER（gift 动画组） |
| `#ACT:encounter_kick` | 相遇·好感低·踢人 | ACTION_ENCOUNTER（kick 动画组） |
| `#ACT:thinking` | 思考中（预留） | ACTION_THINKING |
| `#ACT:leave` | 谈话结束，回待机 | ACTION_COOLDOWN → idle |

> **硬件端 TODO（学姐）**：在 `AgentCommandCallbacks::onWrite` 里判断收到的字符串：
> 以 `#ACT:` 开头 → 解析动作名切状态/动画；否则按对话文字处理（现有逻辑）。
> `encounter_gift` / `encounter_kick` 对应两组相遇动画（亮特产 / 踢人），见设计图。

代码：`.py` `send_to_device()` / `cmd_encounter()` → `.ino` `AgentCommandCallbacks`。

---

## 7. 固件内部 ActionState（动画状态机，不广播）✅

⚠️ **这与 §4 的 PeerState 是两套不同的东西**：
- PeerState = 对外广播的社交阶段（idle/searching/.../review）
- ActionState = 板子内部的动画/动作状态，**只在本机用，不进 BLE**

| 状态 | 触发条件 | 动画目录 |
|------|----------|----------|
| ACTION_SEARCHING | 无活跃 peer | `/cores3_assets/animations/searching/` |
| ACTION_NEAR | best RSSI ≥ visitingRssi | `/animations/near/` |
| ACTION_ENCOUNTER | RSSI ≥ socialRssi 或重复出现 或 单击触发 或收到 `#ACT:encounter_*` | `/animations/encounter/` |
| ACTION_THINKING | 进入相遇后，等待后端回复 | `/animations/thinking/` |
| ACTION_REPLY | 收到后端回写的文本 | `/animations/reply/` |
| ACTION_COOLDOWN | REPLY 展示完 / 超时 / 收到 `#ACT:leave` | `/animations/cooldown/` |

关键时间常量（`.ino`）：
- REPLY 展示时长 `kReplyShowMs = 10000`
- COOLDOWN 时长 `kCooldownMs = 15000`
- THINKING 超时 `kThinkingTimeoutMs = 15000`
- ENCOUNTER 触发冷却 `kEncounterCooldownMs = 20000`

> 🚧 **待打通**：进入 ACTION_ENCOUNTER 时，把广播的 PeerState 同步设为 social(3)，让"屏幕触发相遇"与"后端调 LLM"对齐到同一时刻。

---

## 8. SD 卡资源目录契约 ✅🚧

UI / 动画同学按此目录交付。缺文件时板子有 fallback（色块 / 线条 / tone），**不会黑屏**。

```
/cores3_assets/
  personas/
    xiao_hong/avatar.png
    zhang_zong/avatar.png
  animations/
    searching/frame_0001.jpg, frame_0002.jpg, ...
    near/frame_0001.jpg ...
    encounter/frame_0001.jpg ...     # 亮特产 / 踢人两组，命名待与硬件约定
    thinking/frame_0001.jpg ...
    reply/frame_0001.jpg ...
    cooldown/frame_0001.jpg ...
  audio/
    close.wav    # ENCOUNTER 确认音
    reply.wav    # REPLY 提示音
    error.wav    # 错误提示音
```

- 帧文件名：`frame_%04u.jpg`（从 0001 起，连续编号，播完循环）
- 单帧建议 < 140 KB（板子内存限制）
- 头像 PNG 建议 < 120 KB

---

## 9. 后端相遇会话流程（已实现）✅

后端为每一对设备维护一个 `EncounterSession`，驱动设计图那条时间线：

```
双方都 social(state>=3)
   │
   ▼
[encounter]  算好感度 favorability() -> mode(gift/kick)
             下发 #ACT:encounter_<mode> 给两台板子
   │  (下一轮)
   ▼
[chatting]   每轮生成双人对话(各一句)，下发文字
             带好感度 + mode + 第几句 给 LLM 当上下文
   │
   ▼  结束条件：对话满 MAX_TURNS=4 句  或  对方离开(>12s 没出现)
[ended]      下发 #ACT:leave；清空对话记忆；进入 PAIR_COOLDOWN=25s
```

**好感度算法 `favorability()`**（0-100，对称）：
- 人格基础分（小红×张总 = 38，其余默认 50）
- 任一方带特产 +6
- 有边界感的人遇到话痨 −12；两个话痨 +6
- `>=50` → `gift`(亮特产)，`<50` → `kick`(踢人)

可调参数（`.py` 顶部）：`AFFINITY_THRESHOLD=50`、`MAX_TURNS=4`、`PAIR_LOST_AFTER=12`、`PAIR_COOLDOWN=25`。

---

## 10. 🚧 计划中：WebSocket 通道（降延时）

> 目标：把"后端 → 板子"的回传从 BLE GATT（每次重连 0.5~2s）换成 WiFi WebSocket 长连接（毫秒级）。BLE 广播测距**保持不变**。
> 后端已内置一个**基础 WebSocket 服务器**（`ws://0.0.0.0:8765`），目前用于**广播事件给调试前端**；板子 WiFi 客户端尚未实现。

### 10.1 后端已广播的事件（板子/前端可订阅）
```json
{ "type": "encounter", "a": "A1B2", "b": "C3D4", "affinity": 38, "mode": "kick" }
{ "type": "reply", "device": "A1B2", "turn": 2, "text": "来了就别磨蹭。" }
{ "type": "leave", "a": "A1B2", "b": "C3D4", "reason": "turns" }
```

### 10.2 🚧 未来板子 → 后端（上报，待实现）
```json
{ "type": "hello", "device_id": "A1B2", "persona_id": 1 }
{ "type": "encounter", "device_id": "A1B2", "peer_id": "C3D4", "rssi": -55 }
```

### 10.3 待定决策（设计图里的红字问题）
- [ ] 回复返回**文字** / **语音** / 两者都要？（现状只有文字）
- [ ] 谈话结束判定：现用 **句数(4)** + **离开**；是否还要加"离开一定距离"？
- [x] 相遇动画 2 选一由**后端好感度逻辑**决定，通过 `#ACT:encounter_*` 下发 ✅

---

## 11. 分工边界（避免 git 冲突）

| 负责人 | 主要文件 | 内容 |
|--------|----------|------|
| 偏后端/通信 | `pc_ble_agent_bridge.py` | ✅ 持续扫描、✅ 好感度逻辑、✅ 相遇动画 2 选一、✅ 谈话结束判定、✅ WebSocket 服务器(基础) |
| 偏硬件/交互 | `cores3_encounter.ino` | 🚧 解析 `#ACT:` 动画指令(§6.2)、动画对接、声音/表情库、状态衔接节奏、🚧 WebSocket 客户端 |
| 共同维护 | **本文件 PROTOCOL.md** | BLE 字段、`#ACT:` 指令、WebSocket 消息格式、SD 目录 —— **改前先对齐** |

### 后端本次已完成

- **持续扫描**：`BleakScanner(detection_callback=...)` 替代每轮 `discover(4s)`，循环间隔 0.6s，发现延时大幅下降。
- **好感度逻辑**：`favorability()` + `favorability_mode()`（见 §9）。
- **相遇 2 选一**：下发 `#ACT:encounter_gift` / `#ACT:encounter_kick`。
- **会话状态机**：`EncounterSession`（encounter → chatting → ended）。
- **谈话结束判定**：满 4 句或对方离开 → `#ACT:leave`，并清空该对的对话记忆。
- **WebSocket 服务器**：`ws://0.0.0.0:8765`，广播 encounter / reply / leave（缺 `websockets` 库自动跳过，不影响 BLE）。

**约定**：两人各刷一块板（slot 0 / slot 1），凑近即可真机联调"相遇"全流程。
