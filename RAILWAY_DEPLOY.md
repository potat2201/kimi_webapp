# 🚂 Railway Deployment Guide

快速將 Cool School AI 部署到 Railway 雲端平台

---

## 📋 準備工作

1. 確保你的代碼已經在 GitHub repo
2. 註冊 [Railway](https://railway.app/) 帳號（可用 GitHub 登入）
3. 準備好 Kimi API Key

---

## 🚀 一鍵部署步驟

### Step 1: 連接 GitHub Repo

1. 登入 [Railway Dashboard](https://railway.app/dashboard)
2. 點擊 **"New Project"**
3. 選擇 **"Deploy from GitHub repo"**
4. 選擇你的 `kimi_webapp` repository
5. 點擊 **"Deploy"**

### Step 2: 設定環境變數

1. 在 Railway Dashboard 點擊你的 project
2. 點擊 **"Variables"** tab
3. 新增以下變數：

| 變數名稱 | 值 | 說明 |
|---------|-----|------|
| `SECRET_KEY` | 隨機長字串 | 用於 session 加密，例如：`your-secret-key-123456` |
| `KIMI_API_KEY` | `sk-...` | 你的 Kimi API Key |

4. Railway 會自動偵測 `PORT` 變數，唔需要手動設定

### Step 3: 啟動服務

1. Railway 會自動讀取 `Procfile` 啟動 Gunicorn
2. 等待 build 完成（約 1-2 分鐘）
3. 點擊 **"Deploy"** tab 嘅 URL 即可訪問

---

## 🌐 自訂域名（可選）

1. 在 Railway Dashboard 點擊 **"Settings"**
2. 找到 **"Domains"** 區域
3. 點擊 **"+ Custom Domain"**
4. 輸入你的域名（如：`coolschool.yourdomain.com`）
5. 按照指示設定 DNS CNAME record

---

## 🔄 自動部署

Railway 已經設定好自動部署：

- 每次 push 到 `main` branch → 自動重新部署
- 可在 Settings 關閉自動部署

---

## 📊 監控與日誌

- **Logs**: Railway Dashboard → 點擊服務 → "Deployments" tab → 點擊 deployment 睇 log
- **Metrics**: 可查看 CPU、Memory 使用量

---

## 💰 費用

- **免費額度**: US$5/月（足夠個人/小型學校使用）
- **收費**: 按實際使用量計算（CPU + Memory + 網絡）
- 詳情參考 [Railway Pricing](https://railway.app/pricing)

---

## 🔧 故障排除

### Build 失敗

檢查 `requirements.txt` 是否包含所有 dependency：
```
flask>=2.0.0
flask-login>=0.6.0
flask-sqlalchemy>=3.0.0
werkzeug>=2.0.0
requests>=2.25.0
PyMuPDF>=1.23.0
Pillow>=10.0.0
gunicorn>=21.0.0
```

### Database 問題

Railway 會自動建立 `instance/` folder 作為 persistent volume，SQLite 數據會保存。

### 服務啟動失敗

1. 檢查環境變數是否正確設定
2. 查看 Logs 睇錯誤訊息
3. 確保 `Procfile` 格式正確（無 BOM，Unix line ending）

---

## 📁 重要檔案說明

| 檔案 | 用途 |
|------|------|
| `requirements.txt` | Python dependencies |
| `Procfile` | 告訴 Railway 點樣啟動服務 |
| `railway.json` | Railway 設定檔（可選） |
| `.gitignore` | 排除唔需要 commit 嘅檔案 |

---

## 🔐 生產環境注意事項

部署後請立即：

1. 用預設帳號 `admin` / `kimi2024` 登入
2. **立即更改密碼**
3. 建立教師帳號
4. 考慮關閉公開註冊（修改 `app.py`）

---

完成！🎉 你嘅 Cool School AI 已經上雲！
