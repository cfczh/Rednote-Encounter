import struct
import sys
import time
from datetime import datetime
from pathlib import Path
from pypinyin import Style, lazy_pinyin
import pypinyin
import serial
import wave
import re


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _tick(label: str, t0: float, indent: int = 0) -> float:
    now = time.perf_counter()
    prefix = "  " * indent
    _log(f"{prefix}[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {label} (+{now - t0:.3f}s)")
    return now

# =========================
# 配置
# =========================
SERIAL_PORT = "/dev/cu.usbmodem1101"
BAUDRATE = 2000000

RESOURCE_DIR = Path(__file__).parent / "resources"
ANIMALESE_DIR = (
    Path(__file__).resolve().parent.parent /
    "Animalese-Synthesizer-master"
)
ANIMALESE_PHONEME_DIR = ANIMALESE_DIR / "pinyin_phonemes"

# =========================
# 拼音资源
# =========================
characters = [
    'b', 'p', 'm', 'f', 'd', 't', 'n', 'l',
    'g', 'k', 'h', 'j', 'q', 'x',
    'zh', 'ch', 'sh', 'r',
    'z', 'c', 's', 'y', 'w',

    'a', 'o', 'e', 'i', 'u', 'ü',
    'ai', 'ei', 'ui', 'ao', 'ou',
    'iu', 'ie', 've', 'er',

    'an', 'en', 'in', 'un', 'ün',
    'ang', 'eng', 'ing', 'ong',

    'uang', 'uan', 'uai',
    'uo', 'ua', 'ia',
    'ian', 'iang', 'iong', 'iao'
]

yun_mu_list = [
    'a', 'o', 'e', 'i', 'u', 'ü',
    'ai', 'ei', 'ui', 'ao', 'ou',
    'iu', 'ie', 've', 'er',

    'an', 'en', 'in', 'un', 'ün',
    'ang', 'eng', 'ing', 'ong',

    'uang', 'uan', 'uai',
    'uo', 'ua', 'ia',
    'ian', 'iang', 'iong', 'iao'
]

# =========================
# 基础 wav 参数
# =========================
sample_file = wave.open(
    str(RESOURCE_DIR / "a.wav"),
    "rb"
)

sampleRate = sample_file.getframerate()
sample_file.close()
OUTPUT_SAMPLE_RATE = 16000

# =========================
# 加载资源
# =========================
characters_sound = {}
animalese_sound = {}
animalese_sample_rate = 48000

print("Loading VocalCN resources...")

for c in characters:

    wav_path = RESOURCE_DIR / f"{c}.wav"

    if not wav_path.exists():
        print(f"Missing wav: {wav_path}")
        continue

    file = wave.open(
        str(wav_path),
        "rb"
    )

    samples = file.readframes(
        file.getnframes()
    )

    sw = file.getsampwidth()

    pcm = []

    for i in range(
        0,
        len(samples),
        sw
    ):
        pcm.append(
            struct.unpack(
                "<h",
                samples[i:i+sw]
            )[0]
        )

    characters_sound[c] = pcm

    file.close()

print("VocalCN ready.")

if ANIMALESE_PHONEME_DIR.exists():
    print("Loading Animalese resources...")

    for wav_path in ANIMALESE_PHONEME_DIR.glob("*.wav"):
        try:
            file = wave.open(
                str(wav_path),
                "rb"
            )
        except wave.Error:
            continue

        animalese_sample_rate = file.getframerate()

        samples = file.readframes(
            file.getnframes()
        )

        sw = file.getsampwidth()
        channels = file.getnchannels()
        pcm = []

        frame_width = (
            sw * channels
        )

        for i in range(
            0,
            len(samples),
            frame_width
        ):
            pcm.append(
                struct.unpack(
                    "<h",
                    samples[i:i + sw]
                )[0]
            )

        animalese_sound[wav_path.stem] = pcm
        file.close()

    print("Animalese ready.")

# =========================
# 拼音处理
# =========================
def get_pinyin(text):

    text = re.sub(
        r"[a-zA-Z]",
        " ",
        text
    )

    return pypinyin.slug(
        text,
        separator=" "
    )


def split_pinyin(py):

    if py in yun_mu_list:
        return None, py

    if py.startswith("zh"):
        return "zh", py[2:]

    if py.startswith("ch"):
        return "ch", py[2:]

    if py.startswith("sh"):
        return "sh", py[2:]

    sheng_mu = py[0]
    yun_mu = py[1:]

    # ü 特殊处理
    if py in [
        "ju", "qu", "xu", "yu"
    ]:
        yun_mu = "ü"

    elif py in [
        "jue", "que",
        "xue", "yue"
    ]:
        yun_mu = "ve"

    elif py in [
        "jun", "qun",
        "xun", "yun"
    ]:
        yun_mu = "ün"

    return sheng_mu, yun_mu


