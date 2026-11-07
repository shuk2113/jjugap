package io.github.shuk2113.jjugap;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.graphics.PixelFormat;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.widget.Toast;

import com.google.android.gms.common.ConnectionResult;
import com.google.android.gms.common.GoogleApiAvailability;
import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;

import java.util.ArrayList;
import java.util.Locale;

/**
 * 지도를 켜 둔 동안 도는 위치 기록 서비스 (알림줄에 '선상 모드 켜짐' 표시).
 * - 앱 화면이 안 보일 때(홈 화면·다른 앱·화면 꺼짐) GPS를 모아 두면, 웹 앱이 받아 가서 5분 머문 곳을 자동 기록한다
 * - 앱 화면이 안 보일 때 홈 화면 위에 '포인트 저장' 단추를 띄운다 (끌어서 옮기기, 누르면 바로 저장 화면, 아래 ×에 놓으면 숨기기)
 * - 휴대폰 위치가 2분 넘게 꺼져 있으면 진동 알림 (누르면 위치 켜기)
 * - 배터리: 앱 화면을 볼 때는 웹 앱이 GPS를 받으니 여기는 쉰다 · 안 볼 때는 흘리는 중 10초, 달리는 중 30초마다 받고
 *   30초씩 모아서 한꺼번에 받는다 (그동안 휴대폰이 쉴 수 있게) · 통신망 위치는 GPS가 안 잡힐 때만 (구글 위치 서비스가 없는 폰)
 */
public class TrackService extends Service implements LocationListener {
    static final String CH = "track", CH2 = "saved", CH3 = "loc";
    static final int NID = 7, NID2 = 8, NID3 = 9, NID4 = 10;
    static final long OFF_WAIT = 120000;   // 위치가 이만큼 꺼져 있으면 알림
    static final long SLOW_MS = 10000, FAST_MS = 30000, BATCH_MS = 30000;   // 흘리는 중 · 달리는 중 간격, 모아 받기
    static final float FAST_ON = 3.0f, FAST_OFF = 2.0f;   // m/s: 약 6노트 넘게 두 번이면 달리는 중, 4노트 밑이면 흘리는 중
    static final ArrayList<double[]> fixes = new ArrayList<>();
    static volatile boolean appVisible = true;
    static volatile String status = "자동 기록 켜짐";
    static TrackService self;
    static long lastT, lastPush;
    static double lastLat, lastLon;

    LocationManager lm;
    WindowManager wm;
    Handler h;
    BubbleView bubble;
    TrashView trash;
    WindowManager.LayoutParams lp, tlp;
    boolean hidden;
    long offSince;      // 위치가 꺼진 걸 처음 본 때 (elapsedRealtime, 0 = 켜져 있음)
    boolean offNoted;   // '위치가 꺼져 기록이 멈췄어요' 알림을 띄웠다
    FusedLocationProviderClient flp;   // 구글 위치 서비스 (없으면 null → LocationManager)
    LocationCallback flpCb;
    int gpsMode = -1;   // 0 쉼(앱 화면) · 1 흘리는 중 · 2 달리는 중
    boolean fast, netOn;
    int fastCnt;
    long lastFixEl;     // 마지막으로 위치를 받은 때 (elapsedRealtime)
    double spLat, spLon; long spT;   // 속도를 셀 앞 위치
    final LocationListener netL = new LocationListener() {
        @Override public void onLocationChanged(Location l) { if (SystemClock.elapsedRealtime() - lastFixEl > 60000) { onFix(l); pushNow(); } }
        @Override public void onStatusChanged(String p, int st, Bundle b) { }
        @Override public void onProviderEnabled(String p) { }
        @Override public void onProviderDisabled(String p) { }
    };
    final Runnable watch = new Runnable() {
        @Override public void run() {
            checkLoc();
            // 구글 위치 서비스가 없는 폰: GPS가 1분 넘게 안 잡히면 통신망 위치라도
            if (flp == null && gpsMode > 0 && Loc.on(TrackService.this)) setNet(SystemClock.elapsedRealtime() - lastFixEl > 60000);
            if (self != null) h.postDelayed(this, 15000);
        }
    };

