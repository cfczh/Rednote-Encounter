#include <M5Unified.h>

static const uint32_t BAUD_RATE = 921600;
static const uint32_t MAX_WAV_BYTES = 4 * 1024 * 1024;
static const uint32_t READ_TIMEOUT_MS = 60000;
static const size_t READ_CHUNK_BYTES = 64;
static const uint8_t MAGIC[4] = {'Z', 'A', 'V', '1'};
static size_t lastReadGot = 0;

static bool readExact(uint8_t* dst, size_t len, uint32_t timeoutMs) {
  size_t got = 0;
  lastReadGot = 0;
  uint32_t start = millis();
  uint32_t lastDraw = 0;
  while (got < len) {
    M5.update();
    if (Serial.available() > 0) {
      size_t want = len - got;
      if (want > READ_CHUNK_BYTES) {
        want = READ_CHUNK_BYTES;
      }
      int n = Serial.readBytes(dst + got, want);
      if (n > 0) {
        got += n;
        lastReadGot = got;
        start = millis();
        if (len > 8192 && millis() - lastDraw > 500) {
          lastDraw = millis();
          M5.Display.fillRect(10, 72, 300, 28, TFT_BLACK);
          M5.Display.setCursor(10, 72);
          M5.Display.printf("%u / %u", (unsigned int)got, (unsigned int)len);
        }
      }
    } else {
      delay(1);
    }
    if (millis() - start > timeoutMs) {
      return false;
    }
  }
  return true;
}

static uint32_t readLittleEndianU32(const uint8_t* data) {
  return ((uint32_t)data[0]) |
         ((uint32_t)data[1] << 8) |
         ((uint32_t)data[2] << 16) |
         ((uint32_t)data[3] << 24);
}

static void showStatus(const char* line1, const char* line2 = "") {
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setCursor(10, 24);
  M5.Display.setTextSize(2);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.println(line1);
  if (line2 && line2[0]) {
    M5.Display.println();
    M5.Display.println(line2);
  }
}

static bool waitForHeader(uint32_t* wavLen) {
  uint8_t header[8];
  if (!readExact(header, sizeof(header), READ_TIMEOUT_MS)) {
    return false;
  }
  for (int i = 0; i < 4; ++i) {
    if (header[i] != MAGIC[i]) {
      while (Serial.available()) {
        Serial.read();
      }
      return false;
    }
  }
  *wavLen = readLittleEndianU32(header + 4);
  return true;
}

static bool receiveWavChunks(uint8_t* wav, uint32_t wavLen) {
  uint32_t got = 0;
  uint32_t lastDraw = 0;
  uint8_t chunk[READ_CHUNK_BYTES];
  while (got < wavLen) {
    size_t want = wavLen - got;
    if (want > READ_CHUNK_BYTES) {
      want = READ_CHUNK_BYTES;
    }

    if (!readExact(chunk, want, READ_TIMEOUT_MS)) {
      return false;
    }

    memcpy(wav + got, chunk, want);
    got += want;
    Serial.println("ACK");

    if (millis() - lastDraw > 200) {
      lastDraw = millis();
      M5.Display.fillRect(10, 72, 300, 28, TFT_BLACK);
      M5.Display.setCursor(10, 72);
      M5.Display.printf("%u / %u", (unsigned int)got, (unsigned int)wavLen);
    }
  }
  return true;
}

static void handleOneWav() {
  uint32_t wavLen = 0;
  if (!waitForHeader(&wavLen)) {
    Serial.println("ERR:HEADER");
    showStatus("Header error", "waiting...");
    return;
  }

  if (wavLen == 0 || wavLen > MAX_WAV_BYTES) {
    Serial.println("ERR:SIZE");
    showStatus("Bad WAV size");
    return;
  }

  showStatus("Receiving WAV", String(wavLen).c_str());

  uint8_t* wav = (uint8_t*)ps_malloc(wavLen);
  if (!wav) {
    Serial.println("ERR:PSRAM");
    showStatus("PSRAM alloc failed");
    return;
  }

  Serial.println("SEND");

  if (!receiveWavChunks(wav, wavLen)) {
    free(wav);
    Serial.print("ERR:RECV:");
    Serial.println((unsigned int)lastReadGot);
    showStatus("Receive timeout");
    return;
  }

  showStatus("Playing...");
  bool ok = M5.Speaker.playWav(wav, wavLen, 1, -1, true);
  if (!ok) {
    free(wav);
    Serial.println("ERR:PLAY");
    showStatus("playWav failed");
    return;
  }

  while (M5.Speaker.isPlaying()) {
    M5.update();
    delay(10);
  }

  free(wav);
  Serial.println("DONE");
  showStatus("Ready", "waiting audio");
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  Serial.begin(BAUD_RATE);
  Serial.setTimeout(50);

  M5.Speaker.begin();
  M5.Speaker.setVolume(180);

  showStatus("Ready", "USB WAV player");
  Serial.println("READY");
}

void loop() {
  M5.update();
  if (Serial.available() >= 8) {
    handleOneWav();
  }
  delay(5);
}
