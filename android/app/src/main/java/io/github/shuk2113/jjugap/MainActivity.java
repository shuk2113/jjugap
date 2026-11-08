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
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;
import android.webkit.GeolocationPermissions;
import android.webkit.ValueCallback;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import com.google.android.gms.common.api.ResolvableApiException;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.LocationSettingsRequest;
import com.google.android.gms.location.Priority;

/**
 * 쭈갑이 물때 앱 화면: 웹 앱을 그대로 띄운다.
 * 웹 앱이 지도를 열면(setMapOpen) 위치 기록 서비스를 켜서, 홈 화면에 나가 있거나 화면이 꺼져도 GPS를 모으고
 * 홈 화면 위에 '포인트 저장' 단추를 띄운다.
 * 선상 모드를 켤 때 휴대폰 위치가 꺼져 있으면 한 번에 켜는 창을 띄운다.
 */
public class MainActivity extends Activity {
    static final String HOME = "https://shuk2113.github.io/jjugap/";
    static final int REQ_LOC = 11, REQ_NOTI = 12, REQ_LOCON = 13, REQ_FILE = 14;
    ValueCallback<Uri[]> fileCb;     // 조과 카드에 넣을 사진 고르기

    WebView web;
    static MainActivity live;   // 위치 기록 서비스가 모아 둔 GPS를 바로 넘겨줄 화면
    GeolocationPermissions.Callback geoCb;
    String geoOrigin;
    boolean mapOpen;
    boolean askingLoc, sentLocOn;   // 위치 켜기 창을 띄운 중 · 위치 켜러 설정 화면에 보냄
    long locNoAt;                    // '위치 켜기'를 마다한 때 (10분 동안은 앱에 돌아올 때마다 다시 묻지 않는다)

    SharedPreferences prefs() { return getSharedPreferences("jjugap", MODE_PRIVATE); }

