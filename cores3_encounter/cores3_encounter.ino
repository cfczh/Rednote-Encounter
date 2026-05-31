#include <Arduino.h>
#include <M5Unified.h>
#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include <BLEServer.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEUtils.h>
#include <SD.h>
#include <SPI.h>

#include <algorithm>
#include <math.h>
#include <vector>

enum PeerState : uint8_t {
  PEER_IDLE = 0,
  PEER_SEARCHING = 1,
  PEER_VISITING = 2,
  PEER_SOCIAL = 3,
  PEER_REVIEW = 4,
};

enum ActionState : uint8_t {
  ACTION_SEARCHING = 0,
  ACTION_NEAR      = 1,
  ACTION_ENCOUNTER = 2,
  ACTION_THINKING  = 3,
  ACTION_REPLY     = 4,
  ACTION_COOLDOWN  = 5,
};

void playSoundForAction(ActionState action);

struct PeerBroadcast {
  bool valid = false;
  uint8_t version = 0;
  uint16_t deviceId = 0;
  uint8_t personaId = 0;
  uint8_t state = PEER_IDLE;
  uint8_t giftId = 0;
  uint8_t flags = 0;
  uint8_t counter = 0;
};

struct PersonaConfig {
  uint8_t id;
  uint8_t giftId;
  bool talkative;
  bool slowWarm;
  bool boundarySensitive;
  int visitingRssi;
  int socialRssi;
  const char* codeName;
  const char* shortName;
  const char* archetype;
  const char* giftName;
  const char* searchLine;
  const char* visitLine;
  const char* socialLine;
  const char* reviewLine;
};

struct Encounter {
  String id;
  String name;
  int rssi = -127;
  uint16_t seenCount = 0;
  uint32_t firstSeenMs = 0;
  uint32_t lastSeenMs = 0;
  bool projectPeer = false;
  PeerBroadcast peer;
};

std::vector<Encounter> encounters;
BLEScan* scanner = nullptr;
BLEAdvertising* advertiser = nullptr;
BLEServer* peerServer = nullptr;
BLECharacteristic* agentCommandCharacteristic = nullptr;
String localBleName;

bool socialMode = false;
bool peerOnlyMode = true;
uint16_t localDeviceId = 0;
uint8_t localAdvertiseCounter = 0;
uint32_t lastAdvertiseUpdateMs = 0;
String pendingAgentText;
String pendingActionCmd;          // 收到的 #ACT:<name> 指令名（去掉前缀）
uint32_t actionHoldUntilMs = 0;   // bridge 强制动作后，暂停本地 RSSI 状态机到此刻
String lastAgentText;
uint32_t lastAgentTextMs = 0;
bool duelMode = false;
String duelLeft;
String duelRight;
String duelSpeaker;
String duelText;
String duelState;
uint32_t duelUntilMs = 0;
bool autoDuelEnabled = true;       // BLE 探测到对方时自动进入并保持分屏
uint32_t serialDuelUntilMs = 0;    // 串口 DUEL 命令的优先窗口（此期间不被自动分屏覆盖）
const uint32_t kPeerFreshMs = 12000;   // 对方多久没刷新就视为离开（退出分屏）
const uint32_t kAutoDuelKeepMs = 8000; // 探测到对方时分屏保活时长（> 扫描间隔即可）
uint32_t lastScanMs = 0;
uint32_t lastDrawMs = 0;
uint32_t lastSoundMs = 0;
ActionState currentAction = ACTION_SEARCHING;
uint32_t actionEnteredMs = 0;
uint32_t lastEncounterTriggerMs = 0;
bool manualEncounterTrigger = false;
bool debugOverlay = false;
uint32_t lastTapMs = 0;
uint8_t tapCount = 0;
uint32_t scanRound = 0;
bool sdReady = false;
uint8_t* closeWav = nullptr;
uint8_t* repeatWav = nullptr;
size_t closeWavLen = 0;
size_t repeatWavLen = 0;
uint8_t* avatarPng = nullptr;
size_t avatarPngLen = 0;
bool hasVideoFrames = false;
bool videoMode = false;
uint16_t videoFrame = 1;
uint32_t lastVideoMs = 0;
uint32_t lastSdRetryMs = 0;
uint32_t sdMountSpeed = 0;

const uint16_t kBg = 0x0841;
const uint16_t kInk = 0xEF7D;
const uint16_t kDim = 0x6B4D;
const uint16_t kAmber = 0xFDC0;
const uint16_t kMint = 0x5FF5;
const uint16_t kHot = 0xF9E7;
const uint16_t kBlue = 0x4D7F;

const uint32_t scanIntervalMs = 6000;
const uint32_t staleAfterMs = 45000;
const uint32_t forgetAfterMs = 180000;
const int minShownRssi = -82;
const int maxRadarDevices = 8;
const char* peerServiceUuid = "7f1d2b10-7b6a-4f5d-9a46-202605260001";
const char* agentCommandCharUuid = "7f1d2b11-7b6a-4f5d-9a46-202605260001";
const char* peerNamePrefix = "REDNOTE-";
const uint16_t projectCompanyId = 0xFFFF;
const uint8_t projectProtocolVersion = 1;
#ifndef LOCAL_PERSONA_SLOT
#define LOCAL_PERSONA_SLOT 0
#endif

const uint8_t localPersonaSlot = LOCAL_PERSONA_SLOT;  // 0 = xiao_hong, 1 = zhang_zong.
const PersonaConfig personaConfigs[] = {
  {
    1,
    1,
    false,
    true,
    true,
    -66,
    -54,
    "xiao_hong",
    "XH",
    "quiet penguin",
    "game-snack",
    "watching quietly...",
    "maybe say hi?",
    "OKOK, stay a bit.",
    "needs a little space."
  },
  {
    2,
    2,
    true,
    false,
    false,
    -70,
    -60,
    "zhang_zong",
    "ZZ",
    "factory boss",
    "coffee",
    "checking the floor...",
    "come report.",
    "say it directly.",
    "make a summary."
  }
};
const PersonaConfig& localPersona = personaConfigs[localPersonaSlot];

const int sdCsPin = 4;
const int sdSckPin = 36;
const int sdMisoPin = 35;
const int sdMosiPin = 37;
const char* assetDir      = "/cores3_assets";
const char* avatarPath    = "/cores3_assets/avatar.png";
const char* closeWavPath  = "/cores3_assets/close.wav";
const char* repeatWavPath = "/cores3_assets/repeat.wav";
const char* videoDir      = "/cores3_assets/video";

// 把内部动作状态映射到 SD 卡上的动画子目录名（与设计图/SD 结构一致）。
// idle(待机) / meet(靠近未开聊) / outdoor(开聊前转场) / chat(对话中) / leave(结束)
const char* actionStateFolder(ActionState action) {
  switch (action) {
    case ACTION_SEARCHING: return "idle";
    case ACTION_NEAR:      return "meet";
    case ACTION_ENCOUNTER: return "outdoor";
    case ACTION_THINKING:  return "outdoor";
    case ACTION_REPLY:     return "chat";
    case ACTION_COOLDOWN:  return "leave";
    default:               return "idle";
  }
}

// 完整动画目录：/<persona>/animations/<state>，如 /xiao_hong/animations/idle
const char* actionAnimDir(ActionState action) {
  static char buf[64];
  snprintf(buf, sizeof(buf), "/%s/animations/%s",
           localPersona.codeName, actionStateFolder(action));
  return buf;
}

