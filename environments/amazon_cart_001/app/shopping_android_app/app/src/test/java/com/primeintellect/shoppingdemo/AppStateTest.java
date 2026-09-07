package com.primeintellect.shoppingdemo;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.List;
import java.util.Map;

public class AppStateTest {
    private AppState state(){return new AppState("test_cart_episode");}
    private void add(AppState s,String query,String sku){s.draft(query);s.search();s.add(sku);}
    @Test public void catalogHasSixDistinctProducts(){assertEquals(6,Catalog.PRODUCTS.size());}
    @Test public void searchMatchesAllTokensCaseInsensitively(){
        assertEquals(java.util.Arrays.asList("headphones_wireless_001"),Catalog.search("  WIRELESS   headphones "));
    }
    @Test public void broadSearchHasDecoys(){assertEquals(2,Catalog.search("headphones").size());}
    @Test public void noResultsForUnknownItem(){assertTrue(Catalog.search("television").isEmpty());}
    @Test public void cannotAddWithoutSearch(){
        AppState s=state();assertThrows(IllegalStateException.class,()->s.add("headphones_wireless_001"));
        assertEquals(0,s.snapshot().get("total_quantity"));
    }
    @Test public void cannotAddUnmatchedItem(){
        AppState s=state();s.draft("bottle");s.search();
        assertThrows(IllegalStateException.class,()->s.add("headphones_wireless_001"));
    }
    @Test public void editingSearchInvalidatesResults(){
        AppState s=state();s.draft("headphones");s.search();s.draft("bottle");
        assertFalse(s.currentResults());assertThrows(IllegalStateException.class,()->s.add("headphones_wireless_001"));
    }
    @Test public void threeItemsHaveExactTotal(){
        AppState s=state();
        add(s,"wireless headphones","headphones_wireless_001");
        add(s,"steel water bottle","bottle_steel_001");
        add(s,"laptop backpack","backpack_laptop_001");s.openCart();
        assertEquals(3,s.snapshot().get("distinct_items"));assertEquals(3,s.snapshot().get("total_quantity"));
        assertEquals(499700L,s.snapshot().get("subtotal_paise"));assertEquals("CART",s.snapshot().get("screen"));
        assertEquals(3,((List<?>)s.snapshot().get("searches")).size());
        assertEquals(3,((List<?>)s.snapshot().get("additions")).size());
    }
    @Test public void duplicateAddIncrementsQuantityNotDistinctCount(){
        AppState s=state();add(s,"bottle","bottle_steel_001");s.add("bottle_steel_001");
        assertEquals(2,s.quantity("bottle_steel_001"));assertEquals(1,s.snapshot().get("distinct_items"));
    }
    @Test public void decreaseAndRemoveRecoverCart(){
        AppState s=state();add(s,"bottle","bottle_steel_001");s.add("bottle_steel_001");s.openCart();
        s.adjust("bottle_steel_001",-1);assertEquals(1,s.quantity("bottle_steel_001"));
        s.remove("bottle_steel_001");assertEquals(0,s.snapshot().get("total_quantity"));
    }
    @Test public void quantityIsBounded(){
        AppState s=state();add(s,"bottle","bottle_steel_001");s.openCart();
        for(int i=1;i<9;i++)s.adjust("bottle_steel_001",1);
        assertThrows(IllegalArgumentException.class,()->s.adjust("bottle_steel_001",1));
        assertEquals(9,s.quantity("bottle_steel_001"));
    }
    @Test public void zeroQuantityRemovesRow(){
        AppState s=state();add(s,"bottle","bottle_steel_001");s.openCart();s.adjust("bottle_steel_001",-1);
        assertEquals(0,s.snapshot().get("distinct_items"));
    }
    @Test public void restoreReplaysWithoutDuplicating(){
        AppState s=state();add(s,"headphones","headphones_wireless_001");s.openCart();s.adjust("headphones_wireless_001",1);
        AppState restored=AppState.restore(s.snapshot());
        assertEquals(s.snapshot(),restored.snapshot());assertEquals(2,restored.quantity("headphones_wireless_001"));
    }
    @Test public void corruptSubtotalIsRejected(){
        AppState s=state();Map<String,Object> saved=s.snapshot();saved.put("subtotal_paise",100);
        assertThrows(IllegalArgumentException.class,()->AppState.restore(saved));
    }
    @Test public void fractionalSavedTotalIsRejected(){
        AppState s=state();Map<String,Object> saved=s.snapshot();saved.put("subtotal_paise",0.5);
        assertThrows(IllegalArgumentException.class,()->AppState.restore(saved));
    }
    @Test public void wrongEpisodeCannotBeConstructed(){assertThrows(IllegalArgumentException.class,()->new AppState("../escape"));}
    @Test public void emptySearchRejected(){AppState s=state();assertThrows(IllegalStateException.class,s::search);}
}
