# NEXT_STEPS — 自动续跑交接文档

> 这份文件是给「额度重置后自动续跑的会话」和学姐看的。每次新会话**先读完这份**，再按 §4 清单往下做。
> 项目根目录：`D:\2026春学期\AI_builder_rednote`　GitHub：`cfczh/Rednote-Encounter`

---

## 1. 项目当前真实状态（截至 2026-05-31）

项目已**从 BLE+文字 方案，转向 USB串口 + 逐帧PNG动画 + PCM语音 + 双人分屏(duel)** 方案。

两套并存的代码：
- **旧方案（我之前写的）**：`pc_ble_agent_bridge.py` + `cores3_encounter/cores3_encounter.ino`
  靠 BLE 广播测距 + GATT 回写文字。好感度/相遇2选一/WebSocket服务器都在这里。**保留作参考与 BLE 测距来源，但不再是主线。**
- **新方案（学姐 + zhang_agent_2）**：`animation.ino`（根目录）+ `zhang_agent_2/`
  靠 USB 串口，板子直接从 SD 读 PNG 播放，并能收 PCM 语音播放。**这是新主线。**

---

## 2. 学姐 animation.ino 评估（已读完 1532 行）

**保留（做得好的）：**
- SD 多速率挂载、PNG 直接 `drawPng` 播放（不用预转 jpg，省事）。
- Persona 存 NVS（`Preferences`），BtnA=zhang_zong / BtnB=xiao_hong 切换。
- 每 2s 串口上报 `PERSONA|<name>`，便于后端识别这台板子是谁。
- 串口协议清晰：
  - `PCM`/`PC2` + (PC2带4字节采样率) + 4字节长度 + 原始PCM → `M5.Speaker.playRaw` 播语音
  - `PERSONA|<name>` / `SEL|<name>` → 切人格
  - `DUEL|left|right|speaker|state|text` → 双人分屏（左 x=10 / 右 x=164，各 146x146 缩放0.48，黄框标当前说话者）
  - `TXT|<state>|<text>` → 单人模式，设状态+显示文字
- 状态目录 fallback：找不到 `<state>` 目录就回退 `idle`，不黑屏。
- 波特率 **2000000**（传 PCM 需要高速）。

**需要改进/注意：**
- 文件被某种工具格式化成「每个参数一行」，1532 行其实逻辑不多，**可读性差**。建议重新格式化（不改逻辑）。
- 状态命名要和 SD 卡目录、后端统一为：`idle / outdoor / meet / chat / leave`（见你最新的截图）。确认 `animationFolderPath(persona, state)` 拼出的路径与 SD 实际目录一致：SD 上是 `/<persona>/animations/<state>/`（如 `xiao_hong/animations/meet/`）。
- duel 文字超 22 字截断、单人 20 字截断 —— 中文够用但要知道。
- **没有 BLE**：靠近识别还得靠旧方案的 BLE，或上位机用别的方式判断两台靠近。

**⚠️ Git 问题（必须修）：**
- `persona-agent` 在仓库里是 **gitlink（mode 160000）但没有 .gitmodules** → 学姐那个文件夹里有嵌套 `.git`，导致**实际内容没上传**，远程只有一个空指针。
- 处理：让学姐进入 `persona-agent`，删掉里面的 `.git`，回到根目录 `git rm --cached persona-agent` 后重新 `git add persona-agent/`（作为普通文件夹）再提交。否则谁都拉不到她的后端代码。

---

## 3. SD 卡 / 动画素材现状

- 板子里 SD 卡目录（你截图）：`xiao_hong/animations/{chat,idle,leave,meet,outdoor}`、`zhang_zong/animations/{同上}`。**动画是逐帧 PNG，板子直接读。**
- 仓库 `animation_frame/` 里目前只有：`boss/Boss/` 11 张 PNG（张总表情），`hong/` 空。
- 已写好转换脚本 `tools/convert_frames.py`（缩放到320x240+连号+压<140KB），但**新方案板子直接读 PNG，不一定需要转**；保留脚本备用。
- 可用 Python：`C:\Users\fujisyuke\anaconda3\python.exe`（自带 Pillow 11）。系统 `python` 是 Store 占位符，不可用。
- 字体：`font/点点像素体-方形.ttf`(16MB) + Sixtyfour。**大字体不要进 git。**

---

## 4. 接下来要做的（按顺序，可勾选）

> 自动续跑时：**只改代码/素材并本地提交，不要 git push，不要烧录硬件**——push 和 flash 留给真人确认。

- [ ] **A. 修 gitlink**：确认 `persona-agent` 是否已被学姐修好；没修就在 NEXT_STEPS 里记一笔提醒，别自己乱动她的子模块。
- [ ] **B. 后端串口桥**：基于 `zhang_agent_2/zhang-agent/`（已有 `m5_audio.py`/`voice.py`/`duel.py`/`scripts/list_serial_ports.py`）整理出一个能跑的串口桥：
      列串口 → 连两台板子 → 按对话发 `TXT|state|text` 或 `DUEL|...` → TTS 生成 PCM 用 `PC2` 协议发给板子播。