// 把 #ACT:<name> 指令名映射回内部动作状态。
bool actionFromName(const String& name, ActionState* out) {
  if (name == "idle")    { *out = ACTION_SEARCHING; return true; }
  if (name == "meet")    { *out = ACTION_NEAR;      return true; }
  if (name == "outdoor") { *out = ACTION_ENCOUNTER; return true; }
  if (name == "chat")    { *out = ACTION_REPLY;     return true; }
  if (name == "leave")   { *out = ACTION_COOLDOWN;  return true; }
  // 兼容旧 bridge 指令
  if (name.startsWith("encounter")) { *out = ACTION_ENCOUNTER; return true; }
  if (name == "thinking") { *out = ACTION_THINKING; return true; }
  return false;
}

String proximityLabel(int rssi) {
  if (rssi >= -55) return "CLOSE";
  if (rssi >= -72) return "NEAR";
  return "FAR";
}

uint16_t proximityColor(int rssi) {
  if (rssi >= -55) return kHot;
  if (rssi >= -72) return kAmber;
  return kMint;
}

int bestRssi() {
  int best = -127;
  uint32_t now = millis();
  for (const auto& item : encounters) {
    if (now - item.lastSeenMs <= staleAfterMs) {
      best = max(best, item.rssi);
    }
  }
  return best;
}

String shortId(const String& id) {
  if (id.length() <= 8) return id;
  return id.substring(id.length() - 8);
}

String localPeerName() {
  uint64_t mac = ESP.getEfuseMac();
  char suffix[5];
  snprintf(suffix, sizeof(suffix), "%04X", (uint16_t)(mac & 0xFFFF));
  return String(peerNamePrefix) + suffix;
}

uint16_t makeLocalDeviceId() {
  uint64_t mac = ESP.getEfuseMac();
  return (uint16_t)((mac & 0xFFFF) ^ ((mac >> 16) & 0xFFFF));
}

const char* personaName(uint8_t personaId) {
  switch (personaId) {
    case 1: return "xiao_hong";
    case 2: return "zhang_zong";
    default: return "unknown";
  }
}

const char* stateName(uint8_t state) {
  switch (state) {
    case PEER_IDLE: return "idle";
    case PEER_SEARCHING: return "search";
    case PEER_VISITING: return "visit";
    case PEER_SOCIAL: return "social";
    case PEER_REVIEW: return "review";
    default: return "?";
  }
}

const char* actionStateName(ActionState action) {
  switch (action) {
    case ACTION_SEARCHING: return "SEARCHING";
    case ACTION_NEAR:      return "NEAR";
    case ACTION_ENCOUNTER: return "ENCOUNTER";
    case ACTION_THINKING:  return "THINKING";
    case ACTION_REPLY:     return "REPLY";
    case ACTION_COOLDOWN:  return "COOLDOWN";
    default:               return "?";
  }
}

const char* giftName(uint8_t giftId) {
  switch (giftId) {
    case 1: return "game-snack";
    case 2: return "coffee";
    case 3: return "badge";
    default: return "none";
  }
}

const char* localPersonaLine(PeerState state) {
  switch (state) {
    case PEER_VISITING: return localPersona.visitLine;
    case PEER_SOCIAL: return localPersona.socialLine;
    case PEER_REVIEW: return localPersona.reviewLine;
    case PEER_IDLE:
    case PEER_SEARCHING:
    default: return localPersona.searchLine;
  }
}

PeerState localPeerState() {
  int best = bestRssi();
  if (best >= localPersona.socialRssi) return PEER_SOCIAL;
  if (best >= localPersona.visitingRssi) return PEER_VISITING;
  return PEER_SEARCHING;
}

const uint32_t kReplyShowMs         = 10000;
const uint32_t kCooldownMs          = 4000;
const uint32_t kThinkingTimeoutMs   = 15000;
const uint32_t kEncounterCooldownMs = 20000;

void transitionAction(ActionState next) {
  if (currentAction == next) return;
  Serial.printf("[action] %s -> %s\n", actionStateName(currentAction), actionStateName(next));
  currentAction = next;
  actionEnteredMs = millis();
  videoFrame = 1;
  if (next == ACTION_ENCOUNTER || next == ACTION_REPLY) {
    playSoundForAction(next);
  }
}

void updateActionState() {
  uint32_t now = millis();
  int best   = bestRssi();
  int active = activeCount();

  // bridge 下发的 #ACT 指令优先：强制切动画，并暂停本地 RSSI 状态机一段时间
  if (pendingActionCmd.length()) {
    ActionState target;
    if (actionFromName(pendingActionCmd, &target)) {
      transitionAction(target);
      actionHoldUntilMs = now + (target == ACTION_COOLDOWN ? 4000 : 12000);
    }
    pendingActionCmd = "";
    return;
  }

  // 处于 bridge 强制动作的保持窗口内，不让本地逻辑覆盖
  if (now < actionHoldUntilMs) return;

  if (pendingAgentText.length()) {
    pendingAgentText = "";
    transitionAction(ACTION_REPLY);
    return;
  }

  switch (currentAction) {
    case ACTION_SEARCHING:
      if (active > 0 && best >= localPersona.visitingRssi) {
        transitionAction(ACTION_NEAR);
      } else if (manualEncounterTrigger && active > 0) {
        manualEncounterTrigger = false;
        transitionAction(ACTION_ENCOUNTER);
      }
      break;

    case ACTION_NEAR:
      if (active == 0 || best < localPersona.visitingRssi) {
        transitionAction(ACTION_SEARCHING);
      } else if (best >= localPersona.socialRssi || activeRepeatedCount() >= 1 || manualEncounterTrigger) {
        manualEncounterTrigger = false;
        if (now - lastEncounterTriggerMs > kEncounterCooldownMs) {
          transitionAction(ACTION_ENCOUNTER);
        }
      }
      break;

    case ACTION_ENCOUNTER:
      lastEncounterTriggerMs = now;
      transitionAction(ACTION_THINKING);
      break;

    case ACTION_THINKING:
      if (now - actionEnteredMs > kThinkingTimeoutMs) {
        transitionAction(ACTION_COOLDOWN);
      }
      break;

    case ACTION_REPLY:
      if (now - actionEnteredMs > kReplyShowMs) {
        transitionAction(ACTION_COOLDOWN);
      }
      break;

    case ACTION_COOLDOWN:
      if (now - actionEnteredMs > kCooldownMs) {
        if (best >= localPersona.visitingRssi) {
          transitionAction(ACTION_NEAR);
        } else {
          transitionAction(ACTION_SEARCHING);
        }
      }
      break;
  }
  manualEncounterTrigger = false;
}

// 是否近期(kPeerFreshMs)探测到另一块项目板。
// 注意：128-bit 服务 UUID 占满广播包，厂商数据(含 personaId)常被丢弃，
// 所以不能依赖 peer.personaId；改用「项目板特征」判断：
//   - projectPeer（成功解析到厂商数据时）或
//   - BLE 名字以 REDNOTE- 开头（扫描响应里一定带名字）
// 全项目仅两块板、两个固定人格，探测到对方即可确定分屏对为 xiao_hong|zhang_zong。
bool duelPeerPresent() {
  uint32_t now = millis();
  for (const auto& item : encounters) {
    if (now - item.lastSeenMs > kPeerFreshMs) continue;     // 太久没见 = 已离开
    if (item.rssi < minShownRssi) continue;
    if (item.projectPeer || item.name.startsWith(peerNamePrefix)) return true;
  }
  return false;
}