    static boolean running() { return self != null; }

    static void start(Context c) {
        Intent i = new Intent(c, TrackService.class);
        try { c.startForegroundService(i); } catch (Exception e) { Log.w("jjugap", "start", e); }
    }

    static void stop(Context c) { c.stopService(new Intent(c, TrackService.class)); }

    static void setAppVisible(boolean v) {
        appVisible = v;
        TrackService s = self;
        if (s != null) { s.h.post(s::syncBubble); s.h.post(s::checkLoc); s.h.post(s::applyMode); }
    }

    static void refresh() { TrackService s = self; if (s != null) s.h.post(s::syncBubble); }

    static void setStatus(String t) {
        status = t;
        TrackService s = self;
        if (s != null) s.h.post(s::post);
    }

    static void saved(String t) { TrackService s = self; if (s != null) s.h.post(() -> s.savedNote(t)); }

    /** 모아 둔 GPS를 [[위도, 경도, 오차m, 시각ms], ...] 글자로 넘기고 비운다 */
    static String takeFixes() {
        StringBuilder b = new StringBuilder("[");
        synchronized (fixes) {
            for (int i = 0; i < fixes.size(); i++) {
                double[] f = fixes.get(i);
                if (i > 0) b.append(',');
                b.append(String.format(Locale.US, "[%.6f,%.6f,%.0f,%d]", f[0], f[1], f[2], (long) f[3]));
            }
            fixes.clear();
        }
        return b.append(']').toString();
    }

    SharedPreferences prefs() { return getSharedPreferences("jjugap", MODE_PRIVATE); }

