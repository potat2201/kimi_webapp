#!/bin/bash
# Cool School AI - 一鍵部署 Script
# 用法: ./deploy.sh "改動描述"

# 顏色設定
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 檢查參數
if [ -z "$1" ]; then
    echo -e "${RED}❌ 錯誤：請提供改動描述${NC}"
    echo "用法: ./deploy.sh \"修復了某某問題\""
    echo "   或: ./deploy.sh \"add new feature\""
    exit 1
fi

COMMIT_MSG="$1"

echo -e "${YELLOW}🚀 開始部署 Cool School AI...${NC}"
echo ""

# 檢查是否喺正確目錄
if [ ! -f "app.py" ]; then
    echo -e "${RED}❌ 錯誤：請先進入 kimi_webapp 目錄${NC}"
    echo "cd /Users/foxx/.openclaw/workspace/kimi_webapp"
    exit 1
fi

# 顯示現狀
echo -e "${YELLOW}📋 現狀檢查...${NC}"
git status --short
echo ""

# 加入所有改動
echo -e "${YELLOW}➕ 加入改動...${NC}"
git add .

# Commit
echo -e "${YELLOW}💾 Commit: $COMMIT_MSG${NC}"
git commit -m "$COMMIT_MSG"

# Push 到 GitHub
echo -e "${YELLOW}📤 Push 到 GitHub...${NC}"
git push

# 檢查結果
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 部署成功！${NC}"
    echo -e "${GREEN}🌐 Railway 會自動更新（約 30 秒 - 1 分鐘）${NC}"
    echo ""
    echo "查看部署狀態:"
    echo "  https://railway.app/dashboard"
else
    echo ""
    echo -e "${RED}❌ 部署失敗，請檢查錯誤訊息${NC}"
    exit 1
fi