// BLE 自动分屏：只要持续探测到对方板，就进入并保持分屏；对方离开后自动退回单人。
// 串口 DUEL 命令（后端驱动）在其 12s 窗口内优先，不被这里覆盖。
void updateAutoDuel() {
  if (!autoDuelEnabled) return;
  uint32_t now = millis();
  if (now < serialDuelUntilMs) return;                       // 让位给串口 DUEL

  if (!duelPeerPresent()) return;                            // 没探测到对方：到点自动退出

  bool wasDuel = duelMode;

  // 固定布局：xiao_hong 在左、zhang_zong 在右（两块板画面一致）
  duelLeft  = "xiao_hong";
  duelRight = "zhang_zong";
  duelText  = "";                                            // 自动模式无对白

  // 状态随距离变化：很近=chat，较近=meet，否则=outdoor(正在靠近)
  PeerState ps = localPeerState();
  duelState = (ps == PEER_SOCIAL) ? "chat" : (ps == PEER_VISITING) ? "meet" : "outdoor";

  // 发言者每 2.5s 交替，画面更像在对话
  duelSpeaker = ((now / 2500) % 2 == 0) ? duelLeft : duelRight;

  duelMode = true;
  duelUntilMs = now + kAutoDuelKeepMs;                       // 持续探测到就一直续期

  if (!wasDuel) {
    Serial.printf("[auto-duel] peer detected -> split screen (state=%s)\n", duelState.c_str());
  }
}

String buildProjectManufacturerData(PeerState state) {
  char payload[11];
  payload[0] = (char)(projectCompanyId & 0xFF);
  payload[1] = (char)((projectCompanyId >> 8) & 0xFF);
  payload[2] = 'R';
  payload[3] = 'N';
  payload[4] = projectProtocolVersion;
  payload[5] = (char)(localDeviceId & 0xFF);
  payload[6] = (char)((localDeviceId >> 8) & 0xFF);
  payload[7] = localPersona.id;
  payload[8] = (uint8_t)state;
  payload[9] = localPersona.giftId;
  payload[10] = (localPersona.talkative ? 0x01 : 0x00);
  if (localPersona.slowWarm) payload[10] |= 0x02;
  if (localPersona.boundarySensitive) payload[10] |= 0x04;
  payload[10] |= ((localAdvertiseCounter & 0x0F) << 4);
  return String(payload, sizeof(payload));
}

bool parseProjectManufacturerData(const String& data, PeerBroadcast* out) {
  if (data.length() < 11) return false;

  const uint8_t* bytes = (const uint8_t*)data.c_str();
  uint16_t companyId = bytes[0] | (bytes[1] << 8);
  if (companyId != projectCompanyId) return false;
  if (bytes[2] != 'R' || bytes[3] != 'N') return false;
  if (bytes[4] != projectProtocolVersion) return false;

  out->valid = true;
  out->version = bytes[4];
  out->deviceId = bytes[5] | (bytes[6] << 8);
  out->personaId = bytes[7];
  out->state = bytes[8];
  out->giftId = bytes[9];
  out->flags = bytes[10] & 0x0F;
  out->counter = bytes[10] >> 4;
  return true;
}

bool readProjectBroadcast(BLEAdvertisedDevice& device, PeerBroadcast* out) {
  if (device.haveManufacturerData()) {
    String manufacturerData = device.getManufacturerData();
    if (parseProjectManufacturerData(manufacturerData, out)) return true;
  }
  return false;
}

class AgentCommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* characteristic) override {
    String value = characteristic->getValue();
    value.trim();
    if (!value.length()) return;
    if (value.length() > 96) value = value.substring(0, 96);

    if (value.startsWith("#ACT:")) {
      String actionName = value.substring(5);
      actionName.trim();
      ActionState target;
      if (actionFromName(actionName, &target)) {
        pendingActionCmd = actionName;
        Serial.printf("#ACT: %s -> queue\n", actionName.c_str());
      } else {
        Serial.printf("#ACT: unknown action '%s'\n", actionName.c_str());
      }
      return;
    }

    pendingAgentText = value;
    lastAgentText = value;
    lastAgentTextMs = millis();
    Serial.printf("Agent command: %s\n", value.c_str());
  }
};

