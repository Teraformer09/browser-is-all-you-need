package com.primeintellect.amazonuidemo;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONObject;
import org.json.JSONArray;

/** Device-local data only. Called exclusively on MainActivity's serial executor. */
public final class Store extends SQLiteOpenHelper {
    public static final class Product {
        public final int id, kind, quantity;
        public final String name, category, description, sku;
        public final long price, mrp; // integer paise, never binary floating-point money
        Product(Cursor c) {
            id = c.getInt(0); name = c.getString(1); price = c.getLong(2);
            mrp = c.getLong(3); kind = c.getInt(4); category = c.getString(5);
            description = c.getString(6); sku = c.getString(7); quantity = c.getInt(8);
        }
    }

    public static final class Snapshot {
        public final List<Product> products = new ArrayList<>();
        public final List<String> history = new ArrayList<>();
        public final List<Integer> viewed = new ArrayList<>();
        public String address, profile;
        public long wallet, total;
        public int count;
        public boolean walletSeen;
        public Product byId(int id) {
            for (Product p : products) if (p.id == id) return p;
            return null;
        }
    }

    public Store(Context context) { this(context, "shopping.db"); }
    Store(Context context, String name) { super(context, name, null, 3); }

    @Override public void onConfigure(SQLiteDatabase db) {
        db.setForeignKeyConstraintsEnabled(true);
    }

