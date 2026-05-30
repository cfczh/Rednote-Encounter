#include <M5Unified.h>
#include <SPI.h>
#include <SD.h>
#include <Preferences.h>

#define SD_SPI_CS_PIN    4
#define SD_SPI_SCK_PIN   36
#define SD_SPI_MISO_PIN  35
#define SD_SPI_MOSI_PIN  37
#define DEFAULT_AUDIO_SAMPLE_RATE 16000

// ======================
// 状态
// ======================
String currentState = "idle";
String displayText = "你好";
String currentPersona = "zhang_zong";

String duelLeftPersona = "zhang_zong";
String duelRightPersona = "xiao_hong";
String duelSpeakerPersona = "zhang_zong";
String duelState = "idle";
String duelText = "";
bool duelMode = false;
bool sdReady = false;

bool isPlayingAudio = false;
unsigned long frameDelay = 100;
bool enableAnimation = true;
unsigned long lastPersonaReportAt = 0;
Preferences personaPrefs;

// 当前帧
File currentDir;
bool folderOpened = false;
File duelLeftDir;
File duelRightDir;
bool duelLeftOpened = false;
bool duelRightOpened = false;

void playAnimationFrame();
void resetAnimationFolder();
void resetDuelFolders();

String animationFolderPath(
    const String& persona,
    const String& state
) {

    return "/" +
        persona +
        "/animations/" +
        state;
}

bool tryOpenAnimationFolder(
    const String& state
) {

    if (
        !sdReady
    ) {
        return false;
    }

    String folder =
        animationFolderPath(
            currentPersona,
            state
        );

    Serial.print(
        "Open folder: "
    );
    Serial.println(
        folder
    );

    File dir =
        SD.open(folder);

    if (
        !dir ||
        !dir.isDirectory()
    ) {

        Serial.print(
            "Folder open fail: "
        );
        Serial.println(
            folder
        );

        if (dir) {
            dir.close();
        }

        return false;
    }

    currentDir = dir;
    folderOpened = true;

    return true;
}

void resetAnimationFolder() {

    if (
        folderOpened
    ) {
        currentDir.close();
    }

    folderOpened =
        false;
}

void resetDuelFolders() {

    if (
        duelLeftOpened
    ) {
        duelLeftDir.close();
    }

    if (
        duelRightOpened
    ) {
        duelRightDir.close();
    }

    duelLeftOpened =
        false;

    duelRightOpened =
        false;
}

bool initSDCard() {

    const uint32_t speeds[] = {
        25000000,
        10000000,
        4000000,
        1000000
    };

    pinMode(
        SD_SPI_CS_PIN,
        OUTPUT
    );

    digitalWrite(
        SD_SPI_CS_PIN,
        HIGH
    );

    SPI.begin(
        SD_SPI_SCK_PIN,
        SD_SPI_MISO_PIN,
        SD_SPI_MOSI_PIN,
        SD_SPI_CS_PIN
    );

    delay(500);

    for (
        uint8_t i = 0;
        i < sizeof(speeds) / sizeof(speeds[0]);
        ++i
    ) {

        SD.end();
        delay(150);

        Serial.print(
            "SD begin @ "
        );
        Serial.println(
            speeds[i]
        );

        if (
            SD.begin(
                SD_SPI_CS_PIN,
                SPI,
                speeds[i]
            )
        ) {

            uint8_t cardType =
                SD.cardType();

            if (
                cardType != CARD_NONE
            ) {
                Serial.println(
                    "SD mounted"
                );
                return true;
            }

            Serial.println(
                "SD card none"
            );
        }
    }

    return false;
}

// ======================
// 文本框
// ======================
void drawTextBox() {

    M5.Display.fillRoundRect(
        10,
        10,
        300,
        50,
        12,
        WHITE
    );

    M5.Display.drawRoundRect(
        10,
        10,
        300,
        50,
        12,
        BLACK
    );

    M5.Display.setFont(
        &fonts::efontCN_16
    );

    M5.Display.setTextColor(
        BLACK,
        WHITE
    );

    M5.Display.setCursor(
        20,
        25
    );

    String text =
        displayText;

    if (
        text.length() > 20
    ) {
        text =
            text.substring(
                0,
                20
            );
    }

    M5.Display.print(text);

    M5.Display.setFont(
        &fonts::Font2
    );

    M5.Display.setTextColor(
        WHITE,
        BLACK
    );

    M5.Display.setCursor(
        12,
        64
    );

    M5.Display.print(
        currentPersona
    );
}

