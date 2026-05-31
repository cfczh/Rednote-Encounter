import re
import shutil
import struct
import subprocess
import sys
import unicodedata
import wave
from datetime import datetime
from pathlib import Path

import pypinyin

from zhang_agent.config import resolve_project_path


CHARACTERS = [
    "b",
    "p",
    "m",
    "f",
    "d",
    "t",
    "n",
    "l",
    "g",
    "k",
    "h",
    "j",
    "q",
    "x",
    "zh",
    "ch",
    "sh",
    "r",
    "z",
    "c",
    "s",
    "y",
    "w",
    "a",
    "o",
    "e",
    "i",
    "u",
    "ü",
    "ai",
    "ei",
    "ui",
    "ao",
    "ou",
    "iu",
    "ie",
    "ve",
    "er",
    "an",
    "en",
    "in",
    "un",
    "ün",
    "ang",
    "eng",
    "ing",
    "ong",
    "uang",
    "uan",
    "uai",
    "uo",
    "ua",
    "ia",
    "ian",
    "iang",
    "iong",
    "iao",
]
YUN_MU_LIST = [
    "a",
    "o",
    "e",
    "i",
    "u",
    "ü",
    "ai",
    "ei",
    "ui",
    "ao",
    "ou",
    "iu",
    "ie",
    "ve",
    "er",
    "an",
    "en",
    "in",
    "un",
    "ün",
    "ang",
    "eng",
    "ing",
    "ong",
    "uang",
    "uan",
    "uai",
    "uo",
    "ua",
    "ia",
    "ian",
    "iang",
    "iong",
    "iao",
]


