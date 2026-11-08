# matter-trigger：用語音觸發這台 Mac

在 Mac 上模擬一盞 Matter 可調光燈，加進 Google Home 之後，就能用「Hey Google」觸發 Mac 上的程式。
亮度 0–100 可以當成參數，一句話就能選擇不同的動作。

```
「Hey Google，把機器人調到 30%」
  → Google Assistant（雲端辨識）→ Google 的 Matter 控制端
  → 區網 Matter：levelControl.moveToLevelWithOnOff level=76
  → trigger.mjs：換算成 30%，執行 config.onTriggerWithLevel
  → nest-cast 讓喇叭說「收到，參數 30」→ 1.5 秒後自動關燈，等下一次觸發
```

## 執行

```bash
npm install
node trigger.mjs        # 要在 Claude Code 沙箱外執行：Matter 需要 inbound mDNS／UDP
```

第一次執行會印出 QR code 和手動配對碼，用 Google Home App 的「新增 → Matter 支援裝置」配對。
所有設定都在 [config.json](config.json)；事件會逐行寫進 `events.jsonl`。

## 實驗結果（2026-11-08，Google Home Mini 第一代當 hub）

| 問題 | 結果 |
|---|---|
| App 按鈕能觸發嗎？ | 可以。命令到達後 22ms 內記錄完成 |
| 語音能觸發嗎？ | **可以，但要先註冊**（見下方） |
| 能帶參數嗎？ | 可以。「調到 30%」會收到 `moveToLevelWithOnOff level=76`，換算後是 30 |
| 觸發到喇叭回應 | 約 4 秒（主要花在 nest-cast 啟動與 TTS） |
| 斷網還能用嗎？ | 沒測。語音辨識在雲端，預期不行 |
| 從說完話到命令抵達 | 沒測 |

### 踩過的坑

- **沒註冊的測試裝置，語音會被擋**：App 按得動，但 Assistant 回「this device didn't setup yet」。
  到 [Google Home Developer Console](https://console.home.google.com/) 建立專案，新增 Matter integration
  （VID `0xFFF1`、PID `0x8000`，跟 config.json 一致），再重新配對，語音就能用了。
- **在 App 裡移除裝置，Google 不一定會通知裝置**：裝置會以為自己還在配對中，掃 QR code 會失敗。
  解法是停掉程式，刪除 `.matter-storage/`，再重新啟動。
- **「打開」不帶亮度**：單純「打開」只會送 `onOff.on`；「調到 N%」則是一個命令同時開燈加設定亮度。
  所以程式在收到 ON 後等 `collectLevelMs`，只有跟 ON 一起到的亮度才算參數，避免把上一次的亮度誤當成這次的。
- **觸發詞**：例行程序用「叫 Claude」時沒有反應（推測「叫」被當成打電話）。直接說「打開＋裝置名」最穩。
- Google 會加兩組配對：其中 fabric #2 的管理者廠商 ID 是 0x6006（Google），App 和語音的命令都從這組進來，
  所以 Mac 這邊分不出是語音還是 App 觸發的。

## 限制

- 只能傳數字（0–100），不能傳文字。文字改走 Google Tasks，見下一節。

## 後續：用 Google Tasks 傳文字（[../tasks-probe/](../tasks-probe/watch_tasks.py)）

- 「Hey Google，提醒我請機器人查一個 AI 新聞」會在 Google Tasks 的 TODO 清單建立「機器人要幫我查一個AI新聞」。
  Assistant 會改寫句子（拿掉「提醒我請」），到期日只有日期。
- `watch_tasks.py` 用 `gws` 輪詢 `updatedMin` 之後的任務；看到門鈴的 TRIGGER 就改成每秒輪詢一段時間。
- 2026-11-08 實測：任務建立後 0.2 秒讀到；由 Claude session 查新聞並用 `nest-cast say` 回覆，整個來回約 70 秒，
  最花時間的是處理本身。門鈴加速還沒實測到。
- 需要個人帳號的 `tasks.readonly` scope，以及該 GCP 專案啟用 Tasks API。