void startAgentGattServer() {
  peerServer = BLEDevice::createServer();
  BLEService* service = peerServer->createService(BLEUUID(peerServiceUuid));
  agentCommandCharacteristic = service->createCharacteristic(
      BLEUUID(agentCommandCharUuid),
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  agentCommandCharacteristic->setValue("ready");
  agentCommandCharacteristic->setCallbacks(new AgentCommandCallbacks());
  service->start();
  Serial.printf("Agent command char: %s\n", agentCommandCharUuid);
}

void upsertEncounter(const String& id, const String& name, int rssi, const PeerBroadcast* peer = nullptr) {
  if (rssi < minShownRssi) return;

  uint32_t now = millis();
  for (auto& item : encounters) {
    if (item.id == id) {
      item.name = name.length() ? name : item.name;
      item.rssi = rssi;
      item.seenCount++;
      item.lastSeenMs = now;
      if (peer && peer->valid) {
        item.projectPeer = true;
        item.peer = *peer;
      }
      return;
    }
  }

  Encounter item;
  item.id = id;
  item.name = name;
  item.rssi = rssi;
  item.seenCount = 1;
  item.firstSeenMs = now;
  item.lastSeenMs = now;
  if (peer && peer->valid) {
    item.projectPeer = true;
    item.peer = *peer;
  }
  encounters.push_back(item);
}

bool isActive(const Encounter& item) {
  return millis() - item.lastSeenMs <= staleAfterMs && item.rssi >= minShownRssi;
}

int activeCount() {
  int count = 0;
  for (const auto& item : encounters) {
    if (isActive(item)) count++;
  }
  return count;
}

int activeRepeatedCount() {
  int count = 0;
  for (const auto& item : encounters) {
    if (isActive(item) && item.seenCount >= 3) count++;
  }
  return count;
}

void pruneEncounters() {
  uint32_t now = millis();
  encounters.erase(
      std::remove_if(encounters.begin(), encounters.end(), [now](const Encounter& item) {
        return now - item.lastSeenMs > forgetAfterMs;
      }),
      encounters.end());

  std::sort(encounters.begin(), encounters.end(), [](const Encounter& a, const Encounter& b) {
    if (a.lastSeenMs != b.lastSeenMs) return a.lastSeenMs > b.lastSeenMs;
    return a.rssi > b.rssi;
  });
  if (encounters.size() > 48) encounters.resize(48);
}

void printSerialReport() {
  scanRound++;
  Serial.println();
  Serial.printf("===== BLE scan round %lu =====\n", (unsigned long)scanRound);
  Serial.println(peerOnlyMode ? "Mode: M5 peer service only." : "Mode: all BLE broadcasts.");
  Serial.printf("Self: %04X %s / %s / gift=%s / peer=%s / action=%s\n",
                localDeviceId,
                localPersona.codeName,
                localPersona.archetype,
                localPersona.giftName,
                stateName(localPeerState()),
                actionStateName(currentAction));
  Serial.println("Rank | RSSI | Signal | Seen | Peer | State  | Gift");
  Serial.println("-----+------+--------+------+------+--------+--------");

  int rank = 1;
  for (const auto& item : encounters) {
    if (!isActive(item)) continue;
    String label = item.name.length() ? item.name : ("BLE-" + shortId(item.id));
    Serial.printf("%4d | %4d | %-6s | %4d | %-4s | %-6s | %s\n",
                  rank,
                  item.rssi,
                  proximityLabel(item.rssi).c_str(),
                  item.seenCount,
                  item.projectPeer ? personaName(item.peer.personaId) : "--",
                  item.projectPeer ? stateName(item.peer.state) : "--",
                  item.projectPeer ? giftName(item.peer.giftId) : label.c_str());
    rank++;
    if (rank > 20) break;
  }

  if (rank == 1) {
    Serial.println("No active BLE broadcasts above the display threshold.");
  }
  Serial.println("================================");
}

uint8_t* loadSmallFile(const char* path, size_t* outLen, size_t maxBytes) {
  *outLen = 0;
  if (!sdReady || !SD.exists(path)) return nullptr;

  File file = SD.open(path, FILE_READ);
  if (!file) return nullptr;

  size_t len = file.size();
  if (len == 0 || len > maxBytes) {
    file.close();
    return nullptr;
  }

  uint8_t* buffer = (uint8_t*)malloc(len);
  if (!buffer) {
    file.close();
    return nullptr;
  }

  size_t readLen = file.read(buffer, len);
  file.close();
  if (readLen != len) {
    free(buffer);
    return nullptr;
  }

  *outLen = len;
  return buffer;
}

void initSdAssets() {
  SPI.begin(sdSckPin, sdMisoPin, sdMosiPin, sdCsPin);
  const uint32_t speeds[] = {25000000, 10000000, 4000000, 1000000};
  sdReady = false;
  sdMountSpeed = 0;
  for (uint32_t speed : speeds) {
    if (SD.begin(sdCsPin, SPI, speed)) {
      sdReady = true;
      sdMountSpeed = speed;
      break;
    }
    delay(80);
  }

  Serial.printf("SD card: %s", sdReady ? "ready" : "not found");
  if (sdReady) Serial.printf(" @ %lu Hz", (unsigned long)sdMountSpeed);
  Serial.println();
  if (!sdReady) return;

  if (!SD.exists(assetDir)) {
    SD.mkdir(assetDir);
  }

  closeWav = loadSmallFile(closeWavPath, &closeWavLen, 220000);
  if (!closeWav) closeWav = loadSmallFile("/cores3_assets/audio/close.wav", &closeWavLen, 220000);
  repeatWav = loadSmallFile(repeatWavPath, &repeatWavLen, 220000);
  if (!repeatWav) repeatWav = loadSmallFile("/cores3_assets/audio/reply.wav", &repeatWavLen, 220000);

  char personaAvatarPath[80];
  snprintf(personaAvatarPath, sizeof(personaAvatarPath),
           "/cores3_assets/personas/%s/avatar.png", localPersona.codeName);
  avatarPng = loadSmallFile(personaAvatarPath, &avatarPngLen, 120000);
  if (!avatarPng) avatarPng = loadSmallFile(avatarPath, &avatarPngLen, 120000);

  Serial.printf("avatar: %s (%u bytes) [%s]\n",
                avatarPng ? "loaded" : "missing", (unsigned)avatarPngLen,
                avatarPng ? personaAvatarPath : avatarPath);
  Serial.printf("close.wav: %s (%u bytes)\n", closeWav ? "loaded" : "missing", (unsigned)closeWavLen);
  Serial.printf("reply.wav: %s (%u bytes)\n", repeatWav ? "loaded" : "missing", (unsigned)repeatWavLen);

  // 遍历 idle 目录，确认至少有 1 个图片文件
  hasVideoFrames = false;
  char idleDir[48];
  snprintf(idleDir, sizeof(idleDir), "/%s/animations/idle", localPersona.codeName);
  File d = SD.open(idleDir);
  if (d && d.isDirectory()) {
    int checked = 0;
    while (checked < 60) {
      File f = d.openNextFile();
      if (!f) break;
      checked++;
      String nm = f.name();
      if (!nm.startsWith(".")) {
        bool png = nm.endsWith(".png") || nm.endsWith(".PNG");
        bool jpg = nm.endsWith(".jpg") || nm.endsWith(".JPG") || nm.endsWith(".jpeg") || nm.endsWith(".JPEG");
        if (png || jpg) {
          Serial.printf("  idle frame: %s (%u bytes)\n", nm.c_str(), (unsigned)f.size());
          hasVideoFrames = true;
          f.close();
          break;
        }
      }
      f.close();
    }
  }
  if (d) d.close();
  videoMode = hasVideoFrames;
  Serial.printf("video frames (%s/idle): %s\n", localPersona.codeName,
                hasVideoFrames ? "found" : "missing");
}

void drawSdHint() {
  M5.Display.setTextSize(1);
  M5.Display.setCursor(212, 48);
  if (!sdReady) {
    M5.Display.setTextColor(kHot, kBg);
    M5.Display.print("SD NOT FOUND");
  } else if (hasVideoFrames) {
    M5.Display.setTextColor(kMint, kBg);
    M5.Display.print("SD VIDEO FOUND");
  } else {
    M5.Display.setTextColor(kAmber, kBg);
    M5.Display.print("SD OK / NO VIDEO");
  }
}

// 逐帧动画：遍历当前 persona+状态 目录，按文件顺序循环播放。
// 支持 PNG / JPG，不依赖具体文件名（与学姐 animation.ino 一致）。
// 目录随状态变化自动重开；找不到状态目录时回退到 idle。
File animDir;
bool animDirOpen = false;
ActionState animDirState = (ActionState)0xFF;

// 分屏模式双人动画目录
File duelLeftAnimDir;
bool duelLeftAnimOpen = false;
String duelLeftAnimPersona;
String duelLeftAnimState;

File duelRightAnimDir;
bool duelRightAnimOpen = false;
String duelRightAnimPersona;
String duelRightAnimState;

bool openAnimDir() {
  if (!sdReady) return false;
  if (animDirOpen) { animDir.close(); animDirOpen = false; }

  const char* dir = actionAnimDir(currentAction);
  File d = SD.open(dir);
  if (!d || !d.isDirectory()) {
    if (d) d.close();
    // 回退到本 persona 的 idle 目录
    char fb[64];
    snprintf(fb, sizeof(fb), "/%s/animations/idle", localPersona.codeName);
    d = SD.open(fb);
    if (!d || !d.isDirectory()) { if (d) d.close(); return false; }
  }
  animDir = d;
  animDirOpen = true;
  animDirState = currentAction;
  return true;
}

// 打开指定 persona + state 的动画目录，找不到时回退 idle
bool openDuelAnimDir(File& dir, bool& dirOpen, String& openPersona, String& openState,
                     const String& persona, const String& state) {
  if (dirOpen) { dir.close(); dirOpen = false; }
  if (!sdReady) return false;
  char path[80];
  snprintf(path, sizeof(path), "/%s/animations/%s", persona.c_str(), state.c_str());
  File d = SD.open(path);
  if (!d || !d.isDirectory()) {
    if (d) d.close();
    // 回退 idle
    snprintf(path, sizeof(path), "/%s/animations/idle", persona.c_str());
    d = SD.open(path);
    if (!d || !d.isDirectory()) { if (d) d.close(); return false; }
  }
  dir = d;
  dirOpen = true;
  openPersona = persona;
  openState = state;
  return true;
}

// 读取并绘制指定 persona 的下一帧，绘制区域限定在 (x, y, w, h)
// 帧取完自动回绕；状态/人物变化时自动重开目录
bool drawDuelPersonaFrame(File& dir, bool& dirOpen, String& openPersona, String& openState,
                          const String& persona, const String& state,
                          int x, int y, int w, int h) {
  if (!sdReady) return false;
  if (!dirOpen || openPersona != persona || openState != state) {
    if (!openDuelAnimDir(dir, dirOpen, openPersona, openState, persona, state)) return false;
  }
  File file;
  bool isPng = false;
  int tries = 0;
  while (tries < 60) {
    file = dir.openNextFile();
    tries++;
    if (!file) {
      dir.close(); dirOpen = false;
      if (!openDuelAnimDir(dir, dirOpen, openPersona, openState, persona, state)) return false;
      continue;
    }
    String name = file.name();
    if (name.startsWith(".")) { file.close(); continue; }
    isPng  = name.endsWith(".png") || name.endsWith(".PNG");
    bool isJpg = name.endsWith(".jpg")  || name.endsWith(".JPG") ||
                 name.endsWith(".jpeg") || name.endsWith(".JPEG");
    if (isPng || isJpg) break;
    file.close();
  }
  if (tries >= 60) return false;
  size_t size = file.size();
  if (size == 0 || size > 140000) { file.close(); return false; }
  uint8_t* buf = (uint8_t*)malloc(size);
  if (!buf) { file.close(); return false; }
  size_t readLen = file.read(buf, size);
  file.close();
  if (readLen != size) { free(buf); return false; }
  bool ok = isPng
    ? M5.Display.drawPng(buf, readLen, x, y, w, h, 0, 0, 0.0f, 0.0f, datum_t::middle_center)
    : M5.Display.drawJpg(buf, readLen, x, y, w, h, 0, 0, 0.0f, 0.0f, datum_t::middle_center);
  free(buf);
  return ok;
}

bool drawAnimFrame() {
  if (!sdReady) return false;

  // 状态切了，或还没打开，重开目录
  if (!animDirOpen || animDirState != currentAction) {
    if (!openAnimDir()) return false;
  }

  // 找下一个可读的图片文件（跳过子目录 / 隐藏文件，最多 60 次防死循环）
  File file;
  bool isPng = false;
  int tries = 0;
  while (tries < 60) {
    file = animDir.openNextFile();
    tries++;
    if (!file) {                 // 播完一轮，回到目录开头
      animDir.close();
      animDirOpen = false;
      if (!openAnimDir()) return false;
      continue;
    }

    String name = file.name();
    if (name.startsWith(".")) { file.close(); continue; }
    isPng = name.endsWith(".png") || name.endsWith(".PNG");
    bool isJpg = name.endsWith(".jpg") || name.endsWith(".JPG") ||
                 name.endsWith(".jpeg") || name.endsWith(".JPEG");
    if (isPng || isJpg) break;   // 找到图片
    file.close();                // 非图片，跳过继续
  }
  if (tries >= 60) return false; // 目录里没有图片文件

  size_t size = file.size();
  const size_t kMaxFrame = 140000;
  if (size == 0 || size > kMaxFrame) { file.close(); return false; }

  uint8_t* buf = (uint8_t*)malloc(size);
  if (!buf) { file.close(); return false; }
  size_t readLen = file.read(buf, size);
  file.close();
  if (readLen != size) { free(buf); return false; }

  M5.Display.fillScreen(TFT_BLACK);
  bool ok = isPng
    ? M5.Display.drawPng(buf, readLen,
                         0, 0, M5.Display.width(), M5.Display.height(),
                         0, 0, 0.0f, 0.0f, datum_t::middle_center)
    : M5.Display.drawJpg(buf, readLen,
                         0, 0, M5.Display.width(), M5.Display.height(),
                         0, 0, 0.0f, 0.0f, datum_t::middle_center);
  free(buf);

  // 测试方块：左上角红色 = 显示工作正常
  if (debugOverlay) {
    M5.Display.fillRect(0, 0, 10, 10, kHot);
    M5.Display.fillRect(M5.Display.width() - 10, 0, 10, 10, kMint);
  }

  static uint32_t lastFrameDbg = 0;
  if (millis() - lastFrameDbg > 3000) {
    lastFrameDbg = millis();
    Serial.printf("anim: %s/%s %s %uB %s\n",
                  localPersona.codeName, actionStateFolder(currentAction),
                  isPng ? "PNG" : "JPG", (unsigned)readLen,
                  ok ? "OK" : "FAIL");
  }

  // 对话文字气泡：底部居中
  if (lastAgentText.length() && millis() - lastAgentTextMs < 30000) {
    M5.Display.setTextSize(1);
    String shown = lastAgentText;
    if (shown.length() > 40) shown = shown.substring(0, 40);
    int tw = shown.length() * 10 + 24;
    int tx = (M5.Display.width() - tw) / 2;
    if (tx < 4) tx = 4;
    M5.Display.fillRoundRect(tx, 196, tw, 38, 8, 0x0000);
    M5.Display.drawRoundRect(tx, 196, tw, 38, 8, kHot);
    M5.Display.setTextColor(kHot, 0x0000);
    M5.Display.setCursor(tx + 12, 206);
    M5.Display.print(shown);
  }

  return ok;
}

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice device) override {
    PeerBroadcast peer;
    bool hasProjectService = device.isAdvertisingService(BLEUUID(peerServiceUuid));
    bool hasProjectPayload = readProjectBroadcast(device, &peer);
    if (peerOnlyMode && !hasProjectService && !hasProjectPayload) {
      return;
    }
    String id = device.getAddress().toString().c_str();
    String name = device.haveName() ? device.getName().c_str() : "";
    upsertEncounter(id, name, device.getRSSI(), hasProjectPayload ? &peer : nullptr);
  }
};