    @Override public void onCreate(SQLiteDatabase db) {
        // Keep the original v1 columns so existing installations upgrade without losing their cart.
        db.execSQL("CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,kind INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE cart(product_id INTEGER PRIMARY KEY REFERENCES products(id),qty INTEGER NOT NULL CHECK(qty>0))");
        String[] names = {"Nimbus Wireless Headphones", "Trail Steel Water Bottle",
            "Metro Laptop Backpack", "Pulse Sport Headphones", "Daily Glass Water Bottle", "Urban Travel Backpack"};
        int[] prices = {2499, 699, 1799, 1499, 499, 2199};
        for (int i = 0; i < names.length; i++) {
            db.execSQL("INSERT INTO products VALUES(?,?,?,?)", new Object[]{i + 1, names[i], prices[i], i % 3});
        }
        onUpgrade(db, 1, 3);
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE products ADD COLUMN price_paise INTEGER NOT NULL DEFAULT 0");
            db.execSQL("ALTER TABLE products ADD COLUMN mrp_paise INTEGER NOT NULL DEFAULT 0");
            db.execSQL("ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'Electronics'");
            db.execSQL("ALTER TABLE products ADD COLUMN description TEXT NOT NULL DEFAULT ''");
            db.execSQL("ALTER TABLE products ADD COLUMN sku TEXT NOT NULL DEFAULT ''");
            db.execSQL("UPDATE products SET price_paise=price*100, mrp_paise=(price+1000)*100");
            db.execSQL("UPDATE products SET mrp_paise=399900 WHERE id=1");
            db.execSQL("UPDATE products SET mrp_paise=99900 WHERE id=2");
            db.execSQL("UPDATE products SET mrp_paise=299900 WHERE id=3");
            db.execSQL("UPDATE products SET category='Home' WHERE kind=1");
            db.execSQL("UPDATE products SET category='Travel' WHERE kind=2");
            db.execSQL("UPDATE products SET sku=printf('DC%03d',id), description='An offline demonstration product. No real orders, reviews or delivery.'");
            seed(db, 7, "Nimbus Vision 55-inch QLED TV", 3299900, 5499900, 3, "Electronics",
                "A vivid 55-inch QLED display, slim bezel and room-filling sound. Fictional demo specifications.");
            seed(db, 8, "Fresh Orchard Fruit Basket", 39900, 59900, 4, "Fresh",
                "An illustrated assortment of fruit for this local grocery demo.");
            seed(db, 9, "Everyday Travel Pill Organiser", 24900, 39900, 5, "Wellness",
                "A seven-day storage accessory. No medicine, medical advice or prescription service.");
            db.execSQL("CREATE TABLE search_history(query TEXT PRIMARY KEY COLLATE NOCASE, searched_at INTEGER NOT NULL)");
            db.execSQL("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)");
            db.execSQL("CREATE TABLE viewed(product_id INTEGER PRIMARY KEY REFERENCES products(id), viewed_at INTEGER NOT NULL)");
            put(db, "profile", "Tirtha");
            put(db, "address", "New Delhi 110001");
            put(db, "wallet_paise", "125000");
            put(db, "wallet_seen", "false");
        }
        if (oldVersion < 3 && newVersion >= 3) {
            db.execSQL("CREATE TABLE eval_session(singleton INTEGER PRIMARY KEY CHECK(singleton=1),episode_id TEXT NOT NULL,page TEXT NOT NULL,draft TEXT NOT NULL,query TEXT NOT NULL)");
            db.execSQL("CREATE TABLE eval_events(sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL)");
        }
    }

    private static void seed(SQLiteDatabase db, int id, String name, long price, long mrp,
                             int kind, String category, String description) {
        db.execSQL("INSERT INTO products(id,name,price,kind,price_paise,mrp_paise,category,description,sku) VALUES(?,?,?,?,?,?,?,?,?)",
            new Object[]{id, name, price / 100, kind, price, mrp, category, description, String.format(java.util.Locale.ROOT,"DC%03d",id)});
    }

    private static void put(SQLiteDatabase db, String key, String value) {
        ContentValues cv = new ContentValues();
        cv.put("key", key); cv.put("value", value);
        db.insertWithOnConflict("settings", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
    }

    public void setting(String key, String value) {
        if (!java.util.Arrays.asList("profile", "address", "wallet_paise", "wallet_seen").contains(key))
            throw new IllegalArgumentException("Unknown setting");
        put(getWritableDatabase(), key, value);
    }

    private String setting(SQLiteDatabase db, String key, String fallback) {
        try (Cursor c = db.rawQuery("SELECT value FROM settings WHERE key=?", new String[]{key})) {
            return c.moveToFirst() ? c.getString(0) : fallback;
        }
    }

    public void add(int id) {
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor c = db.rawQuery("SELECT qty FROM cart WHERE product_id=?", new String[]{String.valueOf(id)})) {
                if (c.moveToFirst()) {
                    if (c.getInt(0) >= 99) throw new IllegalArgumentException("Demo limit: 99 of one item");
                    db.execSQL("UPDATE cart SET qty=qty+1 WHERE product_id=?", new Object[]{id});
                } else {
                    db.execSQL("INSERT INTO cart(product_id,qty) VALUES(?,1)", new Object[]{id});
                }
            }
            audit(db, "add", json("product_id", id, "quantity_after", quantity(db,id)));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    public void decrease(int id) {
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            db.execSQL("DELETE FROM cart WHERE product_id=? AND qty=1", new Object[]{id});
            db.execSQL("UPDATE cart SET qty=qty-1 WHERE product_id=? AND qty>1", new Object[]{id});
            audit(db, "decrease", json("product_id", id, "quantity_after", quantity(db,id)));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    public void remove(int id) {
        SQLiteDatabase db = getWritableDatabase(); db.beginTransaction();
        try {
            db.delete("cart", "product_id=?", new String[]{String.valueOf(id)});
            audit(db, "remove", json("product_id", id, "quantity_after", 0));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    public void saveSearch(String query) {
        String q = query.trim();
        if (q.isEmpty()) return;
        if (q.length() > 120) q = q.substring(0, 120);
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            ContentValues cv = new ContentValues();
            cv.put("query", q); cv.put("searched_at", System.currentTimeMillis());
            db.insertWithOnConflict("search_history", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
            db.execSQL("DELETE FROM search_history WHERE query NOT IN (SELECT query FROM search_history ORDER BY searched_at DESC,rowid DESC LIMIT 10)");
            db.execSQL("UPDATE eval_session SET query=?,draft=? WHERE singleton=1", new Object[]{q,q});
            audit(db, "search", json("query", q));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    public void clearHistory() { getWritableDatabase().delete("search_history", null, null); }

    public void viewed(int id) {
        ContentValues cv = new ContentValues();
        cv.put("product_id", id); cv.put("viewed_at", System.currentTimeMillis());
        getWritableDatabase().insertWithOnConflict("viewed", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
    }

    public void topUp() {
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            long current = Long.parseLong(setting(db, "wallet_paise", "125000"));
            if (current >= 10000000) throw new IllegalArgumentException("Demo wallet limit reached");
            put(db, "wallet_paise", String.valueOf(current + 50000));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    private static JSONObject json(Object... pairs) {
        try { JSONObject out = new JSONObject(); for(int i=0;i<pairs.length;i+=2) out.put((String)pairs[i],pairs[i+1]); return out; }
        catch (Exception error) { throw new IllegalStateException(error); }
    }
    private static int quantity(SQLiteDatabase db,int id) {
        try(Cursor c=db.rawQuery("SELECT qty FROM cart WHERE product_id=?",new String[]{String.valueOf(id)})) { return c.moveToFirst()?c.getInt(0):0; }
    }
    private static void audit(SQLiteDatabase db,String kind,JSONObject payload) {
        try(Cursor c=db.rawQuery("SELECT episode_id FROM eval_session WHERE singleton=1",null)) { if(!c.moveToFirst()) return; }
        db.execSQL("INSERT INTO eval_events(sequence,kind,payload) SELECT COALESCE(MAX(sequence),-1)+1,?,? FROM eval_events",
            new Object[]{kind,payload.toString()});
    }
    /** Reset is available only through an explicit harness launch on a disposable emulator. */
    public void startEvaluation(String episode) {
        if(episode==null) return;
        if(!episode.matches("peach_[a-f0-9]{32}")) throw new IllegalArgumentException("Invalid episode identity");
        SQLiteDatabase db=getWritableDatabase(); db.beginTransaction();
        try {
            try(Cursor c=db.rawQuery("SELECT episode_id FROM eval_session WHERE singleton=1",null)) {
                if(c.moveToFirst() && episode.equals(c.getString(0))) { db.setTransactionSuccessful(); return; }
            }
            db.delete("cart",null,null); db.delete("search_history",null,null); db.delete("eval_events",null,null);
            db.delete("eval_session",null,null);
            db.execSQL("INSERT INTO eval_session VALUES(1,?,'home','','')",new Object[]{episode});
            audit(db,"reset",json("episode_id",episode));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    public void viewport(String page,String draft,String query) {
        SQLiteDatabase db=getWritableDatabase(); db.beginTransaction();
        try {
            try(Cursor c=db.rawQuery("SELECT page,draft,query FROM eval_session WHERE singleton=1",null)) {
                if(!c.moveToFirst() || (page.equals(c.getString(0)) && draft.equals(c.getString(1)) && query.equals(c.getString(2)))) {
                    db.setTransactionSuccessful(); return;
                }
            }
            db.execSQL("UPDATE eval_session SET page=?,draft=?,query=? WHERE singleton=1",new Object[]{page,draft,query});
            audit(db,"viewport",json("page",page,"draft",draft,"query",query));
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    public Snapshot snapshot() {
        SQLiteDatabase db = getReadableDatabase();
        Snapshot s = new Snapshot();
        try (Cursor c = db.rawQuery("SELECT p.id,p.name,p.price_paise,p.mrp_paise,p.kind,p.category,p.description,p.sku,COALESCE(c.qty,0) FROM products p LEFT JOIN cart c ON p.id=c.product_id ORDER BY p.id", null)) {
            while (c.moveToNext()) {
                Product p = new Product(c); s.products.add(p);
                s.count += p.quantity; s.total += p.price * p.quantity;
            }
        }
        try (Cursor c = db.rawQuery("SELECT query FROM search_history ORDER BY searched_at DESC,rowid DESC LIMIT 10", null)) {
            while (c.moveToNext()) s.history.add(c.getString(0));
        }
        try (Cursor c = db.rawQuery("SELECT product_id FROM viewed ORDER BY viewed_at DESC LIMIT 6", null)) {
            while (c.moveToNext()) s.viewed.add(c.getInt(0));
        }
        s.profile = setting(db, "profile", "Tirtha");
        s.address = setting(db, "address", "New Delhi 110001");
        s.wallet = Long.parseLong(setting(db, "wallet_paise", "125000"));
        s.walletSeen = Boolean.parseBoolean(setting(db, "wallet_seen", "false"));
        return s;
    }
}


