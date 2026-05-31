# Skills 人设库

每个人设一个子目录，通过 **`persona_id`**（目录名或 `meta.json` 里的 `slug`）引用。

## 目录结构

```
skills/
├── zhang_zong/          persona_id: zhang_zong
│   ├── meta.json        ← 推荐：name + slug
│   ├── SKILL.md
│   └── assets/*.md
└── xiao_hong/
    ├── meta.json
    └── ...
```

## 硬件选人设

设备经串口发送（任选）：

```
PERSONA|zhang_zong
SEL|xiao_hong
```

`bridge` 收到后切换当前对话人设。

## HTTP API

```json
POST /v1/chat
{
  "persona_id": "zhang_zong",
  "message": "你好",
  "session_id": "可选"
}
```