void updatePeerAdvertising(const String& peerName) {
  if (!advertiser) return;

  BLEDevice::stopAdvertising();
  localAdvertiseCounter++;

  BLEAdvertisementData advertisementData;
  advertisementData.setFlags(0x06);
  advertisementData.setCompleteServices(BLEUUID(peerServiceUuid));
  advertisementData.setManufacturerData(buildProjectManufacturerData(localPeerState()));

  BLEAdvertisementData scanResponseData;
  scanResponseData.setName(peerName.c_str());

  advertiser->setAdvertisementData(advertisementData);
  advertiser->setScanResponseData(scanResponseData);
  BLEDevice::startAdvertising();
  lastAdvertiseUpdateMs = millis();
}

void startPeerAdvertising(const String& peerName) {
  advertiser = BLEDevice::getAdvertising();
  advertiser->setMinPreferred(0x06);
  advertiser->setMinPreferred(0x12);
  updatePeerAdvertising(peerName);

  Serial.printf("Peer BLE name: %s\n", peerName.c_str());
  Serial.printf("Peer local ID: %04X\n", localDeviceId);
  Serial.printf("Peer service UUID: %s\n", peerServiceUuid);
}

uint32_t stableHash(const String& value) {
  uint32_t h = 2166136261UL;
  for (size_t i = 0; i < value.length(); i++) {
    h ^= (uint8_t)value[i];
    h *= 16777619UL;
  }
  return h;
}

void drawScanline() {
  int y = (millis() / 38) % M5.Display.height();
  M5.Display.drawFastHLine(0, y, M5.Display.width(), 0x18E3);
}

void drawHeader() {
  M5.Display.fillRect(0, 0, M5.Display.width(), 42, kBg);
  M5.Display.drawFastHLine(0, 41, M5.Display.width(), kDim);
  M5.Display.setTextColor(kInk, kBg);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(10, 8);
  M5.Display.print("M5 PEERS");
  M5.Display.setTextSize(1);
  M5.Display.setCursor(145, 8);
  M5.Display.print(peerOnlyMode ? "shows paired sketches" : "shows all BLE");
  M5.Display.setCursor(145, 22);
  M5.Display.print("tap toggles filter");
}

