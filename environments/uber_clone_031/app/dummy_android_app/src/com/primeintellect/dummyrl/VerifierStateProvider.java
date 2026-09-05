package com.primeintellect.dummyrl;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** DUMP-permission protected. Reads live fields on the UI thread; never mutates the app. */
public class VerifierStateProvider extends ContentProvider {
  @Override public boolean onCreate() { return true; }
  @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
    if (!"state".equals(uri.getLastPathSegment())) { throw new IllegalArgumentException("Unknown verifier URI"); }
    final String[] snapshot = new String[1];
    final RuntimeException[] failure = new RuntimeException[1];
    final CountDownLatch ready = new CountDownLatch(1);
    Runnable capture = new Runnable() {
      public void run() {
        try { snapshot[0] = MainActivity.verifierSnapshot(); }
        catch (RuntimeException error) { failure[0] = error; }
        finally { ready.countDown(); }
      }
    };
    if (Looper.myLooper() == Looper.getMainLooper()) { capture.run(); }
    else { new Handler(Looper.getMainLooper()).post(capture); }
    try {
      if (!ready.await(2, TimeUnit.SECONDS)) { throw new IllegalStateException("Snapshot timeout"); }
    } catch (InterruptedException error) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(error);
    }
    if (failure[0] != null) { throw failure[0]; }
    MatrixCursor result = new MatrixCursor(new String[]{"snapshot"});
    result.addRow(new Object[]{snapshot[0]});
    return result;
  }
  @Override public String getType(Uri uri) { return "application/json"; }
  @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException("Read only"); }
  @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException("Read only"); }
  @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException("Read only"); }
}
