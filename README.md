# nest-cast

用 Cast 協定在區網內控制 Google Nest／Google Home 喇叭的小工具，也是一份實驗紀錄。

起因：用 agent 透過 ADB 改 Google TV 的 skill 很紅，想知道舊的 Nest 能不能比照辦理。

## 結論

Nest 喇叭跑的是 **Cast OS**（Nest Hub 是 Fuchsia），**沒有 ADB、沒有 shell**。
所以 Google TV 那種「精簡系統、刪 app、換 launcher」做不到。

能做的是 Cast 協定開放的部分，不需要 Google 帳號：

| 能力 | 做法 | 實測 |
|---|---|---|
| 找到裝置 | mDNS `_googlecast._tcp` | 成功 |
| 讀裝置資訊（版本、Wi-Fi、地區） | 本機設定 API `http://<ip>:8008/setup/eureka_info`，不需認證 | 成功 |
| 讀狀態、調音量、停止 | Cast v2（TCP 8009） | 成功 |
| 播放網路音訊、TTS 說話 | Default Media Receiver 播放 URL，由喇叭自己去抓 | 成功（BUFFERING → PLAYING → FINISHED） |
| 播放這台電腦上的檔案 | 在本機開 HTTP server 讓喇叭來抓 | 成功（在沙箱外執行） |
| 改系統設定、聽麥克風 | — | 做不到，沒有公開介面 |

實驗裝置：Google Home Mini（第一代），Cast firmware 3.78.540761。

## 使用

需要 [uv](https://docs.astral.sh/uv/) 與 Python 3.11 以上。

```bash
uv sync
uv run nest-cast discover                    # 列出區網上的 Cast 裝置
uv run nest-cast --name 客廳 status          # 音量、目前的 app
uv run nest-cast --name 客廳 info            # 本機設定 API 的完整資訊
uv run nest-cast --name 客廳 say "晚餐好了" --volume 0.3
uv run nest-cast --name 客廳 play https://example.com/a.mp3
uv run nest-cast --name 客廳 play-file ./chime.m4a
uv run nest-cast --name 客廳 volume 0.4
uv run nest-cast --name 客廳 trace           # 印出狀態事件，除錯用
```

- `--host <ip>` 可以跳過 mDNS 探索，直接連線。
- `--volume` 只在這次播放有效，播完會改回原本的音量。
- 所有可調的值（TTS 語言、逾時、port、副檔名對應）都在 [config.toml](config.toml)。
  `[device].default_name` 填好之後就不用每次加 `--name`。

## 程式結構

| 檔案 | 內容 |
|---|---|
| [src/nest_cast/config.py](src/nest_cast/config.py) | 讀 `config.toml` |
| [src/nest_cast/device.py](src/nest_cast/device.py) | 探索、連線、本機設定 API |
| [src/nest_cast/media.py](src/nest_cast/media.py) | 播 URL、TTS、本機檔案、狀態追蹤 |
| [src/nest_cast/cli.py](src/nest_cast/cli.py) | 指令列 |

## 已知限制

- **`play-file` 需要喇叭能主動連進這台電腦。** 在 Claude Code 的沙箱裡跑時，
  inbound 連線會被擋，喇叭會回報 `LOAD FAILED`，沙箱的代理也會回 404。
  請在一般終端機執行，並確認防火牆放行 `[serve].port`。
- 開著 VPN 時，提供給喇叭的網址會用「通往喇叭那條路由」的本機 IP，
  不會誤用 VPN 的位址（踩過這個坑：拿到 172.18.x，喇叭連不到）。
- TTS 用的是 Google Translate 的非正式端點，隨時可能失效；換掉 `[tts].url_template` 即可。
- 只能「說」不能「聽」：Cast 協定拿不到麥克風，也沒辦法用語音觸發這裡的程式。

## 想過但還沒做的用法

- Claude Code／ctd 任務完成或等待權限時，用語音通知
- Unity build、GitLab pipeline 結果廣播
- 會議前的行事曆語音提醒、語音版晨報
- 依時間或天氣播放的房間環境音、桌遊主持人、AI 生成音樂電台
