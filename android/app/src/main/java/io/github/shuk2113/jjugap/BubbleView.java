package io.github.shuk2113.jjugap;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.View;

/** 홈 화면 위에 떠 있는 '포인트 저장' 단추: 파란 동그라미 안 흰 핀(+), 아래에 작은 글씨 */
public class BubbleView extends View {
    final float dp;
    final Paint circle = new Paint(Paint.ANTI_ALIAS_FLAG), pin = new Paint(Paint.ANTI_ALIAS_FLAG),
        pill = new Paint(Paint.ANTI_ALIAS_FLAG), text = new Paint(Paint.ANTI_ALIAS_FLAG);
    final Path pinPath = new Path(), plus = new Path();
    boolean down;
    static final String LABEL = "포인트 저장";

    public BubbleView(Context c) {
        super(c);
        dp = getResources().getDisplayMetrics().density;
        setLayerType(LAYER_TYPE_SOFTWARE, null);   // 그림자
        circle.setColor(0xFF2F7DF6);
        circle.setShadowLayer(6 * dp, 0, 2 * dp, 0x66000000);
        pin.setColor(0xFFFFFFFF);
        pin.setStyle(Paint.Style.STROKE);
        pin.setStrokeJoin(Paint.Join.ROUND);
        pin.setStrokeCap(Paint.Cap.ROUND);
        pill.setColor(0xE60D1819);
        pill.setShadowLayer(3 * dp, 0, 1 * dp, 0x44000000);
        text.setColor(0xFFFFFFFF);
        text.setTextSize(12 * dp);
        text.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        text.setTextAlign(Paint.Align.CENTER);
        // 24칸 기준 핀 모양 (웹 앱 단추와 같은 그림)
        pinPath.moveTo(12f, 21.3f);
        pinPath.cubicTo(9.5f, 18.9f, 5.4f, 14.6f, 5.4f, 10f);
        pinPath.arcTo(new RectF(5.4f, 3.4f, 18.6f, 16.6f), 180f, 180f);
        pinPath.cubicTo(18.6f, 14.6f, 14.5f, 18.9f, 12f, 21.3f);
        pinPath.close();
        plus.moveTo(12f, 7f); plus.lineTo(12f, 13f);
        plus.moveTo(9f, 10f); plus.lineTo(15f, 10f);
    }

    void setDown(boolean d) { down = d; invalidate(); }

    @Override
    protected void onDraw(Canvas c) {
        float w = getWidth(), cx = w / 2f, r = 28 * dp * (down ? 0.93f : 1f), cy = 6 * dp + 28 * dp;
        c.drawCircle(cx, cy, r, circle);
        float s = 30 * dp / 24f * (down ? 0.93f : 1f);
        Matrix m = new Matrix();
        m.setScale(s, s);
        m.postTranslate(cx - 12 * s, cy - 12.4f * s);
        Path a = new Path(pinPath), b = new Path(plus);
        a.transform(m); b.transform(m);
        pin.setStrokeWidth(2.1f * s);
        c.drawPath(a, pin);
        pin.setStrokeWidth(2.3f * s);
        c.drawPath(b, pin);
        float tw = text.measureText(LABEL), ph = 20 * dp, top = cy + 28 * dp + 5 * dp;
        RectF rr = new RectF(cx - tw / 2 - 8 * dp, top, cx + tw / 2 + 8 * dp, top + ph);
        c.drawRoundRect(rr, ph / 2, ph / 2, pill);
        Paint.FontMetrics fm = text.getFontMetrics();
        c.drawText(LABEL, cx, top + ph / 2 - (fm.ascent + fm.descent) / 2, text);
    }
}
