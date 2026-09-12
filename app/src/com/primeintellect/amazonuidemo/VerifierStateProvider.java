package com.primeintellect.amazonuidemo;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.database.sqlite.SQLiteDatabase;
import android.net.Uri;
import org.json.JSONArray;
import org.json.JSONObject;

/** Shell/DUMP-protected inspection only. Never creates a DB or performs a task action. */
public final class VerifierStateProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
        if (!"/state".equals(uri.getPath()) || projection != null || selection != null || args != null || order != null)
            throw new IllegalArgumentException("Only the fixed state snapshot is supported");
        try (SQLiteDatabase db = SQLiteDatabase.openDatabase(
                getContext().getDatabasePath("shopping.db").getPath(), null, SQLiteDatabase.OPEN_READONLY)) {
            String revision = revision(db);
            {
                JSONObject result = new JSONObject();
                String[] tables = {"products", "cart", "search_history", "eval_session", "eval_events"};
                String[] orders = {"id", "product_id", "query COLLATE BINARY", "singleton", "sequence"};
                for (int i = 0; i < tables.length; i++) {
                    JSONArray rows = new JSONArray();
                    try (Cursor c = db.rawQuery("SELECT * FROM " + tables[i] + " ORDER BY " + orders[i], null)) {
                        while (c.moveToNext()) {
                            JSONObject row = new JSONObject();
                            for (int col = 0; col < c.getColumnCount(); col++) {
                                Object value = c.isNull(col) ? JSONObject.NULL : c.getType(col) == Cursor.FIELD_TYPE_INTEGER
                                    ? Long.valueOf(c.getLong(col)) : c.getString(col);
                                row.put(c.getColumnName(col), value);
                            }
                            rows.put(row);
                        }
                    }
                    result.put(tables[i], rows);
                }
                MatrixCursor cursor = new MatrixCursor(new String[]{"snapshot"});
                cursor.addRow(new Object[]{result.toString()});
                if (!revision.equals(revision(db))) throw new IllegalStateException("Snapshot changed during read");
                return cursor;
            }
        } catch (Exception error) { throw new IllegalStateException("Read-only snapshot unavailable", error); }
    }
    private static String revision(SQLiteDatabase db) {
        try (Cursor c = db.rawQuery("SELECT episode_id,(SELECT COALESCE(MAX(sequence),-1) FROM eval_events) FROM eval_session WHERE singleton=1",null)) {
            if (!c.moveToFirst()) throw new IllegalStateException("No evaluation session");
            return c.getString(0)+":"+c.getLong(1);
        }
    }
    @Override public String getType(Uri uri) { return "application/json"; }
    @Override public Uri insert(Uri u, ContentValues v) { throw new UnsupportedOperationException("Read only"); }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException("Read only"); }
    @Override public int delete(Uri u, String s, String[] a) { throw new UnsupportedOperationException("Read only"); }
}