def clean_animalese_text(text: str) -> str:
    return re.sub(
        r"[？ 、；！，。“”?.~…,$\r\n《》——：:、]|(<.*>)",
        "",
        text.strip()
    )


def animalese_phonemes(text: str) -> list[str]:
    cleaned = clean_animalese_text(
        text
    )

    initials = lazy_pinyin(
        cleaned,
        style=Style.INITIALS,
        errors="ignore",
        strict=True
    )

    finals = lazy_pinyin(
        cleaned,
        style=Style.FINALS,
        errors="ignore",
        strict=True
    )

    phonemes = []

    for initial, final in zip(
        initials,
        finals
    ):
        if initial:
            phonemes.append(initial)
        if final:
            phonemes.append(final)

    return phonemes


def scale_samples(
    samples: list[int],
    gain: float
) -> list[int]:
    return [
        max(
            -32768,
            min(
                32767,
                int(s * gain)
            )
        )
        for s in samples
    ]


def append_with_crossfade(
    audio: list[int],
    chunk: list[int],
    overlap: int
) -> None:
    if (
        not audio or
        not chunk or
        overlap <= 0
    ):
        audio.extend(chunk)
        return

    actual = min(
        overlap,
        len(audio),
        len(chunk)
    )

    start = (
        len(audio) -
        actual
    )

    for i in range(actual):
        fade_in = (
            (i + 1) / actual
        )
        fade_out = (
            1.0 - fade_in
        )
        mixed = (
            audio[start + i] * fade_out +
            chunk[i] * fade_in
        )
        audio[start + i] = max(
            -32768,
            min(
                32767,
                int(mixed)
            )
        )

    audio.extend(
        chunk[actual:]
    )


def synthesize_animalese(text: str) -> tuple[list[int], int]:
    """用 Animalese 拼音音素包合成小红声音，返回 PCM samples 和采样率。"""
    t0 = time.perf_counter()
    phonemes = animalese_phonemes(text)
    t0 = _tick(f"animalese: 转音素 ({len(phonemes)} phonemes)", t0, indent=2)

    audio = []
    overlap = int(
        animalese_sample_rate * 0.004
    )

    for phoneme in phonemes:
        samples = animalese_sound.get(
            phoneme
        )

        if not samples:
            continue

        # Animalese 原音素较长；压短后更像“动物语”碎音。
        clipped = samples[
            : max(
                1,
                int(len(samples) * 0.08)
            )
        ]

        append_with_crossfade(
            audio,
            scale_samples(
                clipped,
                0.8
            ),
            overlap
        )

    _tick(
        f"animalese: PCM 合成完成 ({len(audio)} samples, {len(audio)/animalese_sample_rate:.2f}s 音频)",
        t0,
        indent=2
    )

    return audio, animalese_sample_rate


# =========================
# PCM 合成
# =========================
secondPosition = 0.5
connectionPosition = 0.005

connectionSamples = round(
    connectionPosition *
    sampleRate
)


def handle_input(text):

    t0 = time.perf_counter()
    py_list = get_pinyin(text).split()
    t0 = _tick(f"handle_input: 转拼音 ({len(py_list)} 音节)", t0, indent=2)

    audio = []
    last_is_py = False

    for py in py_list:
        if not py:
            continue

        if not py[0].isalpha():

            blank_num = int(
                sampleRate * 0.15
            )

            audio.extend(
                [0] * blank_num
            )

            last_is_py = False
            continue

        sheng_mu, yun_mu = split_pinyin(py)

        if yun_mu not in characters_sound:
            print(
                "missing yunmu:",
                yun_mu
            )
            continue

        sheng_samples = []

        if (
            sheng_mu and
            sheng_mu in characters_sound
        ):
            sheng_samples = (
                characters_sound[
                    sheng_mu
                ]
            )

        yun_samples = (
            characters_sound[
                yun_mu
            ]
        )

        yun_pos = 0

        if sheng_samples:
            yun_pos = int(
                len(
                    sheng_samples
                ) *
                secondPosition
            )

        word = []

        total_len = (
            yun_pos +
            len(yun_samples)
        )

        for i in range(total_len):

            a = 0
            b = 0

            if (
                sheng_samples and
                i < len(sheng_samples)
            ):
                a = sheng_samples[i]

            if (
                i >= yun_pos and
                i - yun_pos <
                len(yun_samples)
            ):
                b = yun_samples[
                    i - yun_pos
                ]

            word.append(a + b)

        # overlap 拼接
        if (
            last_is_py and
            len(audio) >
            connectionSamples
        ):

            overlap = min(
                connectionSamples,
                len(word)
            )

            start = (
                len(audio) -
                overlap
            )

            for j in range(overlap):

                mixed = (
                    audio[start + j]
                    + word[j]
                )

                audio[start + j] = max(
                    -32768,
                    min(32767, mixed)
                )

            audio.extend(
                word[overlap:]
            )

        else:
            audio.extend(word)

        last_is_py = True

    _tick(f"handle_input: PCM 合成完成 ({len(audio)} samples, {len(audio)/sampleRate:.2f}s 音频)", t0, indent=2)
    return audio


