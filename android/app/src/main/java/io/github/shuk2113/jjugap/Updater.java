package io.github.shuk2113.jjugap;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.util.Log;
import android.widget.Toast;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 앱 안에서 업데이트: 새 앱 파일(app/jjugap.apk)을 받아 휴대폰의 '앱 설치' 화면에 넘긴다.
 * 같은 서명이라 지우지 않고 덮어 설치(업데이트)되고, 기록도 그대로 남는다.
 */
public class Updater {
    static final String APK = MainActivity.HOME + "app/jjugap.apk";
    static boolean waiting, busy;

    static long versionCode(Context c) {
        try {
            PackageInfo pi = c.getPackageManager().getPackageInfo(c.getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode;
        } catch (Exception e) { return 0; }
    }

    static void start(Activity a) {
        if (busy) return;
        if (!a.getPackageManager().canRequestPackageInstalls()) {
            waiting = true;
            new AlertDialog.Builder(a)
                .setTitle("앱 업데이트")
                .setMessage("처음 한 번만, 다음 화면에서 '쭈갑 물때'의 '이 출처 허용'을 켜고 돌아와 주세요. 그러면 바로 업데이트를 이어서 해요.")
                .setPositiveButton("켜러 가기", (d, w) -> {
                    try { a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + a.getPackageName()))); }
                    catch (Exception e) { waiting = false; }
                })
                .setNegativeButton("나중에", (d, w) -> waiting = false)
                .show();
            return;
        }
        waiting = false;
        busy = true;
        Toast.makeText(a, "새 버전을 받는 중이에요…", Toast.LENGTH_SHORT).show();
        final Context app = a.getApplicationContext();
        new Thread(() -> {
            String err = null;
            try { install(app); } catch (Exception e) { err = e.getMessage(); Log.w("jjugap", "update", e); }
            busy = false;
            final String msg = err;
            if (msg != null) a.runOnUiThread(() -> Toast.makeText(app, "업데이트 파일을 받지 못했어요. 인터넷 연결을 확인해 주세요", Toast.LENGTH_LONG).show());
        }).start();
    }

    static void resume(Activity a) {
        if (waiting && a.getPackageManager().canRequestPackageInstalls()) start(a);
    }

    static void install(Context c) throws Exception {
        HttpURLConnection con = (HttpURLConnection) new URL(APK + "?t=" + System.currentTimeMillis()).openConnection();
        con.setConnectTimeout(20000);
        con.setReadTimeout(60000);
        con.setUseCaches(false);
        if (con.getResponseCode() != 200) throw new Exception("http " + con.getResponseCode());
        PackageInstaller pi = c.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams p = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        p.setAppPackageName(c.getPackageName());
        if (Build.VERSION.SDK_INT >= 31) p.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        int id = pi.createSession(p);
        try (PackageInstaller.Session s = pi.openSession(id)) {
            try (InputStream in = con.getInputStream(); OutputStream out = s.openWrite("jjugap.apk", 0, -1)) {
                byte[] buf = new byte[65536];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                s.fsync(out);
            }
            Intent done = new Intent(c, InstallReceiver.class);
            int fl = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
            s.commit(PendingIntent.getBroadcast(c, id, done, fl).getIntentSender());
        }
    }
}