class VocalCNSpeaker:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or resolve_project_path("VocalCN_Python源码")
        self.resources = self.root / "resources"
        self.output = self.root / "output"
        self.output.mkdir(parents=True, exist_ok=True)

        with wave.open(str(self._resource_path("a")), "rb") as file:
            self.channels = file.getnchannels()
            self.sample_width = file.getsampwidth()
            self.sample_rate = file.getframerate()

        self.connection_samples = round(0.005 * self.sample_rate)
        self.characters_sound = self._load_resources()

    def speak(self, text: str) -> Path:
        wav_path = self.synthesize(text)
        self.play(wav_path)
        return wav_path

    def synthesize(self, text: str) -> Path:
        clean = self._clean_text(text)
        if not clean:
            raise ValueError("语音内容为空")

        audio = self._handle_input(clean)
        if not audio:
            raise ValueError(f"语音生成失败：{text}")

        return self._save_file(audio, clean)

    def play(self, wav_path: Path) -> None:
        player = shutil.which("afplay") or shutil.which("aplay") or shutil.which("paplay")
        if not player:
            raise RuntimeError("找不到音频播放器：需要 afplay、aplay 或 paplay")
        subprocess.run([player, str(wav_path)], check=True)

    def _load_resources(self) -> dict[str, list[int]]:
        sounds = {}
        for character in CHARACTERS:
            with wave.open(str(self._resource_path(character)), "rb") as file:
                sample_width = file.getsampwidth()
                samples = file.readframes(file.getnframes())
            sounds[character] = [
                struct.unpack("h", samples[index : index + sample_width])[0]
                for index in range(0, len(samples), sample_width)
            ]
        return sounds

    def _resource_path(self, name: str) -> Path:
        path = self.resources / f"{name}.wav"
        if path.exists():
            return path

        normalized = self.resources / unicodedata.normalize("NFD", f"{name}.wav")
        if normalized.exists():
            return normalized

        raise FileNotFoundError(f"找不到 VocalCN 资源：{path}")

    def _clean_text(self, text: str) -> str:
        text = text.replace(" ", "")
        return re.sub(r"[a-zA-Z]", "!", text)

    def _handle_input(self, text: str) -> list[int]:
        py_list = self._pinyin_tokens(text)
        if not py_list:
            return []

        audio: list[int] = []
        last_cha_ispy = False
        for cha in py_list:
            if not cha:
                continue
            if re.fullmatch(r"[a-z]+", cha):
                try:
                    word = self._build_word(cha)
                except ValueError:
                    audio.extend(self._blank_samples(len(cha)))
                    last_cha_ispy = False
                    continue
                if last_cha_ispy and len(audio) >= self.connection_samples:
                    word_first = word[: self.connection_samples]
                    word_second = word[self.connection_samples :]
                    for index in range(len(audio) - self.connection_samples, len(audio)):
                        offset = index - len(audio) + self.connection_samples
                        if offset >= len(word_first):
                            break
                        audio[index] = audio[index] + word_first[offset]
                    audio.extend(word_second)
                else:
                    audio.extend(word)
                last_cha_ispy = True
            else:
                audio.extend(self._blank_samples(len(cha)))
                last_cha_ispy = False
        return audio

    def _pinyin_tokens(self, text: str) -> list[str]:
        return pypinyin.lazy_pinyin(
            text,
            errors=lambda chars: ["!" for _ in chars],
            strict=False,
        )

    def _blank_samples(self, length: int = 1) -> list[int]:
        return [0] * round(self.sample_rate * max(1, length) * 0.2)

    def _build_word(self, cha: str) -> list[int]:
        if cha in CHARACTERS and cha not in YUN_MU_LIST and len(cha) <= 2:
            return self.characters_sound[cha]

        if cha in YUN_MU_LIST:
            sheng_mu = None
            yun_mu = cha
        else:
            sheng_mu = cha[0]
            yun_mu = cha[1:]

        if sheng_mu and yun_mu and yun_mu[0] == "h":
            yun_mu = cha[2:]
            sheng_mu = sheng_mu + "h"

        if cha in ("nv", "lv", "ju", "qu", "xu", "yu"):
            yun_mu = "ü"
        elif cha in ("jun", "qun", "xun", "yun"):
            yun_mu = "ün"
        elif cha in ("xue", "jue", "que", "yue"):
            yun_mu = "ve"

        if sheng_mu and sheng_mu not in CHARACTERS:
            raise ValueError(f"没有找到对应声母：{sheng_mu}")
        if yun_mu not in CHARACTERS:
            raise ValueError(f"没有找到对应韵母：{yun_mu}")

        sheng_mu_samples = self.characters_sound[sheng_mu] if sheng_mu else []
        yun_mu_samples = self.characters_sound[yun_mu]
        yun_mu_position = round(len(sheng_mu_samples) * 0.5) if sheng_mu else 0
        cha_length = yun_mu_position + len(yun_mu_samples)

        word = []
        for index in range(cha_length):
            if index < yun_mu_position:
                word.append(sheng_mu_samples[index])
            else:
                a = sheng_mu_samples[index] if sheng_mu and index < len(sheng_mu_samples) else 0
                b_index = index - yun_mu_position
                b = yun_mu_samples[b_index] if b_index < len(yun_mu_samples) else 0
                word.append(a + b)
        return word

    def _save_file(self, audio: list[int], text: str) -> Path:
        front_name = text.replace(" ", "")
        if len(front_name) > 3:
            front_name = front_name[:3]
        timestamp = datetime.now().time().replace(microsecond=0)
        output_name = f"{str(timestamp).replace(':', '_')}_{front_name}.wav"
        path = self.output / output_name

        with wave.open(str(path), "wb") as output_file:
            output_file.setparams(
                (self.channels, self.sample_width, self.sample_rate, len(audio), "NONE", "not compressed")
            )
            for sample in audio:
                sample = max(-32768, min(32767, sample))
                output_file.writeframes(struct.pack("h", sample))
        return path


def speak_safely(speaker: VocalCNSpeaker, text: str) -> None:
    try:
        speaker.speak(text)
    except Exception as exc:
        print(f"[语音跳过] {exc}", file=sys.stderr)