void drawDuelTextBox() {

    M5.Display.fillRoundRect(
        8,
        8,
        304,
        54,
        10,
        WHITE
    );

    M5.Display.drawRoundRect(
        8,
        8,
        304,
        54,
        10,
        BLACK
    );

    M5.Display.setFont(
        &fonts::efontCN_16
    );

    M5.Display.setTextColor(
        BLACK,
        WHITE
    );

    M5.Display.setCursor(
        16,
        20
    );

    String text =
        duelText;

    if (
        text.length() > 22
    ) {
        text =
            text.substring(
                0,
                22
            );
    }

    M5.Display.print(text);

    M5.Display.setFont(
        &fonts::Font2
    );

    M5.Display.setTextColor(
        WHITE,
        BLACK
    );

    M5.Display.setCursor(
        10,
        224
    );

    M5.Display.print(
        duelLeftPersona
    );

    M5.Display.setCursor(
        206,
        224
    );

    M5.Display.print(
        duelRightPersona
    );

    int speakerX =
        duelSpeakerPersona == duelLeftPersona ?
        8 :
        166;

    M5.Display.drawRoundRect(
        speakerX,
        64,
        146,
        158,
        8,
        YELLOW
    );
}

void reportPersona() {

    Serial.print(
        "PERSONA|"
    );

    Serial.println(
        currentPersona
    );

    Serial.flush();

    lastPersonaReportAt =
        millis();
}

void selectPersona(
    const String& persona
) {

    if (
        currentPersona ==
        persona
    ) {
        reportPersona();
        return;
    }

    currentPersona =
        persona;

    personaPrefs.putString(
        "persona",
        currentPersona
    );

    duelMode =
        false;

    resetDuelFolders();

    displayText =
        "Persona: " +
        currentPersona;

    resetAnimationFolder();

    M5.Display.fillScreen(
        BLACK
    );

    playAnimationFrame();
    reportPersona();
}

void receivePersonaCommand() {

    String msg =
        Serial.readStringUntil(
            '\n'
        );

    msg.trim();

    Serial.println(
        msg
    );

    String persona =
        "";

    if (
        msg.startsWith(
            "PERSONA|"
        )
    ) {
        persona =
            msg.substring(
                8
            );
    } else if (
        msg.startsWith(
            "SEL|"
        )
    ) {
        persona =
            msg.substring(
                4
            );
    }

    persona.trim();

    if (
        persona.length() > 0
    ) {
        selectPersona(
            persona
        );
    }
}

void receiveDuelCommand() {

    String msg =
        Serial.readStringUntil(
            '\n'
        );

    msg.trim();

    Serial.println(
        msg
    );

    int p1 =
        msg.indexOf(
            '|'
        );

    int p2 =
        msg.indexOf(
            '|',
            p1 + 1
        );

    int p3 =
        msg.indexOf(
            '|',
            p2 + 1
        );

    int p4 =
        msg.indexOf(
            '|',
            p3 + 1
        );

    int p5 =
        msg.indexOf(
            '|',
            p4 + 1
        );

    if (
        p1 < 0 ||
        p2 < 0 ||
        p3 < 0 ||
        p4 < 0 ||
        p5 < 0
    ) {
        Serial.println(
            "DUEL parse fail"
        );
        return;
    }

    duelLeftPersona =
        msg.substring(
            p1 + 1,
            p2
        );

    duelRightPersona =
        msg.substring(
            p2 + 1,
            p3
        );

    duelSpeakerPersona =
        msg.substring(
            p3 + 1,
            p4
        );

    duelState =
        msg.substring(
            p4 + 1,
            p5
        );

    duelText =
        msg.substring(
            p5 + 1
        );

    duelMode =
        true;

    resetAnimationFolder();
    resetDuelFolders();

    M5.Display.fillScreen(
        BLACK
    );

    Serial.print(
        "Duel speaker: "
    );
    Serial.println(
        duelSpeakerPersona
    );

    playDuelFrame();
}

