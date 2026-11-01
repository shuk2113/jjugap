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
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Locale;

/**
 * 지도를 켜 둔 동안 도는 위치 기록 서비스 (알림줄에 '지도 켜짐' 표시).
 * - 앱 화면이 안 보일 때(홈 화면·다른 앱·화면 꺼짐) GPS를 모아 두면, 웹 앱이 받아 가서 5분 머문 곳을 자동 기록한다
 * - 앱 화면이 안 보일 때 홈 화면 위에 '포인트 저장' 단추를 띄운다 (끌어서 옮기기, 누르면 바로 저장 화면, 아래 ×에 놓으면 숨기기)
 */
public class TrackService extends Service implements LocationListener {
    static final String CH = "track", CH2 = "saved";
    static final int NID = 7, NID2 = 8;
    static final ArrayList<double[]> fixes = new ArrayList<>();
    static volatile boolean appVisible = true;
    static volatile String status = "자동 기록 켜짐";
    static TrackService self;
    static long lastT;
    static double lastLat, lastLon;

    LocationManager lm;
    WindowManager wm;
    Handler h;
    BubbleView bubble;
    TrashView trash;
    WindowManager.LayoutParams lp, tlp;
    boolean hidden;

    static boolean running() { return self != null; }

    static void start(Context c) {
        Intent i = new Intent(c, TrackService.class);
        try { c.startForegroundService(i); } catch (Exception e) { Log.w("jjugap", "start", e); }
    }

    static void stop(Context c) { c.stopService(new Intent(c, TrackService.class)); }

    static void setAppVisible(boolean v) {
        appVisible = v;
        TrackService s = self;
        if (s != null) s.h.post(s::syncBubble);
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
        nm.createNotificationChannel(new NotificationChannel(CH, "지도 켜짐 · 자동 기록", NotificationManager.IMPORTANCE_LOW));
        NotificationChannel c2 = new NotificationChannel(CH2, "자동 기록 알림", NotificationManager.IMPORTANCE_DEFAULT);
        c2.setSound(null, null);
        c2.enableVibration(true);
        c2.setVibrationPattern(new long[]{0, 120, 90, 120});
        nm.createNotificationChannel(c2);
        goForeground();
        lm = getSystemService(LocationManager.class);
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 4000, 0, this, Looper.getMainLooper());
        } catch (SecurityException | IllegalArgumentException e) { Log.w("jjugap", "gps", e); }
        try {
            if (lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER))
                lm.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 15000, 0, this, Looper.getMainLooper());
        } catch (SecurityException | IllegalArgumentException e) { Log.w("jjugap", "net", e); }
        wm = getSystemService(WindowManager.class);
        syncBubble();
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
        if (lm != null) { try { lm.removeUpdates(this); } catch (Exception ignored) { } }
        removeBubble();
        hideTrash();
        self = null;
        Log.i("jjugap", "service stopped");
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent i) { return null; }

    // ---------- 위치: 앱 화면이 안 보일 때만 모아 둔다 (보일 때는 웹 앱이 직접 받는다)
    @Override
    public void onLocationChanged(Location l) {
        if (appVisible) return;
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
    }

    @Override public void onStatusChanged(String p, int s, Bundle b) { }
    @Override public void onProviderEnabled(String p) { }
    @Override public void onProviderDisabled(String p) { }

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
            .setContentTitle("쭈갑 물때 · 지도 켜짐")
            .setContentText(status)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setContentIntent(openApp("map", 1))
            .addAction(new Notification.Action.Builder(null, "포인트 저장", openApp("save", 2)).build())
            .addAction(new Notification.Action.Builder(null, "기록 끄기", stop).build())
            .build();
    }

    void post() {
        if (self == null) return;
        try { getSystemService(NotificationManager.class).notify(NID, build()); } catch (Exception ignored) { }
    }

    void savedNote(String t) {
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