def resample_samples(samples, source_rate, target_rate):
    if source_rate == target_rate or not samples:
        return samples

    target_len = max(
        1,
        int(len(samples) * target_rate / source_rate)
    )

    resampled = []

    for i in range(target_len):
        src_pos = i * source_rate / target_rate
        left = int(src_pos)
        right = min(
            left + 1,
            len(samples) - 1
        )
        frac = src_pos - left
        value = int(
            samples[left] * (1.0 - frac) +
            samples[right] * frac
        )
        resampled.append(value)

    return resampled

# =========================
# M5 串口音频
# =========================
class M5SerialAudioOutput:

    def __init__(self, ser):

        self.ser = ser
        _log("M5 connected")

    def play_raw(
        self,
        samples,
        source_rate=sampleRate
    ):

        t0 = time.perf_counter()
        CHUNK = 64
        output_rate = OUTPUT_SAMPLE_RATE
        samples = resample_samples(
            samples,
            source_rate,
            output_rate
        )

        pcm_bytes = b"".join(
            struct.pack(
                "<h",
                max(
                    -32768,
                    min(32767, s)
                )
            )
            for s in samples
        )
        t0 = _tick(f"play_raw: PCM 打包 ({len(pcm_bytes)} bytes)", t0, indent=2)

        # 协议头
        self.ser.write(
            b"PC2" +
            struct.pack(
                "<I",
                output_rate
            ) +
            struct.pack(
                "<I",
                len(pcm_bytes)
            )            
        )
        self.ser.flush()
        t0 = _tick(f"play_raw: 发送 PCM 协议头 ({output_rate} Hz)", t0, indent=2)

        ready_deadline = time.time() + 15.0
        got_ready = False
        while time.time() < ready_deadline:
            if not self.ser.in_waiting:
                time.sleep(0.02)
                continue
            raw = self.ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                _log(f"  M5: {text}")
            if "PCM READY" in text:
                got_ready = True
                break
        if not got_ready:
            raise serial.SerialException(
                "M5 did not become ready for PCM data (timeout 15s; "
                "ensure TXT finished on device before PCM)"
            )

        sent = 0

        while sent < len(pcm_bytes):

            chunk = pcm_bytes[
                sent:
                sent + CHUNK
            ]

            self.ser.write(chunk)
            self.ser.flush()
            time.sleep(0.003)

            sent += len(chunk)

        self.ser.flush()
        _tick(f"play_raw: 串口发送音频数据 ({len(pcm_bytes)} bytes)", t0, indent=2)

        from persona_agent.hardware import wait_playback_done

        wait_playback_done(self.ser, len(pcm_bytes), output_rate)
        return len(pcm_bytes), output_rate

    def close(self):
        self.ser.close()


# =========================
# 单例
# =========================
_m5 = None


def get_m5(ser):

    global _m5

    if _m5 is None:
        _m5 = M5SerialAudioOutput(ser)

    return _m5


def reset_m5() -> None:
    global _m5
    _m5 = None


# =========================
# 外部调用函数
# =========================
def speak(
    text: str,
    ser,
    persona_id: str = "zhang_zong"
) -> dict[str, float]:
    """合成并播放；返回各阶段耗时（秒）。"""
    timings: dict[str, float] = {}
    if not text:
        return timings

    t_round = time.perf_counter()
    t0 = time.perf_counter()
    if (
        persona_id == "xiao_hong" and
        animalese_sound
    ):
        samples, source_rate = synthesize_animalese(
            text
        )
    else:
        samples = handle_input(text)
        source_rate = sampleRate

    timings["synthesis"] = time.perf_counter() - t0

    if not samples:
        _tick("speak: 无音频样本，跳过", t_round, indent=1)
        return timings

    t0 = time.perf_counter()
    m5 = get_m5(ser)
    timings["m5_init"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    m5.play_raw(
        samples,
        source_rate
    )
    timings["serial_play"] = time.perf_counter() - t0

    timings["speak_total"] = time.perf_counter() - t_round
    _tick(f"speak 合计 ({timings['speak_total']:.3f}s)", t_round, indent=1)
    return timings
