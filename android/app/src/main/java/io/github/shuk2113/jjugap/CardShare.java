package io.github.shuk2113.jjugap;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentProvider;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.ParcelFileDescriptor;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.util.Base64;
import android.util.Log;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * 조과 카드: 웹 앱이 그린 카드 그림(JPEG)을
 * - 보내기: 카톡·밴드·문자 등 고르는 창으로 (앱 안 임시 파일 → CardShare.Files 로 잠깐 빌려 준다)
 * - 저장: 사진첩 'Pictures/쭈갑이 물때' 에
 * - 글 복사: 클립보드에
 */
public final class CardShare {
    static final String AUTH = "io.github.shuk2113.jjugap.cards";
    static final int REQ_WRITE = 21;

    static String safeName(String n) {
        String s = n == null ? "" : n.replaceAll("[^A-Za-z0-9._-]", "");
        if (s.isEmpty() || s.startsWith(".")) s = "jjugap-card.jpg";
        if (!s.endsWith(".jpg")) s += ".jpg";
        return s.length() > 80 ? s.substring(s.length() - 80) : s;
    }

    static File dir(Activity a) { File d = new File(a.getCacheDir(), "cards"); if (!d.exists()) d.mkdirs(); return d; }

    /** 보내기 창 열기 (오래된 카드 파일은 지운다) */
    static void share(Activity a, String b64, String name) {
        try {
            byte[] img = Base64.decode(b64, Base64.DEFAULT);
            File d = dir(a);
            File[] old = d.listFiles();
            if (old != null) for (File f : old) if (System.currentTimeMillis() - f.lastModified() > 3600_000L) f.delete();
            File f = new File(d, safeName(name));
            try (FileOutputStream o = new FileOutputStream(f)) { o.write(img); }
            Uri u = Uri.parse("content://" + AUTH + "/" + f.getName());
            Intent send = new Intent(Intent.ACTION_SEND).setType("image/jpeg").putExtra(Intent.EXTRA_STREAM, u)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setClipData(ClipData.newRawUri("", u));
            Intent ch = Intent.createChooser(send, "조과 카드 보내기").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            a.runOnUiThread(() -> { try { a.startActivity(ch); Log.i("jjugap", "card share " + img.length); } catch (Exception e) { Log.w("jjugap", "card share", e); } });
        } catch (Exception e) { Log.w("jjugap", "card share", e); }
    }

    /** 사진첩에 저장 → "ok" · 권한을 묻는 중이면 "perm" · 못 하면 "" */
    static String save(Activity a, String b64, String name) {
        try {
            if (Build.VERSION.SDK_INT < 29 && a.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
                a.runOnUiThread(() -> a.requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_WRITE));
                return "perm";
            }
            byte[] img = Base64.decode(b64, Base64.DEFAULT);
            ContentResolver cr = a.getContentResolver();
            ContentValues v = new ContentValues();
            v.put(MediaStore.Images.Media.DISPLAY_NAME, safeName(name));
            v.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            if (Build.VERSION.SDK_INT >= 29) {
                v.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/쭈갑이 물때");
                v.put(MediaStore.Images.Media.IS_PENDING, 1);
            } else {
                File d = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), "쭈갑이 물때");
                if (!d.exists()) d.mkdirs();
                v.put(MediaStore.Images.Media.DATA, new File(d, safeName(name)).getAbsolutePath());
            }
            Uri u = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            if (u == null) return "";
            try (OutputStream o = cr.openOutputStream(u)) { if (o == null) return ""; o.write(img); }
            if (Build.VERSION.SDK_INT >= 29) { ContentValues done = new ContentValues(); done.put(MediaStore.Images.Media.IS_PENDING, 0); cr.update(u, done, null, null); }
            Log.i("jjugap", "card saved " + img.length);
            return "ok";
        } catch (Exception e) { Log.w("jjugap", "card save", e); return ""; }
    }

    static void copy(Activity a, String text) {
        a.runOnUiThread(() -> {
            try {
                ClipboardManager cm = a.getSystemService(ClipboardManager.class);
                cm.setPrimaryClip(ClipData.newPlainText("조과", text));
                Log.i("jjugap", "card copy " + text.length());
            } catch (Exception e) { Log.w("jjugap", "card copy", e); }
        });
    }

    /** 보내기 창에서 고른 앱이 카드 그림을 읽어 가는 곳 (읽기만 · 앱 안 임시 폴더의 카드 파일만) */
    public static class Files extends ContentProvider {
        File file(Uri u) throws FileNotFoundException {
            String n = u.getLastPathSegment();
            if (n == null || !n.equals(safeName(n))) throw new FileNotFoundException();
            File f = new File(new File(getContext().getCacheDir(), "cards"), n);
            if (!f.exists()) throw new FileNotFoundException();
            return f;
        }
        @Override public boolean onCreate() { return true; }
        @Override public String getType(Uri u) { return "image/jpeg"; }
        @Override public ParcelFileDescriptor openFile(Uri u, String mode) throws FileNotFoundException {
            return ParcelFileDescriptor.open(file(u), ParcelFileDescriptor.MODE_READ_ONLY);
        }
        @Override public Cursor query(Uri u, String[] proj, String sel, String[] args, String sort) {
            String[] cols = proj != null ? proj : new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE};
            MatrixCursor c = new MatrixCursor(cols);
            try {
                File f = file(u); Object[] row = new Object[cols.length];
                for (int i = 0; i < cols.length; i++) {
                    if (OpenableColumns.DISPLAY_NAME.equals(cols[i])) row[i] = f.getName();
                    else if (OpenableColumns.SIZE.equals(cols[i])) row[i] = f.length();
                    else if (MediaStore.MediaColumns.MIME_TYPE.equals(cols[i])) row[i] = "image/jpeg";
                }
                c.addRow(row);
            } catch (FileNotFoundException ignored) { }
            return c;
        }
        @Override public Uri insert(Uri u, ContentValues v) { throw new UnsupportedOperationException(); }
        @Override public int delete(Uri u, String s, String[] a) { throw new UnsupportedOperationException(); }
        @Override public int update(Uri u, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
    }
}
