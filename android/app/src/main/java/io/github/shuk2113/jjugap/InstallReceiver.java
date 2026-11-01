package io.github.shuk2113.jjugap;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.os.Build;
import android.util.Log;
import android.widget.Toast;

/** 업데이트 설치 결과: 사용자 확인이 필요하면 휴대폰의 '업데이트할까요?' 화면을 띄운다 */
public class InstallReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        int st = i.getIntExtra(PackageInstaller.EXTRA_STATUS, -999);
        Log.i("jjugap", "install status " + st + " " + i.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE));
        if (st == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirm = Build.VERSION.SDK_INT >= 33 ? i.getParcelableExtra(Intent.EXTRA_INTENT, Intent.class) : i.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirm != null) {
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                try { c.startActivity(confirm); } catch (Exception e) { Log.w("jjugap", "confirm", e); }
            }
        } else if (st != PackageInstaller.STATUS_SUCCESS) {
            Toast.makeText(c, "업데이트가 되지 않았어요. 다시 눌러 주세요", Toast.LENGTH_LONG).show();
        }
    }
}
