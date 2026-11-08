#!/bin/bash
# 가상 휴대폰 시험: 설치 → 지도 열기 → 홈 화면으로 → 같은 자리 6분 → 알림·떠 있는 단추 확인 → 단추 누르기
set -x
OUT=out; P=io.github.shuk2113.jjugap
shot() { adb exec-out screencap -p > "$OUT/$1.png"; }
adb install -r -g "$OUT/jjugap.apk" 2>&1 | tail -2
adb shell appops set $P SYSTEM_ALERT_WINDOW allow
adb shell cmd location set-location-enabled true 2>/dev/null
adb emu geo fix 126.3300 37.1700
adb logcat -c
adb shell am start -n $P/.MainActivity --es act map
sleep 35
adb emu geo fix 126.3301 37.1701
sleep 8
shot 1-map
adb shell input keyevent KEYCODE_HOME
sleep 8
shot 2-home
for i in $(seq 1 46); do adb emu geo fix 126.330$((RANDOM%9)) 37.170$((RANDOM%9)); sleep 9; done   # 6분 넘게 (30초씩 모아 받아도 넉넉히)
shot 3-home-later
adb shell cmd statusbar expand-notifications; sleep 4; shot 4-noti; adb shell cmd statusbar collapse; sleep 3
B=$(adb logcat -d -s jjugap:I | grep "bubble " | tail -1); echo "$B" > "$OUT/bubble.txt"
X=$(echo "$B" | sed -E 's/.*bubble ([0-9]+),([0-9]+) ([0-9]+)x([0-9]+).*/\1/'); Y=$(echo "$B" | sed -E 's/.*bubble ([0-9]+),([0-9]+) ([0-9]+)x([0-9]+).*/\2/')
W=$(echo "$B" | sed -E 's/.*bubble ([0-9]+),([0-9]+) ([0-9]+)x([0-9]+).*/\3/'); H=$(echo "$B" | sed -E 's/.*bubble ([0-9]+),([0-9]+) ([0-9]+)x([0-9]+).*/\4/')
if [ -n "$X" ] && [ "$X" -eq "$X" ] 2>/dev/null; then adb shell input tap $((X + W / 2)) $((Y + H * 38 / 100)); fi
sleep 10
shot 5-after-tap
# 화면 잠금: 앱(지도)을 켠 채 화면을 끄고 다른 자리(B)로 옮겨 6분 머묾 → 알림이 오는지
adb shell input keyevent KEYCODE_BACK; sleep 2; adb shell am start -n $P/.MainActivity --es act map; sleep 8
for i in $(seq 1 6); do adb emu geo fix 126.3$((3 + i))00 37.1600; sleep 6; done
adb shell input keyevent KEYCODE_SLEEP
sleep 3
for i in $(seq 1 48); do adb emu geo fix 126.390$((RANDOM%9)) 37.160$((RANDOM%9)); sleep 9; done
adb shell input keyevent KEYCODE_WAKEUP; sleep 2; adb shell wm dismiss-keyguard; sleep 3
adb shell cmd statusbar expand-notifications; sleep 4; shot 7-lock-noti; adb shell cmd statusbar collapse; sleep 2
adb shell am start -n $P/.MainActivity --es act map; sleep 6; shot 8-after-lock
adb logcat -d -s jjugap:I | grep -E "gps |service |saved|stay" > "$OUT/gps.txt"   # GPS 간격 바뀜·모아 받기 기록
# ---------- 휴대폰 위치(GPS) 꺼짐
# 화면의 글자(알림·창·웹 단추 이름)를 찾아 누른다: tapText <정규식> <이름>
tapText() {
  adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
  adb pull /sdcard/ui.xml "$OUT/ui-$2.xml" >/dev/null 2>&1
  XY=$(python3 - "$OUT/ui-$2.xml" "$1" <<'PY'
import re, sys
s = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
for m in re.finditer(r'<node [^>]*>', s):
    n = m.group(0)
    t = re.search(r' text="([^"]*)"', n); d = re.search(r'content-desc="([^"]*)"', n); r = re.search(r'resource-id="([^"]*)"', n)
    txt = (t.group(1) if t else '') + '|' + (d.group(1) if d else '') + '|' + (r.group(1) if r else '')
    if re.search(sys.argv[2], txt):
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
        if b:
            x1, y1, x2, y2 = map(int, b.groups()); print((x1 + x2) // 2, (y1 + y2) // 2); break
PY
)
  echo "tapText $1 -> $XY" | tee -a "$OUT/loc.txt"
  [ -n "$XY" ] && adb shell input tap $XY
  [ -n "$XY" ]
}
# 알림줄에서 <정규식> 글자가 있는 알림의 '펼치기'를 누른다 (묶인 알림 → 알림 하나 → 단추가 보이게)
tapExpand() {
  adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
  adb pull /sdcard/ui.xml "$OUT/ui-$2.xml" >/dev/null 2>&1
  XY=$(python3 - "$OUT/ui-$2.xml" "$1" <<'PY'
import re, sys
s = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
nodes = []
for m in re.finditer(r'<node [^>]*>', s):
    n = m.group(0); b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
    if not b: continue
    t = re.search(r' text="([^"]*)"', n); d = re.search(r'content-desc="([^"]*)"', n)
    nodes.append(((t.group(1) if t else ''), (d.group(1) if d else ''), tuple(map(int, b.groups()))))
ty = next(((bb[1] + bb[3]) // 2 for t, d, bb in nodes if re.search(sys.argv[2], t)), None)
ex = [bb for t, d, bb in nodes if d == 'Expand']
pick = next((bb for bb in ex if ty is not None and bb[1] <= ty <= bb[3]), ex[0] if ex else None)
if pick: print((pick[0] + pick[2]) // 2, (pick[1] + pick[3]) // 2)
PY
)
  echo "tapExpand $1 -> $XY" | tee -a "$OUT/loc.txt"
  [ -n "$XY" ] && adb shell input tap $XY
}
locState() { echo "$1: location=$(adb shell settings get secure location_mode) $(adb shell cmd location is-location-enabled 2>/dev/null)" | tee -a "$OUT/loc.txt"; }
# (1) 선상 모드 중 위치를 끄면 → 지도에 빨간 띠 · 알약 '위치 꺼짐 · 기록 멈춤'
adb shell am start -n $P/.MainActivity --es act map; sleep 8
adb shell cmd location set-location-enabled false; sleep 10
locState off; shot 9-locoff-map
# (4) 홈 화면에서 2분 넘게 꺼져 있으면 → 진동 알림 '위치가 꺼져 기록이 멈췄어요'
adb shell input keyevent KEYCODE_HOME
sleep 150
adb shell cmd statusbar expand-notifications; sleep 4; shot 10-locoff-noti
# 알림을 누르면 → 앱이 열리고 '위치 켜기' 창 (구글 위치 서비스) → 확인
tapText "위치가 꺼져 기록이 멈췄어요" n10 || { adb shell cmd statusbar collapse; adb shell am start -n $P/.MainActivity --es act map --ez locon true; }
sleep 8; shot 11-locon-ask
tapText "^(OK|Ok|확인|Turn on|TURN ON|사용)\|" a11 || tapText "(OK|확인|Turn on|사용)" a11b || adb shell cmd location set-location-enabled true
sleep 8; locState after-ask; shot 12-locon-after
adb shell cmd location set-location-enabled true
for i in $(seq 1 3); do adb emu geo fix 126.3302 37.1702; sleep 4; done
# 끝날 때 (홈 화면에서 알림줄 '선상 모드 끄기') → 위치를 끄라는 알림이 뜨지 않아야 한다 (없앤 기능)
adb shell input keyevent KEYCODE_HOME; sleep 4
adb shell cmd statusbar expand-notifications; sleep 4
for k in 1 2 3 4; do tapText "^선상 모드 끄기\|" n13-$k && break; tapExpand "선상 모드 켜짐" e13-$k; sleep 2; done
sleep 5; adb shell cmd statusbar collapse; sleep 2; adb shell cmd statusbar expand-notifications; sleep 4; shot 13-end-noti
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml "$OUT/ui-end13.xml" >/dev/null 2>&1
grep -q "위치를 꺼 주세요" "$OUT/ui-end13.xml" && echo "END NOTE SHOWN (안 떠야 함)" | tee -a "$OUT/loc.txt" || echo "end note none (ok)" | tee -a "$OUT/loc.txt"
adb shell cmd statusbar collapse; sleep 2
# (1) 위치를 끈 채 선상 모드를 켜면 → 바로 '위치 켜기' 창 → 확인 → 앱 화면에서 꺼도 '위치를 끌까요?' 창이 뜨지 않아야 한다
adb shell cmd location set-location-enabled false; sleep 4
adb shell am start -n $P/.MainActivity --es act map; sleep 12
shot 14-start-ask
tapText "^(OK|Ok|확인|Turn on|TURN ON|사용)\|" a14 || tapText "(OK|확인|Turn on|사용)" a14b || adb shell cmd location set-location-enabled true
sleep 8; locState after-ask2
for i in $(seq 1 3); do adb emu geo fix 126.3303 37.1703; sleep 4; done
shot 15-map-on
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; sleep 2   # 웹 화면 글자를 읽을 수 있게 한 번 먼저
XY=""; for k in 1 2 3; do tapText "\|mv-off$" w16-$k && break; sleep 3; done
[ -z "$XY" ] && { XY="999 200"; echo "mv-off 글자를 못 읽어 자리로 누름 $XY" | tee -a "$OUT/loc.txt"; adb shell input tap $XY; }   # 지도 윗줄 오른쪽 끝 (pixel 6)
sleep 1; adb shell input tap $XY   # 한 번 더 눌러 확인 (끄기 단추는 실수로 꺼지지 않게 두 번)
sleep 5; shot 16-end-no-dialog
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml "$OUT/ui-end16.xml" >/dev/null 2>&1
grep -q "위치를 끌까요" "$OUT/ui-end16.xml" && echo "END DIALOG SHOWN (안 떠야 함)" | tee -a "$OUT/loc.txt" || echo "end dialog none (ok)" | tee -a "$OUT/loc.txt"
adb shell cmd location set-location-enabled false; sleep 2
adb logcat -d -s jjugap:I | grep -E "loc |locon" >> "$OUT/loc.txt"
# (17) 선상 모드를 끈 뒤 앱이 닫혔다가 '최근 앱'에서 다시 열면: 예전에 알림으로 열었던 요청(지도 열기·위치 켜기)으로 선상 모드가 저절로 켜지면 안 된다
adb shell am force-stop $P; sleep 3; adb logcat -c
adb shell am start -n $P/.MainActivity --es act map --ez locon true -f 0x00100000; sleep 14   # 0x00100000 = 최근 앱 목록에서 열기
shot 17-recents
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml "$OUT/ui-recents17.xml" >/dev/null 2>&1
if adb shell dumpsys activity services $P | grep -q TrackService; then echo "RECENTS STARTED BOARD (켜지면 안 됨)" | tee -a "$OUT/loc.txt"; else echo "recents reopen: board stays off (ok)" | tee -a "$OUT/loc.txt"; fi
grep -qE "Turn on|TURN ON|사용|위치 정확도|location accuracy" "$OUT/ui-recents17.xml" && echo "RECENTS LOC DIALOG (안 떠야 함)" | tee -a "$OUT/loc.txt" || echo "recents reopen: no location dialog (ok)" | tee -a "$OUT/loc.txt"
adb logcat -d -s jjugap:I | grep -E "history|service started|locon" >> "$OUT/loc.txt"
# (18) 조과 카드: 마지막 출조 카드 열기 → 보내기(고르는 창) → 저장(사진첩) → 사진 넣기(사진 고르기 창)
adb logcat -c
adb shell am start -n $P/.MainActivity --es act card; sleep 12; shot 18-card
adb shell input tap 231 1749; sleep 6; shot 19-share   # '보내기' (웹 화면 412×842 기준 자리)
F=$(adb shell dumpsys activity activities | grep -E "topResumedActivity|mResumedActivity" | head -1); echo "after share: $F" | tee -a "$OUT/card.txt"
echo "$F" | grep -qiE "chooser|intentresolver|resolver" && echo "card share sheet (ok)" | tee -a "$OUT/card.txt" || echo "CARD SHARE SHEET NOT SEEN" | tee -a "$OUT/card.txt"
adb shell input keyevent KEYCODE_BACK; sleep 3
adb shell input tap 591 1749; sleep 5; shot 20-saved   # '저장'
G=$(adb shell content query --uri content://media/external/images/media --projection _display_name:relative_path 2>/dev/null | grep -i jjugap)
[ -n "$G" ] && echo "card in gallery (ok): $G" | tee -a "$OUT/card.txt" || echo "CARD NOT IN GALLERY" | tee -a "$OUT/card.txt"
adb shell input tap 283 1608; sleep 6; shot 21-photo-pick   # '사진 넣기'
F=$(adb shell dumpsys activity activities | grep -E "topResumedActivity|mResumedActivity" | head -1); echo "after photo: $F" | tee -a "$OUT/card.txt"
echo "$F" | grep -qiE "documentsui|photopicker|chooser|resolver|providers.media" && echo "photo picker (ok)" | tee -a "$OUT/card.txt" || echo "PHOTO PICKER NOT SEEN" | tee -a "$OUT/card.txt"
adb shell input keyevent KEYCODE_BACK; sleep 2; adb shell input keyevent KEYCODE_BACK; sleep 2
F=$(adb shell dumpsys activity activities | grep -E "topResumedActivity|mResumedActivity" | head -1); echo "after back: $F" | tee -a "$OUT/card.txt"
adb logcat -d -s jjugap:I jjugap:W | grep -E "card|photo" | tee -a "$OUT/card.txt"
adb logcat -d | grep -E "FATAL|AndroidRuntime: java" | head -5 | tee -a "$OUT/card.txt"
# 앱 안에서 업데이트: 같은 파일을 받아 설치 화면을 여는지
adb shell appops set $P REQUEST_INSTALL_PACKAGES allow
adb shell am start -n $P/.MainActivity --es act update
sleep 20
shot 6-update
adb shell dumpsys activity services $P > "$OUT/services.txt" 2>&1
adb logcat -d > "$OUT/logcat-all.txt"
grep -E "jjugap|AndroidRuntime|FATAL|chromium|Console" "$OUT/logcat-all.txt" | tail -500 > "$OUT/log.txt"
echo done > "$OUT/emu-done.txt"