// ======================
// 打开动画目录
// ======================
void openAnimationFolder() {

    if (folderOpened) {
        currentDir.close();
    }
    folderOpened = false;

    if (
        tryOpenAnimationFolder(
            currentState
        )
    ) {
        return;
    }

    if (
        currentState !=
        "idle"
    ) {

        Serial.println(
            "Fallback state: idle"
        );

        currentState =
            "idle";

        tryOpenAnimationFolder(
            currentState
        );
    }
}

bool openDuelFolder(
    File& dir,
    bool& opened,
    const String& persona,
    const String& state
) {

    if (
        !sdReady
    ) {
        return false;
    }

    if (
        opened
    ) {
        dir.close();
    }

    opened =
        false;

    String folder =
        animationFolderPath(
            persona,
            state
        );

    Serial.print(
        "Open duel folder: "
    );
    Serial.println(
        folder
    );

    File next =
        SD.open(folder);

    if (
        !next ||
        !next.isDirectory()
    ) {

        if (next) {
            next.close();
        }

        if (
            state !=
            "idle"
        ) {
            String fallback =
                animationFolderPath(
                    persona,
                    "idle"
                );

            Serial.print(
                "Open duel fallback: "
            );
            Serial.println(
                fallback
            );

            next =
                SD.open(fallback);
        }
    }

    if (
        !next ||
        !next.isDirectory()
    ) {
        Serial.print(
            "Duel folder fail: "
        );
        Serial.println(
            persona
        );

        if (next) {
            next.close();
        }

        return false;
    }

    dir =
        next;
    opened =
        true;

    return true;
}

bool drawNextDuelPersonaFrame(
    File& dir,
    bool& opened,
    const String& persona,
    int32_t x
) {

    if (
        !opened
    ) {
        if (
            !openDuelFolder(
                dir,
                opened,
                persona,
                duelState
            )
        ) {
            return false;
        }
    }

    File file =
        dir.openNextFile();

    if (!file) {
        dir.close();
        opened =
            false;

        if (
            !openDuelFolder(
                dir,
                opened,
                persona,
                duelState
            )
        ) {
            return false;
        }

        file =
            dir.openNextFile();
    }

    if (!file) {
        return false;
    }

    String filename =
        file.name();

    if (
        filename.endsWith(
            ".png"
        ) ||
        filename.endsWith(
            ".PNG"
        )
    ) {

        size_t size =
            file.size();

        uint8_t* buf =
            (uint8_t*)malloc(
                size
            );

        if (buf) {
            file.read(
                buf,
                size
            );

            M5.Display.drawPng(
                buf,
                size,
                x,
                72,
                146,
                146,
                0,
                0,
                0.48f,
                0.48f
            );

            free(buf);
        }
    }

    file.close();
    return true;
}

void playDuelFrame() {

    if (
        isPlayingAudio
    ) {
        drawDuelTextBox();
        return;
    }

    M5.Display.fillRect(
        0,
        64,
        320,
        176,
        BLACK
    );

    drawNextDuelPersonaFrame(
        duelLeftDir,
        duelLeftOpened,
        duelLeftPersona,
        10
    );

    drawNextDuelPersonaFrame(
        duelRightDir,
        duelRightOpened,
        duelRightPersona,
        164
    );

    if (
        !sdReady
    ) {
        M5.Display.fillRoundRect(
            28,
            104,
            86,
            86,
            18,
            DARKGREY
        );
        M5.Display.fillRoundRect(
            206,
            104,
            86,
            86,
            18,
            DARKGREY
        );
        M5.Display.setTextColor(
            WHITE,
            DARKGREY
        );
        M5.Display.setFont(
            &fonts::Font2
        );
        M5.Display.setCursor(
            48,
            142
        );
        M5.Display.print(
            "NO SD"
        );
        M5.Display.setCursor(
            226,
            142
        );
        M5.Display.print(
            "NO SD"
        );
    }

    drawDuelTextBox();

    delay(
        frameDelay
    );
}