void drawLegend() {
  int x = 212;
  int y = 176;
  M5.Display.setTextSize(1);
  M5.Display.setTextColor(kInk, kBg);
  M5.Display.setCursor(x, y);
  M5.Display.print("DOT COLOR");

  M5.Display.fillCircle(x + 4, y + 18, 4, kHot);
  M5.Display.setTextColor(kHot, kBg);
  M5.Display.setCursor(x + 14, y + 14);
  M5.Display.print("red close");

  M5.Display.fillCircle(x + 4, y + 32, 4, kAmber);
  M5.Display.setTextColor(kAmber, kBg);
  M5.Display.setCursor(x + 14, y + 28);
  M5.Display.print("yellow near");

  M5.Display.fillCircle(x + 4, y + 46, 4, kMint);
  M5.Display.setTextColor(kMint, kBg);
  M5.Display.setCursor(x + 14, y + 42);
  M5.Display.print("green far");

  M5.Display.drawCircle(x + 4, y + 60, 7, kBlue);
  M5.Display.setTextColor(kBlue, kBg);
  M5.Display.setCursor(x + 14, y + 56);
  M5.Display.print("blue repeat");
}

void drawLineAvatar(int x, int y, int rssi, int repeated) {
  bool near = rssi >= -55;
  bool far = rssi < -72;
  uint16_t accent = proximityColor(rssi);

  M5.Display.drawRoundRect(x, y, 78, 112, 8, kDim);

  if (avatarPng) {
    bool ok = M5.Display.drawPng(avatarPng, avatarPngLen, x + 1, y + 1, 76, 86, 0, 0, 1.0f);
    if (ok) {
      M5.Display.setTextColor(accent, kBg);
      M5.Display.setTextSize(1);
      M5.Display.setCursor(x + 8, y + 88);
      M5.Display.print(near ? "BOOP!" : (far ? "IDLE" : "PING?"));
      M5.Display.setCursor(x + 8, y + 100);
      M5.Display.printf("repeat %02d", repeated);
      return;
    }
  }

  M5.Display.drawCircle(x + 39, y + 45, 28, kInk);
  M5.Display.drawCircle(x + 39, y + 45, 29, kDim);
  M5.Display.drawLine(x + 25, y + 22, x + 18, y + 7, accent);
  M5.Display.drawLine(x + 52, y + 22, x + 61, y + 7, accent);
  M5.Display.fillCircle(x + 18, y + 7, 3, accent);
  M5.Display.fillCircle(x + 61, y + 7, 3, accent);

  if (near) {
    M5.Display.drawCircle(x + 29, y + 42, 6, accent);
    M5.Display.drawCircle(x + 50, y + 42, 6, accent);
    M5.Display.drawLine(x + 28, y + 61, x + 39, y + 68, kInk);
    M5.Display.drawLine(x + 39, y + 68, x + 54, y + 57, kInk);
  } else if (far) {
    M5.Display.drawLine(x + 23, y + 43, x + 35, y + 43, kInk);
    M5.Display.drawLine(x + 46, y + 43, x + 58, y + 43, kInk);
    M5.Display.drawLine(x + 30, y + 61, x + 51, y + 61, kDim);
  } else {
    M5.Display.fillCircle(x + 30, y + 43, 3, kInk);
    M5.Display.fillCircle(x + 50, y + 43, 3, kInk);
    M5.Display.drawCircle(x + 40, y + 60, 6, accent);
  }

  M5.Display.drawLine(x + 39, y + 74, x + 39, y + 96, kInk);
  M5.Display.drawLine(x + 39, y + 82, x + 23, y + 92, kInk);
  M5.Display.drawLine(x + 39, y + 82, x + 56, y + 92, kInk);
  M5.Display.drawLine(x + 39, y + 96, x + 28, y + 107, kInk);
  M5.Display.drawLine(x + 39, y + 96, x + 52, y + 107, kInk);

  M5.Display.setTextColor(accent, kBg);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(x + 8, y + 88);
  M5.Display.print(near ? "BOOP!" : (far ? "IDLE" : "PING?"));
  M5.Display.setCursor(x + 8, y + 100);
  M5.Display.printf("repeat %02d", repeated);
}

void drawRadar() {
  int cx = 106;
  int cy = 141;
  int maxR = 88;

  M5.Display.drawCircle(cx, cy, 28, kDim);
  M5.Display.drawCircle(cx, cy, 56, kDim);
  M5.Display.drawCircle(cx, cy, maxR, kDim);
  M5.Display.drawFastHLine(cx - maxR, cy, maxR * 2, kDim);
  M5.Display.drawFastVLine(cx, cy - maxR, maxR * 2, kDim);

  float sweep = (millis() % 5000) * 0.0012566f;
  M5.Display.drawLine(cx, cy, cx + cosf(sweep) * maxR, cy + sinf(sweep) * maxR, kMint);

  uint32_t now = millis();
  int drawn = 0;
  for (const auto& item : encounters) {
    if (drawn >= maxRadarDevices) break;
    if (!isActive(item)) continue;
    uint32_t h = stableHash(item.id);
    float a = ((h % 628) / 100.0f) + (millis() % 900) * 0.00015f;
    int dist = map(constrain(item.rssi, -82, -35), -35, -82, 18, maxR - 8);
    int x = cx + cosf(a) * dist;
    int y = cy + sinf(a) * dist;
    uint16_t c = proximityColor(item.rssi);
    int dot = item.seenCount >= 3 ? 5 : 3;

    M5.Display.drawLine(cx, cy, x, y, 0x39E7);
    M5.Display.fillCircle(x, y, dot, c);
    M5.Display.drawCircle(x, y, dot + 3, c);
    if (item.seenCount >= 3) M5.Display.drawCircle(x, y, dot + 7, kBlue);

    drawn++;
  }
}

void drawList() {
  M5.Display.fillRect(0, 42, M5.Display.width(), M5.Display.height() - 42, kBg);

  std::sort(encounters.begin(), encounters.end(), [](const Encounter& a, const Encounter& b) {
    return a.rssi > b.rssi;
  });

  int visible = activeCount();
  int repeated = activeRepeatedCount();

  drawRadar();
  drawLineAvatar(232, 62, bestRssi(), repeated);
  drawLegend();

  M5.Display.setTextColor(kInk, kBg);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(10, 48);
  M5.Display.printf("M5 peers now:      %02d", visible);
  M5.Display.setCursor(10, 61);
  M5.Display.printf("Repeated nearby:   %02d", repeated);
  M5.Display.setTextColor(kDim, kBg);
  M5.Display.setCursor(10, 74);
  PeerState selfState = localPeerState();
  M5.Display.printf("Me:%04X %s %s|%s", localDeviceId, localPersona.shortName, stateName(selfState), actionStateName(currentAction));
  M5.Display.setCursor(10, 87);
  M5.Display.print(localPersonaLine(selfState));
  drawSdHint();

  if (lastAgentText.length() && millis() - lastAgentTextMs < 30000) {
    M5.Display.fillRect(8, 104, 204, 36, kBg);
    M5.Display.drawRoundRect(8, 104, 204, 36, 6, kBlue);
    M5.Display.setTextColor(kBlue, kBg);
    M5.Display.setCursor(15, 112);
    String shown = lastAgentText;
    if (shown.length() > 64) shown = shown.substring(0, 64);
    M5.Display.print(shown);
  }

  int y = 194;
  uint32_t now = millis();
  int rows = 0;
  for (const auto& item : encounters) {
    if (rows >= 3) break;
    if (!isActive(item)) continue;
    bool stale = now - item.lastSeenMs > staleAfterMs;

    M5.Display.setTextColor(stale ? kDim : kInk, kBg);
    M5.Display.setTextSize(1);
    M5.Display.setCursor(10, y);
    String label;
    if (item.projectPeer) {
      char peerId[5];
      snprintf(peerId, sizeof(peerId), "%04X", item.peer.deviceId);
      label = String(peerId) + " " + personaName(item.peer.personaId);
    } else {
      label = item.name.length() ? item.name : ("BLE-" + shortId(item.id));
    }
    if (label.length() > 14) label = label.substring(0, 14);
    M5.Display.print(label);

    M5.Display.setCursor(102, y);
    M5.Display.printf("%4d", item.rssi);

    M5.Display.setTextColor(stale ? kDim : proximityColor(item.rssi), kBg);
    M5.Display.setCursor(138, y);
    M5.Display.print(proximityLabel(item.rssi));

    M5.Display.setTextColor(item.seenCount >= 3 ? kBlue : kDim, kBg);
    M5.Display.setCursor(180, y);
    if (item.projectPeer) {
      M5.Display.printf("%s/%s", stateName(item.peer.state), giftName(item.peer.giftId));
    } else {
      M5.Display.printf("seen %d", item.seenCount);
    }

    y += 20;
    rows++;
  }

  if (visible == 0) {
    M5.Display.setTextColor(kAmber, kBg);
    M5.Display.setTextSize(2);
    M5.Display.setCursor(42, 132);
    M5.Display.print(peerOnlyMode ? "FINDING M5" : "SCANNING BLE");
  }
}

