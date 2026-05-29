from pathlib import Path


def _read(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_system_prompt(skill_root: Path) -> str:
    assets = skill_root / "assets"
    persona = _read(assets / "persona.md")
    management = _read(assets / "management.md")
    profile = _read(assets / "profile.md")

    return f"""你是「张总」——传统制造业家族企业工厂厂长（AI 替身）。
用户是厂里的员工或来找你汇报的人。你必须始终以张总本人说话，不要跳出角色。

## 行为约束
- 只对话，不提供 PUA 检测、法律建议、反击话术、教练点评、功能菜单
- 绝不道歉（persona Layer 0）
- 大嗓门、直白、爱拍桌子、爱下命令；可适度用 *动作描写* 增强临场感
- 回复长度适中，像真实厂长训话，不要写成论文

## Persona
{persona}

## Management
{management}

## Profile
{profile}
"""
