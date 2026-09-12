package com.primeintellect.amazonuidemo;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.view.View;

/** Original vector-like artwork, drawn locally. No downloaded product photos or brand assets. */
public final class ProductArt extends View {
    private final int kind;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private boolean animated;
    public ProductArt(Context c, int kind) {
        super(c); this.kind = kind;
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }
    public void setAnimated(boolean enabled) { animated = enabled; invalidate(); }
    private void rect(Canvas c, int color, float l, float t, float r, float b, float radius) {
        paint.setShader(null); paint.setStyle(Paint.Style.FILL); paint.setColor(color);
        c.drawRoundRect(l,t,r,b,radius,radius,paint);
    }
    private void ellipse(Canvas c, int color, float l, float t, float r, float b) {
        paint.setShader(null); paint.setColor(color); paint.setStyle(Paint.Style.FILL);
        c.drawOval(l,t,r,b,paint);
    }
    private void line(Canvas c, int color, float width, float x, float y, float x2, float y2) {
        paint.setShader(null); paint.setColor(color); paint.setStrokeWidth(width);
        paint.setStrokeCap(Paint.Cap.ROUND); c.drawLine(x,y,x2,y2,paint);
    }
    @Override protected void onDraw(Canvas c) {
        super.onDraw(c); c.save();
        float scale = Math.min(getWidth()/180f,getHeight()/140f);
        c.translate((getWidth()-180*scale)/2,(getHeight()-140*scale)/2); c.scale(scale,scale);
        ellipse(c,0x14000000,22,122,158,132);
        if (kind == 0) headphones(c);
        else if (kind == 1) bottle(c);
        else if (kind == 2) backpack(c);
        else if (kind == 3) television(c);
        else if (kind == 4) fruit(c);
        else organiser(c);
        c.restore();
        if (animated && isShown()) postInvalidateDelayed(40);
    }
    private void headphones(Canvas c) {
        paint.setColor(0xff1b2635); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(13);
        c.drawArc(41,15,139,114,180,180,false,paint);
        paint.setColor(0xff526173); paint.setStrokeWidth(3);
        c.drawArc(38,11,142,117,188,164,false,paint);
        paint.setStyle(Paint.Style.FILL);
        rect(c,0xff263747,31,62,60,119,12); rect(c,0xff263747,120,62,149,119,12);
        rect(c,0xff111a24,37,69,48,114,5); rect(c,0xff111a24,132,69,143,114,5);
        rect(c,0xff657284,49,73,55,105,3); rect(c,0xff657284,124,73,130,105,3);
        line(c,0xffc3d0d8,2,37,60,51,56); line(c,0xffc3d0d8,2,129,56,143,60);
    }
    private void bottle(Canvas c) {
        rect(c,0xff284438,71,10,109,27,4);
        for(int i=0;i<4;i++) line(c,0xff5b7366,1,75,14+i*3,105,14+i*3);
        rect(c,0xff7b9887,62,28,118,127,16);
        paint.setShader(new LinearGradient(62,0,118,0,new int[]{0xff304e44,0xff89a793,0xff5d7a67,0xff294e3d},null,Shader.TileMode.CLAMP));
        c.drawRoundRect(62,31,118,124,14,14,paint); paint.setShader(null);
        rect(c,0x66c9e3cb,68,40,73,113,3);
        paint.setColor(0xffe7efe7); paint.setTypeface(Typeface.create("sans-serif-medium",0)); paint.setTextSize(10);
        c.drawText("TRAIL",75,82,paint); line(c,0xffd4e2d5,1,82,89,99,89);
    }
    private void backpack(Canvas c) {
        rect(c,0xff344255,72,8,108,28,8); rect(c,0xffd8c2ae,79,13,101,22,3);
        rect(c,0xff31415a,40,26,140,128,18);
        paint.setShader(new LinearGradient(45,0,135,0,0xff8090a6,0xff415773,Shader.TileMode.CLAMP));
        c.drawRoundRect(45,25,135,122,16,16,paint); paint.setShader(null);
        rect(c,0xff647891,52,35,128,73,10); line(c,0xffb6c2ce,1,58,37,121,37);
        rect(c,0xff354b64,54,80,126,118,9); line(c,0xffb6c2ce,1,61,86,118,86);
        rect(c,0xffc9b598,80,51,104,60,2); line(c,0xffcbd0d6,2,119,86,119,94);
        rect(c,0xff293d55,34,83,43,115,3); rect(c,0xff293d55,137,83,146,115,3);
    }
    private void television(Canvas c) {
        line(c,0xff27323a,4,48,110,38,127); line(c,0xff27323a,4,132,110,142,127);
        rect(c,0xff1b242e,8,9,172,114,4);
        paint.setShader(new LinearGradient(10,10,155,109,new int[]{0xff102b54,0xff186e88,0xff78d4ba,0xfff3aa84},null,Shader.TileMode.CLAMP));
        c.drawRect(12,13,168,107,paint); paint.setShader(null);
        float shift = animated ? (float)Math.sin(System.currentTimeMillis()/1000.0)*8 : 0;
        ellipse(c,0xffffdfad,114+shift,26,140+shift,52);
        Path mountain = new Path(); mountain.moveTo(12,99); mountain.lineTo(54,36); mountain.lineTo(92,91);
        mountain.lineTo(127,60); mountain.lineTo(168,103); mountain.close();
        paint.setColor(0xff23677c); c.drawPath(mountain,paint);
        Path snow = new Path(); snow.moveTo(38,60); snow.lineTo(54,36); snow.lineTo(71,62);
        snow.lineTo(56,53); snow.lineTo(49,58); snow.close(); paint.setColor(0xffd8eceb); c.drawPath(snow,paint);
        Path water = new Path(); water.moveTo(12,89); water.cubicTo(61,77,101,116,168,82);
        water.lineTo(168,107); water.lineTo(12,107); water.close();
        paint.setColor(0xff72b6b9); c.drawPath(water,paint);
        line(c,0xffafd3cb,1,74,97,127,98);
    }
    private void fruit(Canvas c) {
        rect(c,0xffb68854,38,71,145,125,12);
        for(int i=0;i<7;i++) line(c,0xffe7be83,3,43+i*15,76,43+i*15,120);
        ellipse(c,0xffcd4945,44,35,89,86); ellipse(c,0xffeba545,81,45,130,91);
        ellipse(c,0xff74a653,107,32,145,77);
        line(c,0xff395635,3,64,39,69,27); ellipse(c,0xff466e36,70,23,88,33);
        ellipse(c,0xffe98d75,50,40,59,54);
    }
    private void organiser(Canvas c) {
        rect(c,0xffe1eceb,21,37,158,116,12);
        int[] colors={0xffe6b7c8,0xffb5d9e0,0xffbbd3ae,0xffe9cc97};
        for(int i=0;i<4;i++) {
            rect(c,colors[i],27+i*32,44,55+i*32,109,5);
            paint.setColor(0xff48585b); paint.setTextSize(9);
            c.drawText(new String[]{"M","T","W","T"}[i],37+i*32,65,paint);
            line(c,0x8895a5a7,1,30+i*32,80,52+i*32,80);
        }
    }
}

