package io.github.shuk2113.jjugap;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 쭈갑 물때 앱 화면: 웹 앱을 그대로 띄운다.
 * 웹 앱이 지도를 열면(setMapOpen) 위치 기록 서비스를 켜서, 홈 화면에 나가 있거나 화면이 꺼져도 GPS를 모으고
 * 홈 화면 위에 '포인트 저장' 단추를 띄운다.
 */
public class MainActivity extends Activity {
    static final String HOME = "https://shuk2113.github.io/jjugap/";
    static final int REQ_LOC = 11, REQ_NOTI = 12;

    WebView web;
    GeolocationPermissions.Callback geoCb;
    String geoOrigin;
    boolean mapOpen;

    SharedPreferences prefs() { return getSharedPreferences("jjugap", MODE_PRIVATE); }

    boolean hasLoc() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    static String actOf(Intent i) {
        String a = i == null ? null : i.getStringExtra("act");
        return "save".equals(a) || "map".equals(a) ? a : null;
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setGeolocationEnabled(true);
        s.setTextZoom(100);
        s.setAllowFileAccess(false);
        s.setUserAgentString(s.getUserAgentString() + " JjugapApp/1");
        // 홈 화면에 나가 있어도 웹 앱이 모아 둔 GPS를 계속 처리하게
        web.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);
        web.addJavascriptInterface(new Bridge(), "JjugapNative");
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
                if (hasLoc()) { cb.invoke(origin, true, false); return; }
                geoOrigin = origin; geoCb = cb;
                requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOC);
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("shuk2113.github.io".equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }
        });
        String act = actOf(getIntent());
        web.loadUrl(HOME + (act != null ? "?act=" + act : ""));
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        String act = actOf(i);
        if (act != null && web != null) {
            web.evaluateJavascript("window.jjugapAct ? jjugapAct('" + act + "') : location.replace('" + HOME + "?act=" + act + "')", null);
        }
    }

    @Override
    protected void onStart() {
        super.onStart();
        TrackService.setAppVisible(true);
    }

    @Override
    protected void onStop() {
        super.onStop();
        TrackService.setAppVisible(false);
    }

    @Override
    public void onBackPressed() {
        // 지도·판은 웹 앱의 뒤로 가기로 닫고, 맨 처음 화면이면 앱을 끄지 않고 뒤로 보낸다 (지도 기록이 이어지게)
        if (web != null && web.canGoBack()) web.goBack();
        else moveTaskToBack(true);
    }

    @Override
    protected void onDestroy() {
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        super.onRequestPermissionsResult(req, perms, res);
        if (req == REQ_LOC) {
            boolean ok = hasLoc();
            if (geoCb != null) { geoCb.invoke(geoOrigin, ok, false); geoCb = null; }
            if (ok && mapOpen) setMapOpen(true);
        } else if (req == REQ_NOTI) {
            if (mapOpen && hasLoc()) startTracking();
        }
    }

    // 웹 앱이 지도를 열고 닫을 때
    void setMapOpen(boolean on) {
        mapOpen = on;
        if (!on) { TrackService.stop(this); return; }
        if (!hasLoc()) return;   // 위치 권한을 받은 뒤 다시 (onRequestPermissionsResult)
        if (Build.VERSION.SDK_INT >= 33
            && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            && !prefs().getBoolean("askedNoti", false)) {
            prefs().edit().putBoolean("askedNoti", true).apply();
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTI);
            return;
        }
        startTracking();
    }

    void startTracking() {
        TrackService.start(this);
        SharedPreferences sp = prefs();
        if (!sp.getBoolean("bubble", true) || Settings.canDrawOverlays(this) || sp.getBoolean("askedOverlay", false)) return;
        sp.edit().putBoolean("askedOverlay", true).apply();
        new AlertDialog.Builder(this)
            .setTitle("홈 화면에 '포인트 저장' 단추")
            .setMessage("지도를 켠 채 홈 화면으로 나가도 '포인트 저장' 단추가 떠 있게 하려면, 다음 화면에서 '쭈갑 물때'를 찾아 '다른 앱 위에 표시'를 켜 주세요.")
            .setPositiveButton("켜러 가기", (d, w) -> openOverlaySettings())
            .setNegativeButton("나중에", null)
            .show();
    }

    void openOverlaySettings() {
        try {
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + getPackageName())));
        } catch (Exception e) {
            try { startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)); } catch (Exception ignored) { }
        }
    }

    /** 웹 앱에서 부르는 것들 (window.JjugapNative) */
    class Bridge {
        @JavascriptInterface public String version() { return "1"; }
        @JavascriptInterface public void setMapOpen(boolean on) { runOnUiThread(() -> MainActivity.this.setMapOpen(on)); }
        @JavascriptInterface public boolean isTracking() { return TrackService.running(); }
        @JavascriptInterface public String takeFixes() { return TrackService.takeFixes(); }
        @JavascriptInterface public void setStatus(String s) { TrackService.setStatus(s); }
        @JavascriptInterface public void saved(String s) { TrackService.saved(s); }
        @JavascriptInterface public boolean bubbleOn() { return prefs().getBoolean("bubble", true) && Settings.canDrawOverlays(MainActivity.this); }
        @JavascriptInterface public void setBubble(boolean on) {
            runOnUiThread(() -> {
                prefs().edit().putBoolean("bubble", on).apply();
                if (on && !Settings.canDrawOverlays(MainActivity.this)) openOverlaySettings();
                TrackService.refresh();
            });
        }
    }
}
