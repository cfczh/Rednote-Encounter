import sys
from pathlib import Path

from zhang_agent.chat import PersonaAgent
from zhang_agent.config import (
    other_device_port,
    other_persona_path,
    resolve_project_path,
    skill_dir,
    zhang_device_port,
)
from zhang_agent.prompt import (
    build_persona_prompt,
    build_system_prompt,
    persona_display_name,
)
from zhang_agent.sessions import Session


def _validate_persona_path(path: Path) -> None:
    if path.is_file():
        return
    if (path / "SKILL.md").exists():
        return
    if any(path.glob("*.md")):
        return
    if (path / "assets").exists() and any((path / "assets").glob("*.md")):
        return
    raise FileNotFoundError(
        f"找不到可用人设文件或 Skill 目录：{path}\n"
        "请放入 .md 文件，或包含 SKILL.md / assets/*.md 的目录。"
    )


def _voice_text(text: str, limit: int | None) -> str:
    if not limit or len(text) <= limit:
        return text
    trimmed = text[:limit].rstrip("，。！？,.!? ")
    return f"{trimmed}。"


def _play_voice(
    speaker,
    text: str,
    local_speak,
    m5_output=None,
    m5_play=None,
    max_chars: int | None = None,
) -> None:
    text = _voice_text(text, max_chars if m5_output else None)
    if m5_output and m5_play:
        try:
            wav_path = speaker.synthesize(text)
        except Exception as exc:
            print(f"[语音跳过] {exc}", file=sys.stderr)
            return
        m5_play(m5_output, wav_path)
    elif local_speak:
        local_speak(speaker, text)


def run_duel(
    other_path: str | None = None,
    rounds: int = 6,
    topic: str | None = None,
    other_name: str | None = None,
    voice: bool = False,
    voice_output: str = "local",
    zhang_port: str | None = None,
    other_port: str | None = None,
    voice_max_chars: int | None = None,
    display: bool = False,
) -> None:
    zhang_root = skill_dir()
    if not (zhang_root / "assets" / "persona.md").exists():
        print(f"错误：找不到张总 Skill：{zhang_root}", file=sys.stderr)
        sys.exit(1)

    persona_path = resolve_project_path(other_path) if other_path else other_persona_path()
    try:
        _validate_persona_path(persona_path)
    except FileNotFoundError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(1)

    zhang = PersonaAgent(build_system_prompt(zhang_root))
    other = PersonaAgent(build_persona_prompt(persona_path, other_name))
    zhang_session = Session(id="duel-zhang")
    other_session = Session(id="duel-other")
    zhang_audio = None
    other_audio = None

    if voice:
        from zhang_agent.voice import VocalCNSpeaker, speak_safely

        speaker = VocalCNSpeaker()
        if voice_output == "m5":
            from zhang_agent.m5_audio import M5SerialAudioOutput, play_on_m5_safely

            resolved_zhang_port = zhang_port or zhang_device_port()
            resolved_other_port = other_port or other_device_port()
            if not resolved_zhang_port or not resolved_other_port:
                print(
                    "错误：M5Stack 输出需要设置 ZHANG_DEVICE_PORT 和 OTHER_DEVICE_PORT，"
                    "或通过 --zhang-port / --other-port 指定。",
                    file=sys.stderr,
                )
                sys.exit(1)
            zhang_audio = M5SerialAudioOutput(resolved_zhang_port, label="张总设备")
            other_audio = M5SerialAudioOutput(resolved_other_port, label="小红设备")
            if voice_max_chars is None:
                voice_max_chars = 10
        else:
            play_on_m5_safely = None
    else:
        speaker = None
        speak_safely = None
        play_on_m5_safely = None

    bridge = None
    other_board_persona = persona_path.name  # e.g. "xiao_hong"
    if display:
        if voice and voice_output == "m5":
            print("[Bridge] 警告：--display 与 --voice-output m5 共用同一串口会冲突，跳过显示桥接。")
        else:
            from zhang_agent.serial_bridge import M5SerialBridge
            resolved_zhang = zhang_port or zhang_device_port()
            resolved_other = other_port or other_device_port()
            ports = [p for p in [resolved_zhang, resolved_other] if p]
            if ports:
                bridge = M5SerialBridge(ports)
            else:
                print("[Bridge] 未指定串口，跳过显示桥接。请用 --zhang-port / --other-port 指定。")

    other_label = other_name or persona_display_name(persona_path)
    message = topic or "张总，今天我们聊聊工厂管理和人怎么带。"

    print("双 Agent 对话")
    print(f"张总 Skill: {zhang_root}")
    print(f"{other_label} 人设: {persona_path}")
    print(f"轮数: {rounds}\n")

    for index in range(1, rounds + 1):
        zhang_reply = zhang.reply(zhang_session, f"{other_label}：{message}")
        print(f"[{index}. 张总]\n{zhang_reply}\n")
        if bridge and bridge.connected:
            bridge.send_duel("zhang_zong", other_board_persona, "zhang_zong", "chat", zhang_reply)
        if speaker and speak_safely:
            _play_voice(
                speaker,
                zhang_reply,
                speak_safely,
                zhang_audio,
                play_on_m5_safely,
                voice_max_chars,
            )

        other_reply = other.reply(other_session, f"张总：{zhang_reply}")
        print(f"[{index}. {other_label}]\n{other_reply}\n")
        if bridge and bridge.connected:
            bridge.send_duel("zhang_zong", other_board_persona, other_board_persona, "chat", other_reply)
        if speaker and speak_safely:
            _play_voice(
                speaker,
                other_reply,
                speak_safely,
                other_audio,
                play_on_m5_safely,
                voice_max_chars,
            )

        message = other_reply

    if zhang_audio:
        zhang_audio.close()
    if other_audio:
        other_audio.close()
    if bridge:
        bridge.send_act("leave")
        bridge.close()
