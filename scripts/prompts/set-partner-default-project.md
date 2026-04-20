# Agent Prompt: 設定所有 Partner 的 default_project

## 你的任務

ZenOS 多租戶系統裡，每個 partner（API key）需要有一個 `default_project` 欄位，
用來讓 server 自動隔離不同專案的 tasks——不論 agent 有沒有帶 project 參數，都不會撈到別人的任務。

你的工作是：
1. 讀出 Firestore 裡所有 active partners
2. 列出目前每個 partner 的狀態（有沒有 `default_project`）
3. 對每個缺少 `default_project` 的 partner，推斷應該是哪個 project
4. 寫入 Firestore 完成設定
5. 回報結果

---

## 執行步驟

### Step 1：列出所有 partners

用下面的 Python 腳本讀取 Firestore，**用 Bash tool 執行**：

```python
import os
from google.cloud import firestore

db = firestore.Client(project="zenos-naruvia")
docs = db.collection("partners").where("status", "==", "active").stream()

print("=== 目前 Partners ===")
for doc in docs:
    data = doc.to_dict()
    print(f"""
ID: {doc.id}
  displayName : {data.get('displayName', '?')}
  email       : {data.get('email', '?')}
  default_project: {data.get('default_project', '【未設定】')}
""")
```

### Step 2：推斷 default_project 規則

根據 partner 的 `displayName`、`email` 或其他欄位，用以下規則推斷：

| 線索 | 推斷的 default_project |
|------|----------------------|
| displayName 或 email 包含 "zenos" / "naruvia" / "barry" | `"zenos"` |
| displayName 或 email 包含 "paceriz" | `"paceriz"` |
| 其他 / 無法判斷 | 用 `displayName` 的小寫、空格換底線作為 project ID，例如 "Marketing Partner" → `"marketing_partner"` |

**如果你不確定某個 partner 應該歸哪個 project，不要猜——把它列在「需要人工確認」清單，先跳過，處理其他確定的。**

### Step 3：更新 Firestore

對每個已確認的 partner，用下面的腳本設定（一次處理一個）：

```python
from google.cloud import firestore
from datetime import datetime, timezone

db = firestore.Client(project="zenos-naruvia")

updates = [
    # ("partner_document_id", "default_project_value"),
    # 根據 Step 1 的結果填入，例如：
    # ("abc123", "zenos"),
    # ("def456", "paceriz"),
]

for partner_id, default_project in updates:
    db.collection("partners").document(partner_id).update({
        "default_project": default_project,
        "updatedAt": datetime.now(timezone.utc),
    })
    print(f"✅ {partner_id} → default_project = '{default_project}'")

print("Done.")
```

### Step 4：驗證

更新完後，重新執行 Step 1 的腳本確認每個 partner 都有 `default_project`。

---

## 輸出格式

完成後回報：

```
## Partner default_project 設定結果

### 已更新
| Partner ID | displayName | default_project |
|------------|-------------|-----------------|
| ...        | ...         | ...             |

### 需要人工確認（未動）
| Partner ID | displayName | 原因 |
|------------|-------------|------|
| ...        | ...         | 無法從現有資料推斷專案歸屬 |

### 驗證
所有 partners 讀取結果：（貼上 Step 4 的輸出）
```

---

## 注意事項

- **不要修改 `apiKey`、`status`、`isAdmin` 等其他欄位**，只加 `default_project` 和更新 `updatedAt`
- **只處理 status=active 的 partners**
- 如果有任何 Python 執行錯誤，貼出完整 error message，不要猜測原因
- Firestore project 固定是 `zenos-naruvia`，不用問