    @Override
    public void onCreate() {
        super.onCreate();
        self = this;
        h = new Handler(Looper.getMainLooper());
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CH, "선상 모드 · 자동 기록", NotificationManager.IMPORTANCE_LOW));
        NotificationChannel c2 = new NotificationChannel(CH2, "자동 기록 알림", NotificationManager.IMPORTANCE_DEFAULT);
        c2.setSound(null, null);
        c2.enableVibration(true);
        c2.setVibrationPattern(new long[]{0, 120, 90, 120});
        nm.createNotificationChannel(c2);
        NotificationChannel c3 = new NotificationChannel(CH3, "위치(GPS) 알림", NotificationManager.IMPORTANCE_HIGH);
        c3.setSound(null, null);
        c3.enableVibration(true);
        c3.setVibrationPattern(new long[]{0, 400, 200, 400, 200, 400});
        nm.createNotificationChannel(c3);
        goForeground();
        lm = getSystemService(LocationManager.class);
        try {
            if (GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(this) == ConnectionResult.SUCCESS) {
                flp = LocationServices.getFusedLocationProviderClient(this);
                flpCb = new LocationCallback() {
                    @Override public void onLocationResult(LocationResult r) {
                        int n = 0;
                        for (Location l : r.getLocations()) { onFix(l); n++; }
                        pushNow();
                        Log.i("jjugap", "gps batch " + n);
                    }
                };
            }
        } catch (Throwable t) { Log.w("jjugap", "fused", t); flp = null; }
        applyMode();
        wm = getSystemService(WindowManager.class);
        syncBubble();
        h.post(watch);
        Log.i("jjugap", "service started");
    }

    void goForeground() {
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(NID, build(), ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
            else startForeground(NID, build());
        } catch (Exception e) {
            Log.w("jjugap", "foreground", e);
            stopSelf();
        }
    }

    @Override
    public int onStartCommand(Intent i, int flags, int id) {
        if (i != null && "STOP".equals(i.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        goForeground();
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        h.removeCallbacks(watch);
        stopUpdates();
        removeBubble();
        hideTrash();
        self = null;
        NotificationManager nm = getSystemService(NotificationManager.class);
        try { nm.cancel(NID3); } catch (Exception ignored) { }
        Loc.clearHelped(this);   // 선상 모드가 끝나도 위치를 끄라고 묻지 않는다 (사용자 요청)
        Log.i("jjugap", "service stopped");
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent i) { return null; }

    // ---------- 위치 받기: 상황에 맞는 간격으로 (배터리)
    void applyMode() {
        if (self == null) return;
        int m = appVisible ? 0 : fast ? 2 : 1;
        if (m == gpsMode) return;
        int was = gpsMode;
        gpsMode = m;
        if (m == 0) {
            // 앱 화면을 본다: 웹 앱이 GPS를 받으니 여기는 쉰다. 모아 둔 위치는 먼저 내보내서 바로 보이게
            if (flp != null && was > 0) {
                try { flp.flushLocations().addOnCompleteListener(t -> { if (gpsMode == 0) stopUpdates(); pushNow(); }); }
                catch (Exception e) { stopUpdates(); }
            } else stopUpdates();
            Log.i("jjugap", "gps rest (app on screen)");
            return;
        }
        long iv = m == 2 ? FAST_MS : SLOW_MS;
        stopUpdates();
        try {
            if (flp != null) {
                LocationRequest r = new LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, iv)
                    .setMinUpdateIntervalMillis(Math.min(iv, 8000))
                    .setMaxUpdateDelayMillis(BATCH_MS)
                    .build();
                flp.requestLocationUpdates(r, flpCb, Looper.getMainLooper());
            } else {
                lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, iv, 0, this, Looper.getMainLooper());
            }
        } catch (SecurityException | IllegalArgumentException e) { Log.w("jjugap", "gps", e); }
        Log.i("jjugap", "gps " + (m == 2 ? "fast 30s" : "slow 10s") + (flp != null ? " fused batch 30s" : " lm"));
    }

    void stopUpdates() {
        if (flp != null && flpCb != null) { try { flp.removeLocationUpdates(flpCb); } catch (Exception ignored) { } }
        if (lm != null) { try { lm.removeUpdates(this); } catch (Exception ignored) { } }
        setNet(false);
    }

    /** 통신망 위치: GPS가 1분 넘게 안 잡힐 때만 (구글 위치 서비스가 없는 폰에서) */
    void setNet(boolean on) {
        if (on == netOn || lm == null) return;
        netOn = on;
        try {
            if (on && lm.getAllProviders().contains(LocationManager.NETWORK_PROVIDER))
                lm.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 30000, 0, netL, Looper.getMainLooper());
            else lm.removeUpdates(netL);
        } catch (SecurityException | IllegalArgumentException e) { Log.w("jjugap", "net", e); }
    }

    /** 속도로 '달리는 중/흘리는 중'을 판단해 간격을 바꾼다 */
    void judgeSpeed(Location l, long t) {
        float v = -1;
        if (l.hasSpeed()) v = l.getSpeed();
        else if (spT > 0 && t - spT >= 5000) {
            float[] d = new float[1];
            Location.distanceBetween(spLat, spLon, l.getLatitude(), l.getLongitude(), d);
            v = d[0] / ((t - spT) / 1000f);
        }
        spLat = l.getLatitude(); spLon = l.getLongitude(); spT = t;
        if (v < 0) return;
        boolean was = fast;
        if (v >= FAST_ON) { if (++fastCnt >= 2) fast = true; }
        else { fastCnt = 0; if (v < FAST_OFF) fast = false; }
        if (fast != was) h.post(this::applyMode);
    }

    void pushNow() {
        MainActivity a = MainActivity.live;
        if (a != null) { lastPush = System.currentTimeMillis(); a.pushFixes(); }
    }

    @Override
    public void onLocationChanged(Location l) {   // 구글 위치 서비스가 없는 폰 (LocationManager GPS)
        onFix(l);
        long now = System.currentTimeMillis();
        if (now - lastPush > 20000) pushNow();   // 20초마다 웹 앱에 넘겨 처리
    }

    // 모아 두기 (웹 앱이 받아 가서 5분 머문 곳을 자동 기록한다)
    void onFix(Location l) {
        if (l.hasAccuracy() && l.getAccuracy() > 100) return;
        long t = l.getTime() > 0 ? l.getTime() : System.currentTimeMillis();
        synchronized (fixes) {
            if (lastT > 0) {
                float[] d = new float[1];
                Location.distanceBetween(lastLat, lastLon, l.getLatitude(), l.getLongitude(), d);
                if (t <= lastT || (t - lastT < 8000 && d[0] < 25)) return;
            }
            fixes.add(new double[]{l.getLatitude(), l.getLongitude(), l.hasAccuracy() ? l.getAccuracy() : 30, t});
            if (fixes.size() > 20000) fixes.remove(0);
            lastT = t; lastLat = l.getLatitude(); lastLon = l.getLongitude();
        }
        if (LocationManager.GPS_PROVIDER.equals(l.getProvider()) || flp != null) { lastFixEl = SystemClock.elapsedRealtime(); setNet(false); }
        judgeSpeed(l, t);
    }

    @Override public void onStatusChanged(String p, int s, Bundle b) { }
    @Override public void onProviderEnabled(String p) { h.post(this::checkLoc); }
    @Override public void onProviderDisabled(String p) { h.post(this::checkLoc); }

    // ---------- 휴대폰 위치(GPS)가 꺼졌는지 15초마다
    void checkLoc() {
        if (self == null) return;
        boolean on = Loc.on(this);
        long now = SystemClock.elapsedRealtime();
        if (!on) {
            if (offSince == 0) { offSince = now; Loc.markOffSeen(this); post(); Log.i("jjugap", "loc off"); }
            if (!offNoted && !appVisible && now - offSince >= OFF_WAIT) { offNoted = true; offOnNote(); }
        } else if (offSince != 0) {
            offSince = 0;
            Loc.noteOn(this);
            post();
            Log.i("jjugap", "loc on");
            if (offNoted) { offNoted = false; try { getSystemService(NotificationManager.class).cancel(NID3); } catch (Exception ignored) { } }
            MainActivity a = MainActivity.live;
            if (a != null) a.runOnUiThread(a::locOnNow);
        }
    }

    PendingIntent locOnIntent(int rc) {
        Intent i = new Intent(this, MainActivity.class).putExtra("act", "map").putExtra("locon", true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this, rc, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    static boolean noteShown(Context c, int id) {
        try {
            for (android.service.notification.StatusBarNotification n : c.getSystemService(NotificationManager.class).getActiveNotifications())
                if (n.getId() == id) return true;
        } catch (Exception ignored) { }
        return false;
    }

    /** 선상 모드 중인데 위치가 꺼져 있다 (진동) */
    void offOnNote() {
        Notification n = new Notification.Builder(this, CH3)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(0xFFE5484D)
            .setGroup("jjugap-locon")   // 다른 알림과 묶이지 않게 (묶인 줄을 누르면 앱만 열려서)
            .setContentTitle("위치가 꺼져 기록이 멈췄어요")
            .setContentText("선상 모드 중인데 휴대폰 위치(GPS)가 꺼져 있어요 · 눌러서 켜기")
            .setStyle(new Notification.BigTextStyle().bigText("선상 모드 중인데 휴대폰 위치(GPS)가 꺼져 있어서 포인트 저장·자동 기록이 안 돼요. 눌러서 위치를 켜 주세요."))
            .setCategory(Notification.CATEGORY_STATUS)
            .setAutoCancel(true)
            .setContentIntent(locOnIntent(6))
            .addAction(new Notification.Action.Builder(null, "위치 켜기", locOnIntent(7)).build())
            .build();
        try { getSystemService(NotificationManager.class).notify(NID3, n); Log.i("jjugap", "loc off note"); } catch (Exception ignored) { }
    }

    /* (없앰) 선상 모드가 끝났을 때 '위치를 꺼 주세요' 알림
    void offNote(NotificationManager nm) {
        // 앱을 거쳐 설정 화면으로 (끄고 뒤로 오면 앱이 '위치를 껐어요'라고 알려 준다)
        Intent go = new Intent(this, MainActivity.class).putExtra("locoff", true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent set = PendingIntent.getActivity(this, 8, go, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(this, CH3)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(0xFF2F7DF6)
            .setGroup("jjugap-locoff")  // 다른 알림과 묶이지 않게 (묶인 줄을 누르면 앱만 열려서)
            .setContentTitle("선상 모드가 끝났어요 · 위치를 꺼 주세요")
            .setContentText("눌러서 맨 위 스위치('사용 중')를 끄고 돌아오세요")
            .setStyle(new Notification.BigTextStyle().bigText("오늘 켠 휴대폰 위치(GPS)가 아직 켜져 있어요. 눌러서 다음 화면 맨 위 스위치('사용 중')를 끄고 뒤로 돌아오세요."))
            .setAutoCancel(true)
            .setContentIntent(set)
            .addAction(new Notification.Action.Builder(null, "위치 끄기", set).build())
            .build();
        try { nm.notify(NID4, n); } catch (Exception ignored) { }
    }
    */

    // ---------- 알림줄
    PendingIntent openApp(String act, int rc) {
        Intent i = new Intent(this, MainActivity.class).putExtra("act", act)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this, rc, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    Notification build() {
        PendingIntent stop = PendingIntent.getService(this, 3, new Intent(this, TrackService.class).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CH)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(0xFF2F7DF6)
            .setContentTitle("쭈갑이 물때 · 선상 모드 켜짐")
            .setContentText(offSince != 0 ? "위치 꺼짐 · 기록 멈춤 · 눌러서 위치 켜기" : status)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setContentIntent(offSince != 0 ? locOnIntent(9) : openApp("map", 1))
            .addAction(new Notification.Action.Builder(null, "포인트 저장", openApp("save", 2)).build())
            .addAction(new Notification.Action.Builder(null, "선상 모드 끄기", stop).build())
            .build();
    }

    void post() {
        if (self == null) return;
        try { getSystemService(NotificationManager.class).notify(NID, build()); } catch (Exception ignored) { }
    }

    void savedNote(String t) {
        Log.i("jjugap", "saved note " + t);
        post();
        if (appVisible) return;   // 앱 화면에서는 웹 앱이 직접 알려 준다
        Notification n = new Notification.Builder(this, CH2)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(0xFF2F7DF6)
            .setContentTitle("포인트를 남겼어요")
            .setContentText(t + " · 눌러서 마릿수 넣기")
            .setAutoCancel(true)
            .setContentIntent(openApp("map", 4))
            .build();
        try { getSystemService(NotificationManager.class).notify(NID2, n); } catch (Exception ignored) { }
    }

    // ---------- 홈 화면 위 '포인트 저장' 단추
    void syncBubble() {
        if (appVisible) hidden = false;   // 앱에 들어왔다 나가면 숨긴 단추가 다시 생긴다
        boolean want = !appVisible && !hidden && prefs().getBoolean("bubble", true) && Settings.canDrawOverlays(this);
        if (want && bubble == null) addBubble();
        else if (!want && bubble != null) removeBubble();
    }

    int overlayType() { return WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY; }

    void addBubble() {
        DisplayMetrics dm = getResources().getDisplayMetrics();
        float dp = dm.density;
        bubble = new BubbleView(this);
        int w = Math.round(84 * dp), hh = Math.round(92 * dp);
        lp = new WindowManager.LayoutParams(w, hh, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN, PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        SharedPreferences sp = prefs();
        lp.x = clampX(sp.getInt("bx", dm.widthPixels - w - Math.round(8 * dp)));
        lp.y = clampY(sp.getInt("by", Math.round(dm.heightPixels * 0.62f)));
        bubble.setOnTouchListener(new Drag());
        try {
            wm.addView(bubble, lp);
            Log.i("jjugap", "bubble " + lp.x + "," + lp.y + " " + w + "x" + hh + " screen " + dm.widthPixels + "x" + dm.heightPixels);
        } catch (Exception e) {
            Log.w("jjugap", "bubble", e);
            bubble = null;
        }
    }

    void removeBubble() {
        if (bubble != null) { try { wm.removeView(bubble); } catch (Exception ignored) { } bubble = null; }
    }

    int clampX(int x) {
        DisplayMetrics dm = getResources().getDisplayMetrics();
        int w = lp != null ? lp.width : Math.round(84 * dm.density);
        return Math.max(0, Math.min(dm.widthPixels - w, x));
    }

    int clampY(int y) {
        DisplayMetrics dm = getResources().getDisplayMetrics();
        int hh = lp != null ? lp.height : Math.round(92 * dm.density);
        return Math.max(Math.round(24 * dm.density), Math.min(dm.heightPixels - hh, y));
    }

    void showTrash() {
        if (trash != null) return;
        DisplayMetrics dm = getResources().getDisplayMetrics();
        int s = Math.round(64 * dm.density);
        trash = new TrashView(this);
        tlp = new WindowManager.LayoutParams(s, s, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT);
        tlp.gravity = Gravity.TOP | Gravity.START;
        tlp.x = (dm.widthPixels - s) / 2;
        tlp.y = dm.heightPixels - s - Math.round(56 * dm.density);
        try { wm.addView(trash, tlp); } catch (Exception e) { trash = null; }
    }

    void hideTrash() {
        if (trash != null) { try { wm.removeView(trash); } catch (Exception ignored) { } trash = null; }
    }

    boolean overTrash() {
        if (trash == null || lp == null) return false;
        float bx = lp.x + lp.width / 2f, by = lp.y + lp.height * 0.38f;
        float tx = tlp.x + tlp.width / 2f, ty = tlp.y + tlp.height / 2f;
        return Math.hypot(bx - tx, by - ty) < 80 * getResources().getDisplayMetrics().density;
    }

    void openSave() {
        try {
            startActivity(new Intent(this, MainActivity.class).putExtra("act", "save")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP));
        } catch (Exception e) {
            Log.w("jjugap", "open", e);
            try { openApp("save", 5).send(); } catch (Exception ignored) { }
        }
    }

    class Drag implements View.OnTouchListener {
        float rx, ry;
        int x0, y0;
        boolean drag;
        final int slop = ViewConfiguration.get(TrackService.this).getScaledTouchSlop();

        @Override
        public boolean onTouch(View v, MotionEvent e) {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    rx = e.getRawX(); ry = e.getRawY(); x0 = lp.x; y0 = lp.y; drag = false;
                    bubble.setDown(true);
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx = e.getRawX() - rx, dy = e.getRawY() - ry;
                    if (!drag && Math.hypot(dx, dy) > slop) { drag = true; showTrash(); }
                    if (drag) {
                        lp.x = clampX(Math.round(x0 + dx)); lp.y = clampY(Math.round(y0 + dy));
                        try { wm.updateViewLayout(bubble, lp); } catch (Exception ignored) { }
                        if (trash != null) trash.setHot(overTrash());
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP: {
                    bubble.setDown(false);
                    if (!drag) { openSave(); return true; }
                    boolean kill = overTrash();
                    hideTrash();
                    if (kill) {
                        hidden = true; removeBubble();
                        Toast.makeText(TrackService.this, "단추를 숨겼어요. 앱에 들어갔다 나오면 다시 생겨요", Toast.LENGTH_SHORT).show();
                    } else {
                        prefs().edit().putInt("bx", lp.x).putInt("by", lp.y).apply();
                    }
                    return true;
                }
                case MotionEvent.ACTION_CANCEL:
                    bubble.setDown(false);
                    hideTrash();
                    return true;
            }
            return false;
        }
    }
}
