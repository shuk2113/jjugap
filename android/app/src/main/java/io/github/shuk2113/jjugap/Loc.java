package io.github.shuk2113.jjugap;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.location.LocationManager;
import android.os.Build;
import android.provider.Settings;

/**
 * 휴대폰 위치(GPS) 켜짐 확인과 '앱이 위치를 켜게 도와준 날' 기억.
 * - 선상 모드 중 위치가 꺼져 있는 걸 봤다가(markOffSeen) 다시 켜지면(noteOn) → 앱이 켜게 도와줬다고 적어 둔다
 * - 그날(24시간 안) 선상 모드가 끝나면 위치를 끄라고 한 번 알려 준다 (앱이 위치를 직접 끌 수는 없어서 설정 화면으로)
 */
final class Loc {
    static final long KEEP = 24L * 3600 * 1000;

    static SharedPreferences sp(Context c) { return c.getSharedPreferences("jjugap", Context.MODE_PRIVATE); }

    static boolean on(Context c) {
        LocationManager lm = c.getSystemService(LocationManager.class);
        if (lm == null) return true;
        try {
            if (Build.VERSION.SDK_INT >= 28) return lm.isLocationEnabled();
            return lm.isProviderEnabled(LocationManager.GPS_PROVIDER) || lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER);
        } catch (Exception e) { return true; }
    }

    /** 선상 모드 중에 위치가 꺼져 있는 걸 봤다 */
    static void markOffSeen(Context c) { sp(c).edit().putLong("locOffSeen", System.currentTimeMillis()).apply(); }

    /** 꺼져 있던 위치가 켜졌다 (선상 모드 중) → 앱이 켜게 도와준 날로 */
    static void noteOn(Context c) {
        long t = sp(c).getLong("locOffSeen", 0);
        if (t > 0 && System.currentTimeMillis() - t < KEEP) markHelped(c);
    }

    static void markHelped(Context c) {
        sp(c).edit().putLong("locHelped", System.currentTimeMillis()).remove("locOffSeen").apply();
    }

    static boolean helped(Context c) {
        long t = sp(c).getLong("locHelped", 0);
        return t > 0 && System.currentTimeMillis() - t < KEEP;
    }

    /** 끄기 안내를 했으면 지운다 (같은 날 다시 나가도 또 묻지 않게) · 선상 모드가 끝나면 '꺼져 있던 걸 봤다'도 지운다 */
    static void clearHelped(Context c) { sp(c).edit().remove("locHelped").remove("locOffSeen").apply(); }
    static void clearOffSeen(Context c) { sp(c).edit().remove("locOffSeen").apply(); }

    static Intent settings() {
        return new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }

    static boolean openSettings(Context c) {
        try { c.startActivity(settings()); return true; }
        catch (Exception e) {
            try { c.startActivity(new Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return true; }
            catch (Exception ignored) { return false; }
        }
    }
}