void playSoundForAction(ActionState action) {
  uint32_t now = millis();
  uint32_t minGap = 8000;

  switch (action) {
    case ACTION_SEARCHING:
      return;

    case ACTION_NEAR:
      minGap = 12000;
      if (now - lastSoundMs < minGap) return;
      lastSoundMs = now;
      M5.Speaker.tone(680, 30);
      delay(60);
      M5.Speaker.tone(820, 30);
      return;

    case ACTION_ENCOUNTER:
      if (now - lastSoundMs < 1000) return;
      lastSoundMs = now;
      if (closeWav) {
        M5.Speaker.playWav(closeWav, closeWavLen, 1, -1, true);
      } else {
        M5.Speaker.tone(1040, 40); delay(50);
        M5.Speaker.tone(1280, 40); delay(50);
        M5.Speaker.tone(1600, 60);
      }
      return;

    case ACTION_THINKING:
      return;

    case ACTION_REPLY:
      if (now - lastSoundMs < 500) return;
      lastSoundMs = now;
      if (repeatWav) {
        M5.Speaker.playWav(repeatWav, repeatWavLen, 1, -1, true);
      } else {
        M5.Speaker.tone(880, 50);  delay(60);
        M5.Speaker.tone(1100, 50); delay(60);
        M5.Speaker.tone(1320, 80);
      }
      return;

    case ACTION_COOLDOWN:
      return;
  }
}

void playMinionishSound(int rssi, bool repeated) {
  playSoundForAction(currentAction);
}

void drawDebugOverlay() {
  M5.Display.fillRect(0, 0, M5.Display.width(), M5.Display.height(), 0x0000);
  M5.Display.setTextColor(kMint, 0x0000);
  M5.Display.setTextSize(1);
  int y = 8;
  M5.Display.setCursor(6, y); M5.Display.printf("persona:  %s", localPersona.codeName);    y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("devid:    %04X", localDeviceId);           y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("action:   %s", actionStateName(currentAction)); y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("peer-st:  %s", stateName(localPeerState())); y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("bestRSSI: %d", bestRssi());                y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("peers:    %d (rep %d)", activeCount(), activeRepeatedCount()); y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("peerOnly: %s", peerOnlyMode ? "ON" : "OFF"); y += 14;
  M5.Display.setCursor(6, y); M5.Display.printf("sdReady:  %s", sdReady ? "YES" : "NO");   y += 14;
  if (lastAgentText.length()) {
    M5.Display.setCursor(6, y); M5.Display.printf("reply: %s", lastAgentText.substring(0, 32).c_str());
  }
}

String duelLabel(const String& persona) {
  if (persona == "xiao_hong") return "XIAO HONG";
  if (persona == "zhang_zong") return "ZHANG ZONG";
  return persona.length() ? persona : "?";
}

void drawDuelPanel(int x, int y, int w, int h, const String& persona, bool active, uint16_t color) {
  uint16_t border = active ? color : kDim;
  M5.Display.fillRoundRect(x, y, w, h, 8, active ? 0x18E3 : 0x0841);
  M5.Display.drawRoundRect(x, y, w, h, 8, border);
  M5.Display.setTextSize(1);
  M5.Display.setTextColor(active ? color : kInk, active ? 0x18E3 : 0x0841);
  M5.Display.setCursor(x + 10, y + 10);
  M5.Display.print(duelLabel(persona));

  int cx = x + w / 2;
  int cy = y + 76;
  M5.Display.drawCircle(cx, cy, active ? 34 : 30, border);
  M5.Display.fillCircle(cx - 12, cy - 5, 4, kInk);
  M5.Display.fillCircle(cx + 12, cy - 5, 4, kInk);
  M5.Display.drawLine(cx - 12, cy + 14, cx, cy + 21, active ? color : kInk);
  M5.Display.drawLine(cx, cy + 21, cx + 14, cy + 12, active ? color : kInk);
}

void drawDuelScreen() {
  M5.Display.fillScreen(TFT_BLACK);
  bool leftActive  = duelSpeaker == duelLeft;
  bool rightActive = duelSpeaker == duelRight;

  // 优先从 SD 卡读 PNG 动画帧；SD 取不到时回退到占位符小人
  bool leftOk  = drawDuelPersonaFrame(
      duelLeftAnimDir,  duelLeftAnimOpen,  duelLeftAnimPersona,  duelLeftAnimState,
      duelLeft,  duelState, 8, 16, 148, 148);
  bool rightOk = drawDuelPersonaFrame(
      duelRightAnimDir, duelRightAnimOpen, duelRightAnimPersona, duelRightAnimState,
      duelRight, duelState, 164, 16, 148, 148);

  if (!leftOk)  drawDuelPanel(8,   16, 148, 148, duelLeft,  leftActive,  kMint);
  if (!rightOk) drawDuelPanel(164, 16, 148, 148, duelRight, rightActive, kHot);

  // 发言者边框高亮（叠在动画上方）
  M5.Display.drawRoundRect(8,   16, 148, 148, 8, leftActive  ? kMint : kDim);
  M5.Display.drawRoundRect(164, 16, 148, 148, 8, rightActive ? kHot  : kDim);

  // 名字标签（顶部半透明黑底，确保可读）
  M5.Display.setTextSize(1);
  M5.Display.fillRect(8,   16, 148, 18, 0x0000);
  M5.Display.setTextColor(leftActive  ? kMint : kInk, 0x0000);
  M5.Display.setCursor(18, 20);
  M5.Display.print(duelLabel(duelLeft));
  M5.Display.fillRect(164, 16, 148, 18, 0x0000);
  M5.Display.setTextColor(rightActive ? kHot  : kInk, 0x0000);
  M5.Display.setCursor(174, 20);
  M5.Display.print(duelLabel(duelRight));

  // 状态 + 对话文字（动画面板下方区域）
  M5.Display.setTextSize(1);
  M5.Display.setTextColor(kAmber, TFT_BLACK);
  M5.Display.setCursor(12, 174);
  M5.Display.printf("state: %s", duelState.c_str());

  if (duelText.length()) {
    String shown = duelText;
    if (shown.length() > 56) shown = shown.substring(0, 56);
    M5.Display.fillRoundRect(8, 190, 304, 42, 8, 0x0841);
    M5.Display.drawRoundRect(8, 190, 304, 42, 8, leftActive ? kMint : kHot);
    M5.Display.setTextColor(kInk, 0x0841);
    M5.Display.setCursor(18, 204);
    M5.Display.print(shown);
  }
}

