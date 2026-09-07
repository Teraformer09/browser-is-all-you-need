package com.primeintellect.shoppingdemo;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public final class VerifierStateProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
        if (!"/state".equals(uri.getPath())) throw new IllegalArgumentException("Unknown verifier path");
        final String[] snapshot = new String[1];
        final RuntimeException[] error = new RuntimeException[1];
        CountDownLatch done = new CountDownLatch(1);
        Runnable read = () -> {
            try { snapshot[0] = MainActivity.verifierSnapshot(); }
            catch (RuntimeException ex) { error[0] = ex; }
            finally { done.countDown(); }
        };
        if (Looper.myLooper() == Looper.getMainLooper()) read.run();
        else new Handler(Looper.getMainLooper()).post(read);
        try {
            if (!done.await(2, TimeUnit.SECONDS)) throw new IllegalStateException("Snapshot timeout");
        } catch (InterruptedException ex) { Thread.currentThread().interrupt(); throw new IllegalStateException(ex); }
        if (error[0] != null) throw error[0];
        MatrixCursor cursor = new MatrixCursor(new String[]{"snapshot"});
        cursor.addRow(new Object[]{snapshot[0]});
        return cursor;
    }
    @Override public String getType(Uri uri) { return "application/json"; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException("Read only"); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException("Read only"); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException("Read only"); }
}