- [ ] **C. 状态统一**：把所有地方的状态名统一成 `idle/outdoor/meet/chat/leave`。更新 `docs/PROTOCOL.md`。
- [ ] **D. 流程串通**：idle（待机）→ 蓝牙识别靠近 → outdoor（分屏出门）→ meet → chat（逐句对话+语音）→ leave（同屏离开）→ 回 idle。
- [ ] **E. WebSocket**：现在串口模拟，之后把传输层换成 WebSocket（板子 WiFi 客户端 + 后端服务器）。BLE 仅用于测距触发。
- [ ] **F. 素材**：等 UI 同学补齐 hong 各状态 PNG；需要转换时用 `tools/convert_frames.py`。

---

## 5. 安全/约定（每次都要守）
- **绝不提交** `.env`（含 API key）、`.venv/`、`__MACOSX/`、大字体、大媒体。`.gitignore` 已覆盖大部分。
- push、删除、烧录硬件 = 需真人确认，自动会话不要做。
- 中文文件存 UTF-8。
- 改完在本文件 §4 勾选进度，并在底部追加一行「续跑日志：<时间> 做了什么」。

---

## 6. 已确认的方向决策（人工拍板，自动会话须遵守）
- **续跑强度**：保守。每次会话只推进 1-2 项小改动就停，省额度。
- **旧 BLE 方案**：**保留**，作为「两台靠近」的测距/触发来源；新方案（USB串口+PNG+PCM）负责动画与语音。两者最终通过：BLE 判断靠近 → 触发后端 → 后端走串口/未来WebSocket 驱动板子动画+语音。
- 因此旧 `pc_ble_agent_bridge.py` / `cores3_encounter.ino` **不要归档、不要删**。

## 7. 编译 / 烧录速查（实测可用）
> Windows + arduino-cli 1.5.0，核心 `m5stack:esp32` 3.3.7，库 M5Unified/M5GFX 已装。

- **FQBN**：`m5stack:esp32:m5stack_cores3`
- **⚠️ build 路径不能含中文**：项目在 `D:\2026春学期\...`，GNU 链接器 `ld.exe` 在中文路径写 `.elf` 会乱码报 `cannot open output file`。
  解决：编译时用 `--build-path C:\m5build\xx`（纯英文）。源码可在中文路径（arduino-cli 会先把 .ino 拷进 build 目录）。
- **人格槽位**用编译宏区分：`--build-property "compiler.cpp.extra_flags=-DLOCAL_PERSONA_SLOT=0"`（0=xiao_hong，1=zhang_zong）。
- 两块板（都是 ESP32-S3 原生 USB，VID 303A）：
  - **COM3 = xiao_hong (slot 0)**，MAC 44:1b:f6:e1:fb:2c
  - **COM7 = zhang_zong (slot 1)**，MAC 44:1b:f6:e1:fc:10
- 命令示例：
  ```powershell
  $cli = "C:\Program Files\Arduino CLI\arduino-cli.exe"
  $sk  = "D:\2026春学期\AI_builder_rednote\cores3_encounter"
  & $cli compile --fqbn m5stack:esp32:m5stack_cores3 --build-path C:\m5build\xh --build-property "compiler.cpp.extra_flags=-DLOCAL_PERSONA_SLOT=0" $sk
  & $cli upload -p COM3 --fqbn m5stack:esp32:m5stack_cores3 --input-dir C:\m5build\xh $sk
  ```
- **分屏测试**：板子串口 115200，发一行 `DUEL|<left>|<right>|<speaker>|<state>|<text>`，
  例 `DUEL|xiao_hong|zhang_zong|zhang_zong|chat|hello`，进入分屏约 12 秒。
  收到会回显 `SERIAL DUEL: ...`。⚠️ cores3_encounter 文字气泡用默认字体，**中文会显示成方块**（动画 PNG 不受影响）——要中文气泡需换 efontCN 字体，留作后续。

## 续跑日志
- 2026-05-31 初始建立本文档（人工会话）。
- 2026-05-31 确认方向：续跑保守(每次1-2项)；旧BLE方案保留仅作测距用。
- 2026-05-31 修复分屏动画：cores3_encounter.ino 的 drawDuelScreen 原来用 drawDuelPanel() 程序画假小人(圆+线)，没读 SD 卡。已改为 drawDuelPersonaFrame() 逐帧读 /<persona>/animations/<state>/ 的 PNG，左右各维护目录句柄，SD 取不到才回退占位符；loop 刷帧扩展到分屏模式。commit b840851。
- 2026-05-31 编译并烧录两块板：COM3=xiao_hong(slot0)、COM7=zhang_zong(slot1)，hash 校验通过。串口实测 DUEL 命令解析正确、板子能成功 drawPng（anim ... PNG OK）。记录中文 build 路径坑 + 编译烧录速查于 §7。
- 2026-05-31 新增 BLE 自动分屏（commit 5bb1c4d）：两块板只要 BLE 探测到对方(REDNOTE- 名字)就自动进入并保持分屏，对方离开 12s 才退回单人；状态随距离 social=chat/visiting=meet/其余=outdoor。⚠️重要坑：128bit 服务 UUID 占满 31 字节广播包，厂商数据(personaId)被丢弃→扫描里 peer 列恒为 `--`，所以不能靠 personaId 识别对方，只能靠 BLE 名字前缀。已烧录两板并串口实测：开机首轮即 `[auto-duel] peer detected -> split screen (state=chat)`。