void drawScreen() {
  if (debugOverlay) {
    drawDebugOverlay();
    return;
  }
  if (duelMode && millis() < duelUntilMs) {
    drawDuelScreen();
    return;
  }
  if (duelMode && millis() >= duelUntilMs) {
    duelMode = false;
    // 关闭分屏动画目录，释放文件句柄
    if (duelLeftAnimOpen)  { duelLeftAnimDir.close();  duelLeftAnimOpen  = false; }
    if (duelRightAnimOpen) { duelRightAnimDir.close(); duelRightAnimOpen = false; }
  }
  if (videoMode) {
    bool ok = drawAnimFrame();
    if (!ok) {
      M5.Display.fillScreen(kBg);
      M5.Display.setTextSize(2);
      M5.Display.setTextColor(kAmber, kBg);
      M5.Display.setCursor(50, 110);
      M5.Display.print("loading...");
    }
    return;
  }
  M5.Display.fillScreen(kBg);
  M5.Display.setTextSize(2);
  M5.Display.setTextColor(kAmber, kBg);
  M5.Display.setCursor(40, 100);
  M5.Display.print(sdReady ? "NO ANIMATION" : "NO SD CARD");
}

void scanNearby() {
  BLEScanResults* results = scanner->start(4, false);
  if (results != nullptr) {
    scanner->clearResults();
  }
  if (advertiser && localBleName.length()) {
    updatePeerAdvertising(localBleName);
  }
  pruneEncounters();
  printSerialReport();
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Display.setBrightness(128);
  M5.Display.fillScreen(TFT_BLACK);
  M5.Speaker.setVolume(0);

  Serial.begin(115200);
  delay(300);
  Serial.println("CoreS3 M5 peer radar ready. Open Arduino IDE Serial Monitor at 115200 baud.");
  Serial.printf("Persona slot: %d = %s (%s)\n", localPersonaSlot, localPersona.codeName, localPersona.archetype);
  Serial.printf("visitingRssi=%d  socialRssi=%d\n", localPersona.visitingRssi, localPersona.socialRssi);
  initSdAssets();
  localDeviceId = makeLocalDeviceId();
  localBleName = localPeerName();
  BLEDevice::init(localBleName.c_str());
  startAgentGattServer();
  startPeerAdvertising(localBleName);
  scanner = BLEDevice::getScan();
  scanner->setAdvertisedDeviceCallbacks(new ScanCallbacks(), true);
  scanner->setActiveScan(true);
  scanner->setInterval(100);
  scanner->setWindow(80);

  drawScreen();
}

// ======================
// 串口协议（与 animation.ino 兼容，补充 BLE GATT）
// ======================
void handleSerialCommands() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (!line.length()) continue;

    // TXT|<state>|<text>  直接切换动画状态 + 显示文字
    if (line.startsWith("TXT|")) {
      int p1 = line.indexOf('|', 4);
      String stateName = (p1 > 0) ? line.substring(4, p1) : line.substring(4);
      String text = (p1 > 0) ? line.substring(p1 + 1) : "";
      stateName.trim();
      text.trim();

      ActionState target;
      if (actionFromName(stateName, &target)) {
        transitionAction(target);
        actionHoldUntilMs = millis() + (target == ACTION_COOLDOWN ? 4000 : 12000);   // 防本地 RSSI 覆盖
        Serial.printf("SERIAL TXT: state=%s text='%s'\n", stateName.c_str(), text.c_str());
      } else {
        Serial.printf("SERIAL TXT: unknown state '%s'\n", stateName.c_str());
      }

      if (text.length()) {
        lastAgentText = text;
        lastAgentTextMs = millis();
      }
      continue;
    }

    // DUEL|<left>|<right>|<speaker>|<state>|<text>  双人分屏（预留）
    if (line.startsWith("DUEL|")) {
      int p1 = line.indexOf('|', 5);
      int p2 = p1 > 0 ? line.indexOf('|', p1 + 1) : -1;
      int p3 = p2 > 0 ? line.indexOf('|', p2 + 1) : -1;
      int p4 = p3 > 0 ? line.indexOf('|', p3 + 1) : -1;
      if (p1 > 0 && p2 > 0 && p3 > 0 && p4 > 0) {
        duelLeft = line.substring(5, p1);
        duelRight = line.substring(p1 + 1, p2);
        duelSpeaker = line.substring(p2 + 1, p3);
        duelState = line.substring(p3 + 1, p4);
        duelText = line.substring(p4 + 1);
        duelLeft.trim();
        duelRight.trim();
        duelSpeaker.trim();
        duelState.trim();
        duelText.trim();

        ActionState target;
        if (actionFromName(duelState, &target)) {
          transitionAction(target);
          actionHoldUntilMs = millis() + 12000;
        }
        if (duelText.length()) {
          lastAgentText = duelText;
          lastAgentTextMs = millis();
        }
        duelMode = true;
        duelUntilMs = millis() + 12000;
        serialDuelUntilMs = millis() + 12000;   // 串口命令优先窗口，期间不被自动分屏覆盖
        // 重置分屏动画目录（人物或状态变化时重新打开）
        if (duelLeftAnimOpen)  { duelLeftAnimDir.close();  duelLeftAnimOpen  = false; }
        if (duelRightAnimOpen) { duelRightAnimDir.close(); duelRightAnimOpen = false; }
        Serial.printf("SERIAL DUEL: %s | %s says '%s'\n",
                      duelState.c_str(), duelSpeaker.c_str(), duelText.c_str());
      } else {
        Serial.printf("SERIAL DUEL malformed: %s\n", line.c_str());
      }
      continue;
    }

    Serial.printf("SERIAL: %s\n", line.c_str());
  }
}

void loop() {
  M5.update();
  uint32_t now = millis();

  handleSerialCommands();

  auto touch = M5.Touch.getDetail();
  if (touch.wasHold()) {
    peerOnlyMode = !peerOnlyMode;
    encounters.clear();
    tapCount = 0;
    Serial.printf("Touch long: peerOnlyMode=%s\n", peerOnlyMode ? "ON" : "OFF");
    drawScreen();
  } else if (touch.wasPressed()) {
    uint32_t tNow = millis();
    if (tNow - lastTapMs < 400) {
      tapCount++;
    } else {
      tapCount = 1;
    }
    lastTapMs = tNow;

    if (tapCount >= 2) {
      tapCount = 0;
      debugOverlay = !debugOverlay;
      Serial.printf("Touch double: debugOverlay=%s\n", debugOverlay ? "ON" : "OFF");
    } else {
      if (currentAction == ACTION_SEARCHING || currentAction == ACTION_NEAR || currentAction == ACTION_COOLDOWN) {
        manualEncounterTrigger = true;
        Serial.println("Touch single: manual ENCOUNTER trigger");
      }
    }
    drawScreen();
  }

  if (now - lastVideoMs > 120) {
    lastVideoMs = now;
    if (duelMode && millis() < duelUntilMs) {
      drawDuelScreen();              // 分屏模式：左右各读下一帧
    } else if (videoMode) {
      drawAnimFrame();               // 单人模式：读本地 persona 帧
    }
  }

  if (!videoMode && advertiser && now - lastAdvertiseUpdateMs > 10000) {
    updatePeerAdvertising(localBleName);
  }

  if (now - lastScanMs > scanIntervalMs) {
    lastScanMs = now;
    scanNearby();
    updateActionState();
    updateAutoDuel();
    bool repeated = activeRepeatedCount() > 0;
    if (currentAction != ACTION_THINKING && currentAction != ACTION_COOLDOWN) {
      playMinionishSound(bestRssi(), repeated);
    }
    drawScreen();
  }

  if (now - lastDrawMs > 1000) {
    lastDrawMs = now;
    updateActionState();
    updateAutoDuel();
    drawScreen();
  }
}
