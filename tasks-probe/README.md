# tasks-probe：用 Google Tasks 把語音指令傳成文字

Google Assistant 的「提醒我…」會寫進 Google Tasks，所以這是把**任意文字**從客廳傳到 Mac 的通道。

| 檔案 | 作用 |
|---|---|
| [watch_tasks.py](watch_tasks.py) | 輪詢所有清單裡 `updatedMin`（啟動時間）之後的任務，每筆新任務印一行 JSON（含 `list_id`、`id`） |
| [finish_task.py](finish_task.py) | 處理完後刪除任務；標題不是「機器人」開頭就拒絕，不會誤刪自己的待辦 |

```bash
export GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws-personal   # 綁 Google Home 的那個帳號
python3 watch_tasks.py --poll 5 --fast-poll 1 --fast-for 90
python3 finish_task.py <list_id> <task_id>
```

`watch_tasks.py` 也會看 [../matter-trigger/](../matter-trigger/README.md) 的 `events.jsonl`：
門鈴一響，就改成每 `--fast-poll` 秒輪詢，持續 `--fast-for` 秒。

## 設定

- `gws` 的個人帳號要有 `https://www.googleapis.com/auth/tasks` scope（要刪除，唯讀不夠），
  而且 `gws` 用的那個 GCP 專案要啟用 Tasks API。
- 重新授權後如果還是回報 scope 不足，把 `token_cache.json` 移開，讓 gws 重新拿 token。

## 觀察（2026-11-08）

- 任務會進 **TODO** 清單（不是另外一個「提醒」清單），到期日只有日期，沒有時間。
- Assistant 會改寫句子：「提醒我請機器人查明天天氣」變成「機器人查明天天氣」。
- 從說完到 Tasks 出現，要等 Google 處理，體感偏慢；Mac 這邊在任務建立後 0.2～2 秒內讀到。
- 語音辨識可能錯得離譜（「發文到 Slack」被寫成「撥聞到 snake」），看不懂就先問、不要猜。
