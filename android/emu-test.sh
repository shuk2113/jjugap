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
for i in $(seq 1 40); do adb emu geo fix 126.330$((RANDOM%9)) 37.170$((RANDOM%9)); sleep 9; done
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
for i in $(seq 1 42); do adb emu geo fix 126.390$((RANDOM%9)) 37.160$((RANDOM%9)); sleep 9; done
adb shell input keyevent KEYCODE_WAKEUP; sleep 2; adb shell wm dismiss-keyguard; sleep 3
adb shell cmd statusbar expand-notifications; sleep 4; shot 7-lock-noti; adb shell cmd statusbar collapse; sleep 2
adb shell am start -n $P/.MainActivity --es act map; sleep 6; shot 8-after-lock
# 앱 안에서 업데이트: 같은 파일을 받아 설치 화면을 여는지
adb shell appops set $P REQUEST_INSTALL_PACKAGES allow
adb shell am start -n $P/.MainActivity --es act update
sleep 20
shot 6-update
adb shell dumpsys activity services $P > "$OUT/services.txt" 2>&1
adb logcat -d > "$OUT/logcat-all.txt"
grep -E "jjugap|AndroidRuntime|FATAL|chromium|Console" "$OUT/logcat-all.txt" | tail -500 > "$OUT/log.txt"
echo done > "$OUT/emu-done.txt"
