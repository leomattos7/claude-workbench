#!/usr/bin/env bash
# Notification hook: desktop toast when a session asks for permission or input.
# WSL -> Windows toast via powershell.exe; Linux -> notify-send; otherwise no-op.
# Reads the hook JSON on stdin. Never blocks and always exits 0.
payload=$(cat 2>/dev/null || true)

account=$(basename "${CLAUDE_CONFIG_DIR:-$HOME/.claude}")
account=${account#.claude-}
[ "$account" = ".claude" ] && account=default

read_field() { # read_field <key> <fallback>
  printf '%s' "$payload" | python3 -I -c '
import json, sys
print(json.load(sys.stdin).get(sys.argv[1]) or sys.argv[2])' "$1" "$2" 2>/dev/null || printf '%s' "$2"
}

folder=$(basename "$(read_field cwd "")")
title="Claude ($account) · $folder"
body=$(read_field message "needs your attention")

if grep -qi microsoft /proc/version 2>/dev/null && command -v powershell.exe >/dev/null 2>&1; then
  export TOAST_TITLE="$title" TOAST_BODY="$body"
  export WSLENV="TOAST_TITLE:TOAST_BODY${WSLENV:+:$WSLENV}"
  setsid timeout 20 powershell.exe -NoProfile -NonInteractive -Command '
$e=[Security.SecurityElement]
$t=$e::Escape($env:TOAST_TITLE); $b=$e::Escape($env:TOAST_BODY)
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime]
$x=New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml("<toast><visual><binding template=`"ToastGeneric`"><text>$t</text><text>$b</text></binding></visual></toast>")
$id="{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show([Windows.UI.Notifications.ToastNotification]::new($x))
' >/dev/null 2>&1 < /dev/null &
elif command -v notify-send >/dev/null 2>&1; then
  timeout 5 notify-send "$title" "$body" >/dev/null 2>&1 || true
fi
exit 0
