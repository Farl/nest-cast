# nest-cast：用舊的 Google Home 喇叭指揮 Claude

對客廳的 Google Home Mini 說一句話，Claude 就在 Mac 上把事情做完，再用同一顆喇叭唸結果給你聽，
最後自動清掉這次的紀錄。

```
「Hey Google，提醒我今天請機器人 <要做的事>」
  │  Google Assistant 把句子寫進 Google Tasks（標題：機器人<要做的事>）
  │
  │  （可選）「Hey Google，打開機器人」── 門鈴：Matter 虛擬燈，讓 Mac 立刻改成每秒檢查
  ▼
tasks-probe/watch_tasks.py   輪詢 Google Tasks，挑出「機器人」開頭的新任務
  ▼
Claude session               依內容完成工作；對外動作（發訊息、刪東西、付款）先在電腦上確認
  ▼
nest-cast say                在喇叭上唸結果（長文自動分段）
  ▼
tasks-probe/finish_task.py   唸完才刪掉任務；只刪「機器人」開頭的任務
```

## 實測（2026-11-08，Google Home Mini 第一代）

| 指令（Tasks 裡的標題） | 結果 | 時間 |
|---|---|---|
| 機器人要幫我查一個AI新聞 | 搜尋後唸出一則新聞 | 任務建立到唸完約 70 秒，大多花在搜尋 |
| 機器人幫我撥聞到snake說 | 原意是「發文到 Slack 說一則笑話」：先在喇叭說聽不懂、在電腦上確認後私訊到自己的 Slack，唸完後刪除任務 | 確認後約 34 秒 |

- 任務建立後，最慢在一個輪詢間隔（平常 5 秒、門鈴響後 1 秒）內就會讀到。
- 最弱的一環是 **Assistant 的語音辨識**：「發文到 Slack」被寫成「撥聞到 snake」。
  聽不懂的指令不要猜，先問、任務先留著。
- Assistant 會改寫句子（拿掉「提醒我請」），所以用「機器人」當開頭，方便跟自己的待辦分開。

## 怎麼跑起來

1. **喇叭**：`uv sync`，確認 `uv run nest-cast discover` 找得到喇叭。
2. **Google Tasks**：個人帳號的 `gws` 要有 `https://www.googleapis.com/auth/tasks` scope，
   而且那個 GCP 專案要啟用 Tasks API。細節見 [tasks-probe/](tasks-probe/README.md)。
3. **門鈴（可選）**：`cd matter-trigger && npm install && node trigger.mjs`，用 Google Home App 配對。
   語音要能觸發，測試裝置必須先在 Google Home Developer Console 註冊。見 [matter-trigger/](matter-trigger/README.md)。
4. **處理者**：在 Claude Code session 裡監看 `watch_tasks.py` 的輸出，收到任務就做事、`say`、`finish_task.py`。

需要 inbound 連線的部分（Matter、`play-file`）要在 Claude Code 沙箱外執行。

## 目前的限制

- **要靠 Claude session 開著。** 監看是 session 裡的背景工作，關掉就沒有人接手，
  提醒會留在 Tasks 裡。想常駐要改成服務（例如收到任務就啟動 `claude -p`），
  但那樣就沒有人能即時確認對外的動作，需要另外設計。
- **門鈴只能傳數字**（開關、0–100 的亮度），文字一定要走 Tasks。
- TTS 用的是 Google Translate 的非正式端點，隨時可能失效；換掉 `config.toml` 的 `[tts].url_template` 即可。

## 組成

| 資料夾／指令 | 角色 |
|---|---|
| [`nest-cast`](src/nest_cast/) CLI | 喇叭的「嘴巴」：探索、狀態、TTS、播放、音量 |
| [tasks-probe/](tasks-probe/README.md) | 文字通道：監看 Google Tasks、處理完刪除 |
| [matter-trigger/](matter-trigger/README.md) | 門鈴：Matter 虛擬燈，把語音變成即時觸發與 0–100 參數 |

### nest-cast CLI

```bash
uv run nest-cast discover                    # 列出區網上的 Cast 裝置
uv run nest-cast --name 客廳 status          # 音量、目前的 app
uv run nest-cast --name 客廳 info            # 喇叭本機設定 API 的資訊（版本、Wi-Fi、地區）
uv run nest-cast --name 客廳 say "晚餐好了" --volume 0.3
uv run nest-cast --name 客廳 play https://example.com/a.mp3
uv run nest-cast --name 客廳 play-file ./chime.m4a
uv run nest-cast --name 客廳 volume 0.4
uv run nest-cast --name 客廳 stop
uv run nest-cast --name 客廳 trace           # 印出狀態事件，除錯用
```

- `--name` 找到裝置就繼續，不用等滿逾時；`--host <ip>` 直接連線，跳過探索。
- `--volume` 只在這次播放有效，播完改回原本的音量。
- 可調的值都在 [config.toml](config.toml)：TTS 語言與分段長度、逾時、port、副檔名對應。

| 檔案 | 內容 |
|---|---|
| [src/nest_cast/config.py](src/nest_cast/config.py) | 讀 `config.toml` |
| [src/nest_cast/device.py](src/nest_cast/device.py) | 探索、連線、本機設定 API |
| [src/nest_cast/media.py](src/nest_cast/media.py) | 播 URL、TTS（含長文分段）、本機檔案、狀態追蹤 |
| [src/nest_cast/cli.py](src/nest_cast/cli.py) | 指令列 |

## 背景：為什麼不是 ADB

起因是用 agent 透過 ADB 改 Google TV 的 skill 很紅，想知道舊的 Nest 能不能比照辦理。

不行：Nest 喇叭跑的是 Cast OS（Nest Hub 是 Fuchsia），沒有 ADB 也沒有 shell，
精簡系統、刪 app、換 launcher 這些都做不到。能用的只有區網上開放的部分，不需要 Google 帳號：

| 能力 | 做法 |
|---|---|
| 找到裝置 | mDNS `_googlecast._tcp` |
| 讀裝置資訊 | 本機設定 API `http://<ip>:8008/setup/eureka_info`，不需認證 |
| 狀態、音量、停止、播放 URL、TTS | Cast v2（TCP 8009），喇叭自己去抓音訊 |
| 改系統設定、聽麥克風 | 做不到。所以「耳朵」要繞道 Google Tasks 和 Matter |

## 踩過的坑

- **沙箱**：Claude Code 沙箱擋 inbound，`play-file` 會 `LOAD FAILED`，Matter 也配對不了。
- **VPN**：`play-file` 給喇叭的網址，要用「通往喇叭那條路由」的本機 IP，不能用 VPN 的位址。
- **mDNS 很慢**：喇叭忙著回應語音時，可能 5 秒內都不回 mDNS。所以改成依名稱查詢，找到就繼續，最多等 10 秒。
- 門鈴與 Tasks 各自的坑，寫在各自的 README。

## 想過但還沒做

- Claude Code／ctd 任務完成或等待權限時，用語音通知
- Unity build、GitLab pipeline 結果廣播
- 會議前的行事曆語音提醒、語音版晨報
