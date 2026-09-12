package com.primeintellect.amazonuidemo;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.os.Bundle;
import java.util.UUID;

/** Developer storage tests, not a task verifier or an agent evaluation. */
public final class StorageSmokeTest extends Instrumentation {
    private int checks;
    @Override public void onCreate(Bundle args) { super.onCreate(args); start(); }
    private void check(boolean value,String reason) {
        if(!value)throw new AssertionError(reason);
        checks++;
    }
    @Override public void onStart() {
        Bundle report=new Bundle();
        Context c=getTargetContext();
        String name="ui-smoke-"+UUID.randomUUID()+".db";
        Store store=null;
        try {
            // Real version-one fixture: opening the v2 helper must migrate, not reset it.
            SQLiteDatabase old=c.openOrCreateDatabase(name,0,null);
            old.execSQL("CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,kind INTEGER NOT NULL)");
            old.execSQL("CREATE TABLE cart(product_id INTEGER PRIMARY KEY REFERENCES products(id),qty INTEGER NOT NULL CHECK(qty>0))");
            String[] names={"Nimbus Wireless Headphones","Trail Steel Water Bottle","Metro Laptop Backpack",
                "Pulse Sport Headphones","Daily Glass Water Bottle","Urban Travel Backpack"};
            int[] prices={2499,699,1799,1499,499,2199};
            for(int i=0;i<6;i++)old.execSQL("INSERT INTO products VALUES(?,?,?,?)",new Object[]{i+1,names[i],prices[i],i%3});
            old.execSQL("INSERT INTO cart VALUES(1,1),(2,1),(3,1)");old.setVersion(1);old.close();
            store=new Store(c,name);
            Store.Snapshot s=store.snapshot();
            check(s.products.size()==9,"migration seeds new catalog");
            check(s.count==3,"v1 cart retained");
            check(s.total==499700,"rupee-to-paise migration preserves INR 4997 total");
            check(s.byId(1).price==249900,"integer paise price");
            check(s.byId(7).price==3299900,"TV catalog price");
            store.add(1);check(store.snapshot().byId(1).quantity==2,"atomic increment");
            store.decrease(1);check(store.snapshot().byId(1).quantity==1,"decrement");
            store.decrease(2);check(store.snapshot().byId(2).quantity==0,"decrement to zero removes");
            store.add(2);store.remove(2);check(store.snapshot().byId(2).quantity==0,"delete");
            store.add(2);
            store.saveSearch("  Headphones  ");store.saveSearch("headphones");
            check(store.snapshot().history.size()==1,"case-insensitive search dedup");
            store.saveSearch("x' OR 1=1 --");
            check(store.snapshot().history.contains("x' OR 1=1 --"),"search stored as data");
            for(int i=0;i<15;i++)store.saveSearch("query"+i);
            check(store.snapshot().history.size()==10,"bounded history");
            store.setting("address","New Delhi 110002");store.setting("profile","Test Shopper");
            store.topUp();store.viewed(3);store.setting("wallet_seen","true");
            store.close();store=new Store(c,name);s=store.snapshot();
            check(s.count==3&&s.total==499700,"cart survives reopen");
            check(s.address.equals("New Delhi 110002"),"address persists");
            check(s.profile.equals("Test Shopper"),"profile persists");
            check(s.wallet==175000,"wallet demo credits persist");
            check(s.walletSeen,"wallet notification acknowledged");
            check(s.viewed.contains(3),"browsing history persists");
            store.clearHistory();check(store.snapshot().history.isEmpty(),"clear search history");
            for(int i=1;i<99;i++)store.add(1);
            boolean capped=false;try{store.add(1);}catch(IllegalArgumentException expected){capped=true;}
            check(capped&&store.snapshot().byId(1).quantity==99,"quantity cap rolls back cleanly");
            report.putString("stream","Storage smoke tests: "+checks+" checks passed. No evaluation, model or reward.\n");
            finish(Activity.RESULT_OK,report);
        } catch(Throwable failure) {
            report.putString("stream","FAILED after "+checks+" checks: "+failure+"\n");
            finish(Activity.RESULT_CANCELED,report);
        } finally {
            if(store!=null)store.close();
            c.deleteDatabase(name); // Only the uniquely named disposable test database.
        }
    }
}

