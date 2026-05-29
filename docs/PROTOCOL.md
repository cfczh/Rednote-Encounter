# 通信协议契约 (PROTOCOL.md)

本文件是硬件端(`cores3_encounter.ino`)与后端(`pc_ble_agent_bridge.py`)之间的**接口契约**。
两人分工开发时，任何一方要改这里的字段/常量，必须先在本文件改并通知对方，否则会扫不到 / 连不上。

- 标 ✅ **已实现** 的部分：当前代码就是这样，可直接联调。
- 标 🚧 **计划中** 的部分：尚未实现，是 WebSocket 扩展的设计目标。

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
        BLE GATT 写回一句话 / 🚧 WebSocket 推送
```

**两条链路，各司其职：**

| 链路 | 技术 | 方向 | 用途 |
|------|------|------|------|
| 设备发现 / 测距 | **BLE 广播** | 板子 ⇄ 板子，板子 → 后端 | 靠近感应、身份识别（**必须 BLE，WiFi 测不了物理距离**） |
| 指令 / 对话回传 | **BLE GATT** ✅ / **WebSocket** 🚧 | 后端 → 板子 | 把生成的一句话 / 状态推回板子显示 |

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

**后端 LLM 触发规则** ✅：只有当对方 `state >= 3 (social)` 时才调用大模型，避免路过就浪费 API。

---

## 5. gift_id 特产映射 ✅

| ID | 名称 |
|----|------|
| 1 | game_snack |
| 2 | coffee |
| 3 | badge |

---

## 6. 后端 → 板子：回写一句话（BLE GATT）✅

后端生成回复后，连接目标板子，向 Command Char 写入。

- **编码**：UTF-8
- **最大长度**：板子侧截断到 96 字节（约 30+ 汉字）
- **方向**：后端主动连接 → 写入 → 断开（write without response）
- **板子接收**：`AgentCommandCallbacks::onWrite` → 触发 `ACTION_REPLY` 状态

代码：`.py` `write_agent_reply()` → `.ino` `AgentCommandCallbacks`。

---

## 7. 固件内部 ActionState（动画状态机，不广播）✅

⚠️ **这与 §4 的 PeerState 是两套不同的东西**：
- PeerState = 对外广播的社交阶段（idle/searching/.../review）
- ActionState = 板子内部的动画/动作状态，**只在本机用，不进 BLE**

| 状态 | 触发条件 | 动画目录 |
|------|----------|----------|
| ACTION_SEARCHING | 无活跃 peer | `/cores3_assets/animations/searching/` |
| ACTION_NEAR | best RSSI ≥ visitingRssi | `/animations/near/` |
| ACTION_ENCOUNTER | RSSI ≥ socialRssi 或重复出现 或 单击触发 | `/animations/encounter/` |
| ACTION_THINKING | 进入相遇后，等待后端回复 | `/animations/thinking/` |
| ACTION_REPLY | 收到后端回写的文本 | `/animations/reply/` |
| ACTION_COOLDOWN | REPLY 展示完 / 超时 | `/animations/cooldown/` |

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
    encounter/frame_0001.jpg ...
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

## 9. 🚧 计划中：WebSocket 通道（降延时）

> 目标：把"后端 → 板子"的回传从 BLE GATT（每次重连 0.5~2s）换成 WiFi WebSocket 长连接（毫秒级），并支持后端主动推送多种事件。BLE 广播测距**保持不变**。

### 9.1 连接

- 板子开机连 WiFi，作为 WebSocket **客户端**连到后端服务器
- 后端跑 WebSocket **服务器**（如 `websockets` 库），监听板子上报
- 消息格式：**JSON 文本帧**

### 9.2 板子 → 后端（上报）

```json
{
  "type": "encounter",
  "device_id": "A1B2",
  "persona_id": 1,
  "peer_id": "C3D4",
  "peer_persona_id": 2,
  "rssi": -55,
  "state": 3
}
```

`type` 取值（建议）：`hello`（上线）/ `encounter`（相遇）/ `heartbeat`（心跳）/ `left`（离开）

### 9.3 后端 → 板子（推送）

```json
{ "type": "set_action", "action": "thinking" }
{ "type": "reply", "text": "那好吧，待一会儿。", "voice_url": null }
{ "type": "emote", "emote": "wave" }
{ "type": "leave" }
```

`type` 取值（建议）：
- `set_action` — 直接切动画状态
- `reply` — 显示一句话（未来可带 `voice_url` / `voice_len` 支持语音）
- `emote` — 中途触发动作库/表情
- `leave` — 后端判定谈话结束，板子回 idle

### 9.4 待定决策（设计图里的红字问题）

- [ ] 回复返回**文字** / **语音** / 两者都要？（现状只有文字）
- [ ] 谈话结束判定：**离开一定距离** / **固定对话句数** / 两者都行？
- [ ] 相遇动画 2 选一（亮特产 ≥50 好感 / 踢人 <50）由谁判定 → 应在**后端好感度逻辑**里决定，通过 `set_action` 下发

---

## 10. 分工边界（避免 git 冲突）

| 负责人 | 主要文件 | 内容 |
|--------|----------|------|
| 偏后端/通信 | `pc_ble_agent_bridge.py` | 持续扫描、好感度逻辑、相遇动画 2 选一、谈话结束判定、🚧 WebSocket 服务器 |
| 偏硬件/交互 | `cores3_encounter.ino` | 动画对接、声音/表情库、状态衔接节奏、🚧 WebSocket 客户端 |
| 共同维护 | **本文件 PROTOCOL.md** | BLE 字段、WebSocket 消息格式、SD 目录 —— **改前先对齐** |

**约定**：两人各刷一块板（slot 0 / slot 1），凑近即可真机联调"相遇"全流程。