// ======================
// 播放一帧
// ======================
void playAnimationFrame() {

    if (
        !enableAnimation
    ) {
        drawTextBox();
        return;
    }

    if (
        isPlayingAudio
    ) {
        drawTextBox();
        return;
    }

    if (
        !folderOpened
    ) {
        openAnimationFolder();
        return;
    }

    File file =
        currentDir.openNextFile();

    // 播放完重新循环
    if (!file) {

        currentDir.close();

        folderOpened =
            false;

        openAnimationFolder();

        return;
    }

    String filename =
        file.name();

    if (
        filename.endsWith(
            ".png"
        ) ||
        filename.endsWith(
            ".PNG"
        )
    ) {

        size_t size =
            file.size();

        uint8_t* buf =
            (uint8_t*)
            malloc(size);

        if (buf) {

            file.read(
                buf,
                size
            );

            M5.Display.drawPng(
                buf,
                size,
                0,
                60
            );

            free(buf);
        }

        drawTextBox();

        delay(frameDelay);
    }

    file.close();
}

// ======================
// PCM 接收
// 协议：
// PCM + uint32 + data
// ======================
void receivePCM(
    char magic0,
    char magic1,
    char magic2
) {

    bool isLegacyPcm =
        magic0 == 'P' &&
        magic1 == 'C' &&
        magic2 == 'M';

    bool hasRateHeader =
        magic0 == 'P' &&
        magic1 == 'C' &&
        magic2 == '2';

    if (
        !isLegacyPcm &&
        !hasRateHeader
    ) {
        return;
    }

    uint32_t sampleRate =
        DEFAULT_AUDIO_SAMPLE_RATE;
    uint32_t pcmSize =
        0;

    if (
        hasRateHeader
    ) {

        while (
            Serial.available() < 8
        );

        Serial.readBytes(
            (char*)&sampleRate,
            4
        );

        Serial.readBytes(
            (char*)&pcmSize,
            4
        );
    } else {

        while (
            Serial.available() < 4
        );

        Serial.readBytes(
            (char*)&pcmSize,
            4
        );
    }

    Serial.print(
        "PCM sample rate: "
    );
    Serial.println(
        sampleRate
    );

    Serial.print(
        "PCM bytes: "
    );
    Serial.println(
        pcmSize
    );

    isPlayingAudio =
        true;

    uint8_t* pcmBuffer =
        (uint8_t*)malloc(
            pcmSize
        );

    if (
        !pcmBuffer
    ) {
        Serial.println(
            "PCM malloc fail"
        );
        isPlayingAudio =
            false;
        return;
    }

    Serial.println(
        "PCM READY"
    );

    uint32_t received =
        0;
    unsigned long lastByteAt =
        millis();

    while (
        received <
        pcmSize
    ) {

        int remain =
            pcmSize -
            received;

        int availableBytes =
            Serial.available();

        if (
            availableBytes <= 0
        ) {
            if (
                millis() -
                lastByteAt > 3000
            ) {
                Serial.print(
                    "PCM receive timeout: "
                );
                Serial.println(
                    received
                );
                free(
                    pcmBuffer
                );
                isPlayingAudio =
                    false;
                return;
            }
            delay(1);
            continue;
        }

        int toRead =
            min(
                remain,
                availableBytes
            );

        int readLen =
            Serial.readBytes(
                (char*)pcmBuffer + received,
                toRead
            );

        if (
            readLen > 0
        ) {

            received +=
                readLen;
            lastByteAt =
                millis();
        } else {
            Serial.println(
                "PCM read timeout"
            );
            delay(1);
        }
    }

    Serial.print(
        "PCM received: "
    );
    Serial.println(
        received
    );

    bool queued =
        M5.Speaker.playRaw(
            (const int16_t*)
            pcmBuffer,

            pcmSize / 2,

            sampleRate,

            false,

            1,

            0,

            true
        );

    Serial.print(
        "PCM queued: "
    );
    Serial.println(
        queued ?
        "yes" :
        "no"
    );

    unsigned long waitStart =
        millis();
    unsigned long playMs =
        (unsigned long)(
            ((uint64_t)(pcmSize / 2) * 1000ULL) /
            sampleRate
        ) + 100;

    while (
        M5.Speaker.isPlaying()
    ) {
        if (
            millis() -
            waitStart > 10000
        ) {
            Serial.println(
                "PCM wait timeout"
            );
            break;
        }
        delay(1);
    }

    delay(
        playMs
    );

    free(
        pcmBuffer
    );

    isPlayingAudio =
        false;

    Serial.println(
        "PCM done"
    );

    if (
        duelMode
    ) {
        resetDuelFolders();
    } else {
        resetAnimationFolder();
    }

    enableAnimation =
        true;
}

