package io.github.shuk2113.jjugap;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.View;

/** 단추를 끌 때 아래에 나오는 × (여기 놓으면 단추를 숨긴다) */
public class TrashView extends View {
    final float dp;
    final Paint bg = new Paint(Paint.ANTI_ALIAS_FLAG), x = new Paint(Paint.ANTI_ALIAS_FLAG);
    boolean hot;

    public TrashView(Context c) {
        super(c);
        dp = getResources().getDisplayMetrics().density;
        x.setColor(0xFFFFFFFF);
        x.setStyle(Paint.Style.STROKE);
        x.setStrokeCap(Paint.Cap.ROUND);
        x.setStrokeWidth(3 * dp);
    }

    void setHot(boolean h) { if (h != hot) { hot = h; invalidate(); } }

    @Override
    protected void onDraw(Canvas c) {
        float cx = getWidth() / 2f, cy = getHeight() / 2f, r = (hot ? 31 : 26) * dp, k = 8 * dp;
        bg.setColor(hot ? 0xF0E5484D : 0xB3101820);
        c.drawCircle(cx, cy, r, bg);
        c.drawLine(cx - k, cy - k, cx + k, cy + k, x);
        c.drawLine(cx + k, cy - k, cx - k, cy + k, x);
    }
}