    boolean hasLoc() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    static String actOf(Intent i) {
        String a = i == null ? null : i.getStringExtra("act");
        return "save".equals(a) || "map".equals(a) || "card".equals(a) ? a : null;
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        setContentView(web);
        live = this;
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
            // 조과 카드: '사진 넣기' → 휴대폰 사진 고르기
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCb != null) fileCb.onReceiveValue(null);
                fileCb = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*");
                try { startActivityForResult(Intent.createChooser(i, "사진 고르기"), REQ_FILE); Log.i("jjugap", "photo pick"); return true; }
                catch (Exception e) { fileCb = null; Log.w("jjugap", "photo pick", e); return false; }
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("shuk2113.github.io".equals(u.getHost())) return false;
                openOutside(u.toString());
                return true;
            }
        });
        // 최근 앱 목록에서 다시 열었거나 화면을 다시 만든 경우: 예전에 알림·바로가기로 열 때의 요청(선상 모드 열기 등)을 또 하지 않는다
        // (사용자가 누르지 않았는데 선상 모드가 저절로 켜지지 않게)
        boolean stale = b != null || (getIntent().getFlags() & Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0;
        String act = stale ? null : actOf(getIntent());
        web.loadUrl(HOME + (act != null ? "?act=" + act : ""));
        if (!stale && "update".equals(getIntent().getStringExtra("act"))) Updater.start(this);
        if (!stale && getIntent().getBooleanExtra("locon", false)) web.postDelayed(this::askLocationOn, 1200);
        if (stale) Log.i("jjugap", "launch from history: act ignored");
        getIntent().removeExtra("locon");   // 화면을 다시 만들 때 또 열리지 않게
        try { getSystemService(android.app.NotificationManager.class).cancel(TrackService.NID4); } catch (Exception ignored) { }   // 예전 판의 '위치를 꺼 주세요' 알림이 남아 있으면 지운다
    }

    /** 다른 앱으로 열기: 길안내(카카오맵·네이버지도·티맵)·로드뷰·전화·출처 글.
     *  intent: 주소는 풀어서 열고, 그 앱이 없으면 플레이 스토어의 그 앱 쪽으로 (아무 일도 안 일어나는 일이 없게) */
    void openOutside(String s) {
        try {
            if (s.startsWith("intent:")) {
                Intent it = Intent.parseUri(s, Intent.URI_INTENT_SCHEME);
                it.addCategory(Intent.CATEGORY_BROWSABLE); it.setComponent(null); it.setSelector(null);
                try { startActivity(it); return; } catch (android.content.ActivityNotFoundException e) {
                    String fb = it.getStringExtra("browser_fallback_url");
                    if (fb != null && fb.startsWith("https://")) { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(fb))); return; }
                    if (it.getPackage() != null) { market(it.getPackage()); return; }
                }
                Toast.makeText(this, "열 수 있는 앱이 없어요", Toast.LENGTH_SHORT).show();
                return;
            }
            Uri u = Uri.parse(s);
            try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (android.content.ActivityNotFoundException e) {
                String sc = u.getScheme(), pk = "nmap".equals(sc) ? "com.nhn.android.nmap" : "tmap".equals(sc) ? "com.skt.tmap.ku" : "kakaomap".equals(sc) ? "net.daum.android.map" : null;
                if (pk != null) market(pk); else Toast.makeText(this, "열 수 있는 앱이 없어요", Toast.LENGTH_SHORT).show();
            }
        } catch (Exception e) { Log.w("jjugap", "open outside", e); }
    }

    void market(String pk) {
        Log.i("jjugap", "market " + pk);
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + pk))); }
        catch (Exception e) { try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=" + pk))); } catch (Exception ignored) { } }
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        if ("update".equals(i.getStringExtra("act"))) { Updater.start(this); return; }
        if (i.getBooleanExtra("locon", false) && web != null) web.postDelayed(this::askLocationOn, 600);
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
    protected void onResume() {
        super.onResume();
        Updater.resume(this);   // '이 출처 허용'을 켜고 돌아오면 이어서 업데이트
        if (sentLocOn) {   // 위치를 켜러 설정 화면에 갔다 돌아옴
            sentLocOn = false;
            if (Loc.on(this)) { Loc.markHelped(this); locOnNow(); }
        }
        if (web != null) web.evaluateJavascript("window.jjugapLocCheck && jjugapLocCheck()", null);
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

    // 화면이 잠겨 있어도 모아 둔 GPS를 웹 앱이 바로 처리하게 (웹 앱의 시계는 잠금 중에 느려질 수 있어서)
    void pushFixes() {
        if (web != null) web.evaluateJavascript("window.jjugapNatFixes && jjugapNatFixes()", null);
    }

    boolean batteryOk() {
        PowerManager pm = getSystemService(PowerManager.class);
        return pm == null || pm.isIgnoringBatteryOptimizations(getPackageName());
    }

    void askBattery() {
        try { startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + getPackageName()))); }
        catch (Exception e) {
            try { startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)); } catch (Exception ignored) { }
        }
    }

    @Override
    protected void onDestroy() {
        if (live == this) live = null;
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_FILE) {
            Uri u = res == RESULT_OK && data != null ? data.getData() : null;
            if (fileCb != null) fileCb.onReceiveValue(u != null ? new Uri[]{u} : null);
            fileCb = null; return;
        }
        if (req == REQ_LOCON) {
            askingLoc = false;
            if (res == RESULT_OK || Loc.on(this)) { Loc.markHelped(this); locOnNow(); afterLocOn(); Log.i("jjugap", "loc on by app"); }
            else { locNoAt = SystemClock.elapsedRealtime(); Log.i("jjugap", "loc on declined"); }
        }
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
        if (!Loc.on(this)) {   // 위치부터 (단추 안내는 다음에)
            Loc.markOffSeen(this);
            if (locNoAt == 0 || SystemClock.elapsedRealtime() - locNoAt > 10 * 60000) askLocationOn();
            return;
        }
        askOverlay();
    }

    void afterLocOn() { if (mapOpen) askOverlay(); }

    void askOverlay() {
        SharedPreferences sp = prefs();
        if (!sp.getBoolean("bubble", true) || Settings.canDrawOverlays(this) || sp.getBoolean("askedOverlay", false)) return;
        sp.edit().putBoolean("askedOverlay", true).apply();
        new AlertDialog.Builder(this)
            .setTitle("홈 화면에 '포인트 저장' 단추")
            .setMessage("선상 모드를 켠 채 홈 화면으로 나가도 '포인트 저장' 단추가 떠 있게 하려면, 다음 화면에서 '쭈갑이 물때'를 찾아 '다른 앱 위에 표시'를 켜 주세요.")
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

    // ---------- 휴대폰 위치(GPS) 켜기 · 끄기 안내
    /** 위치가 꺼져 있으면 '위치 켜기' 창 (구글 위치 서비스로 한 번에, 안 되면 설정 화면으로) */
    void askLocationOn() {
        if (Loc.on(this)) { locOnNow(); return; }
        if (askingLoc || isFinishing()) return;
        askingLoc = true;
        try {
            LocationRequest lr = new LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 4000).build();
            LocationSettingsRequest r = new LocationSettingsRequest.Builder().addLocationRequest(lr).setAlwaysShow(true).build();
            LocationServices.getSettingsClient(this).checkLocationSettings(r)
                .addOnSuccessListener(this, x -> {
                    askingLoc = false;
                    if (Loc.on(this)) { locOnNow(); afterLocOn(); } else locOnDialog();
                })
                .addOnFailureListener(this, e -> {
                    if (e instanceof ResolvableApiException) {
                        try { ((ResolvableApiException) e).startResolutionForResult(this, REQ_LOCON); return; }
                        catch (Exception x) { Log.w("jjugap", "locon", x); }
                    }
                    askingLoc = false;
                    locOnDialog();
                });
        } catch (Throwable t) {   // 구글 위치 서비스가 없는 휴대폰
            Log.w("jjugap", "locon", t);
            askingLoc = false;
            locOnDialog();
        }
    }

    void locOnDialog() {
        if (isFinishing() || Loc.on(this)) return;
        new AlertDialog.Builder(this)
            .setTitle("위치가 꺼져 있어요")
            .setMessage("포인트 저장과 자동 기록에는 휴대폰 위치(GPS)가 필요해요. 다음 화면에서 '위치'를 켜고 돌아와 주세요.")
            .setPositiveButton("위치 켜기", (d, w) -> { sentLocOn = true; Loc.openSettings(this); })
            .setNegativeButton("나중에", (d, w) -> locNoAt = SystemClock.elapsedRealtime())
            .show();
    }

    /** 위치가 켜졌다 → 웹 앱이 GPS를 다시 받게 */
    void locOnNow() {
        if (web != null) web.evaluateJavascript("window.jjugapLocOn && jjugapLocOn()", null);
    }

    /** 웹 앱에서 부르는 것들 (window.JjugapNative) */
    class Bridge {
        @JavascriptInterface public String version() { return "4"; }   // 3: 조과 카드 보내기·저장·글 복사·사진 넣기 · 4: 길안내 앱(intent:) 열기, 없으면 플레이 스토어
        @JavascriptInterface public void shareImage(String b64, String name) { CardShare.share(MainActivity.this, b64, name); }
        @JavascriptInterface public String saveImage(String b64, String name) { return CardShare.save(MainActivity.this, b64, name); }
        @JavascriptInterface public void copyText(String t) { CardShare.copy(MainActivity.this, t); }
        @JavascriptInterface public boolean locationOn() { return Loc.on(MainActivity.this); }
        @JavascriptInterface public void askLocationOn() { runOnUiThread(MainActivity.this::askLocationOn); }
        @JavascriptInterface public void openLocationSettings() { runOnUiThread(() -> Loc.openSettings(MainActivity.this)); }
        @JavascriptInterface public boolean helpedToday() { return Loc.helped(MainActivity.this); }
        @JavascriptInterface public boolean batteryOk() { return MainActivity.this.batteryOk(); }
        @JavascriptInterface public void askBattery() { runOnUiThread(MainActivity.this::askBattery); }
        @JavascriptInterface public long versionCode() { return Updater.versionCode(MainActivity.this); }
        @JavascriptInterface public void update() { runOnUiThread(() -> Updater.start(MainActivity.this)); }
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