// ======================
// setup
// ======================
void setup() {

    auto cfg =
        M5.config();

    M5.begin(cfg);

    Serial.begin(
        2000000
    );

    personaPrefs.begin(
        "persona",
        false
    );

    currentPersona =
        personaPrefs.getString(
            "persona",
            currentPersona
        );

    M5.Display.fillScreen(
        BLACK
    );

    // ======================
    // Speaker
    // ======================
    auto spk_cfg =
        M5.Speaker.config();

    spk_cfg.sample_rate =
        DEFAULT_AUDIO_SAMPLE_RATE;

    M5.Speaker.config(
        spk_cfg
    );

    M5.Speaker.begin();
    M5.Speaker.setVolume(
        180
    );

    sdReady =
        initSDCard();

    if (
        sdReady
    ) {
        M5.Display.println(
            "SD OK"
        );
    } else {
        Serial.println(
            "SD FAIL"
        );

        M5.Display.println(
            "SD FAIL"
        );
    }

    delay(1000);

    M5.Display.fillScreen(
        BLACK
    );

    openAnimationFolder();

    Serial.println(
        "READY"
    );

    reportPersona();
}

// ======================
// loop
// ======================
void loop() {

    M5.update();

    if (
        millis() - lastPersonaReportAt > 2000
    ) {
        reportPersona();
    }

    if (
        M5.BtnA.wasPressed()
    ) {
        selectPersona(
            "zhang_zong"
        );
    }

    if (
        M5.BtnB.wasPressed()
    ) {
        selectPersona(
            "xiao_hong"
        );
    }

    // ======================
    // 串口消息
    // ======================
    if (
        Serial.available()
    ) {

        char c =
            Serial.peek();

        // PCM
        if (
            c == 'P'
        ) {

            while (
                Serial.available() < 3
            ) {
                delay(1);
            }

            char magic0 =
                Serial.read();

            char magic1 =
                Serial.read();

            char magic2 =
                Serial.read();

            if (
                magic0 == 'P' &&
                magic1 == 'C' &&
                (
                    magic2 == 'M' ||
                    magic2 == '2'
                )
            ) {

                receivePCM(
                    magic0,
                    magic1,
                    magic2
                );
            } else if (
                magic0 == 'P' &&
                magic1 == 'E' &&
                magic2 == 'R'
            ) {

                String rest =
                    Serial.readStringUntil(
                        '\n'
                    );

                rest =
                    "PER" +
                    rest;

                rest.trim();

                Serial.println(
                    rest
                );

                String persona =
                    rest.substring(
                        8
                    );

                persona.trim();

                if (
                    rest.startsWith(
                        "PERSONA|"
                    ) &&
                    persona.length() > 0
                ) {
                    selectPersona(
                        persona
                    );
                }
            } else {
                Serial.readStringUntil(
                    '\n'
                );
            }

            return;
        }

        if (
            c == 'S'
        ) {

            receivePersonaCommand();

            return;
        }

        if (
            c == 'D'
        ) {

            receiveDuelCommand();

            return;
        }

        // TXT
        if (
            c == 'T'
        ) {

            String msg =
                Serial.readStringUntil(
                    '\n'
                );

            msg.trim();

            Serial.println(
                msg
            );

            if (
                msg.startsWith(
                    "TXT|"
                )
            ) {

                int p1 =
                    msg.indexOf(
                        '|',
                        4
                    );

                if (
                    p1 > 0
                ) {

                    currentState =
                        msg.substring(
                            4,
                            p1
                        );

                    displayText =
                        msg.substring(
                            p1 + 1
                        );

                    duelMode =
                        false;

                    resetDuelFolders();

                    Serial.print(
                        "State: "
                    );

                    Serial.println(
                        currentState
                    );

                    Serial.print(
                        "Text: "
                    );

                    Serial.println(
                        displayText
                    );

                    resetAnimationFolder();

                    M5.Display.fillScreen(
                        BLACK
                    );

                    enableAnimation =
                        true;

                    playAnimationFrame();
                }
            }
        }
    }

    if (
        duelMode
    ) {
        playDuelFrame();
    } else {
        playAnimationFrame();
    }
}
