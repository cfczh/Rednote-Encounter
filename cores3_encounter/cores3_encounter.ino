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
String lastAgentText;
uint32_t lastAgentTextMs = 0;
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

const char* actionAnimDir(ActionState action) {
  switch (action) {
    case ACTION_SEARCHING: return "/cores3_assets/animations/searching";
    case ACTION_NEAR:      return "/cores3_assets/animations/near";
    case ACTION_ENCOUNTER: return "/cores3_assets/animations/encounter";
    case ACTION_THINKING:  return "/cores3_assets/animations/thinking";
    case ACTION_REPLY:     return "/cores3_assets/animations/reply";
    case ACTION_COOLDOWN:  return "/cores3_assets/animations/cooldown";
    default:               return "/cores3_assets/animations/searching";
  }
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
const uint32_t kCooldownMs          = 15000;
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

  hasVideoFrames = SD.exists("/cores3_assets/video/frame_0001.jpg");
  videoMode = hasVideoFrames;
  Serial.printf("video frames: %s\n", hasVideoFrames ? "found" : "missing");
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

bool drawAnimFrame() {
  if (!sdReady) return false;

  const char* dir = actionAnimDir(currentAction);
  char path[80];
  snprintf(path, sizeof(path), "%s/frame_%04u.jpg", dir, videoFrame);
  if (!SD.exists(path)) {
    videoFrame = 1;
    snprintf(path, sizeof(path), "%s/frame_%04u.jpg", dir, videoFrame);
    if (!SD.exists(path)) {
      snprintf(path, sizeof(path), "%s/frame_%04u.jpg", videoDir, videoFrame);
      if (!SD.exists(path)) return false;
    }
  }

  size_t frameLen = 0;
  uint8_t* frameData = loadSmallFile(path, &frameLen, 140000);
  if (!frameData) return false;

  M5.Display.fillScreen(TFT_BLACK);
  bool ok = M5.Display.drawJpg(frameData, frameLen, 0, 0, 320, 240, 0, 0, 1.0f);
  free(frameData);

  M5.Display.setTextSize(1);
  M5.Display.setTextColor(kMint, TFT_BLACK);
  M5.Display.setCursor(6, 6);
  M5.Display.printf("%s f%04u", actionStateName(currentAction), videoFrame);

  videoFrame++;
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

void drawScreen() {
  if (debugOverlay) {
    drawDebugOverlay();
    return;
  }
  if (videoMode && drawAnimFrame()) {
    return;
  }
  drawHeader();
  drawList();
  drawScanline();
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
  M5.Display.setRotation(1);
  M5.Display.fillScreen(kBg);
  M5.Speaker.setVolume(72);

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

void loop() {
  M5.update();
  uint32_t now = millis();

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

  if (videoMode && now - lastVideoMs > 120) {
    lastVideoMs = now;
    drawVideoFrame();
    return;
  }

  if (!videoMode && advertiser && now - lastAdvertiseUpdateMs > 10000) {
    updatePeerAdvertising(localBleName);
  }

  if (now - lastScanMs > scanIntervalMs) {
    lastScanMs = now;
    scanNearby();
    updateActionState();
    bool repeated = activeRepeatedCount() > 0;
    if (currentAction != ACTION_THINKING && currentAction != ACTION_COOLDOWN) {
      playMinionishSound(bestRssi(), repeated);
    }
    drawScreen();
  }

  if (now - lastDrawMs > 1000) {
    lastDrawMs = now;
    updateActionState();
    drawScreen();
  }
}
