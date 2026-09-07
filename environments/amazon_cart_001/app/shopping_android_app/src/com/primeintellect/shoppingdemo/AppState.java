package com.primeintellect.shoppingdemo;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** UI-independent search and cart logic; no task-specific expected product set. */
public final class AppState {
    public final String episodeId;
    private String draft="",query="",screen="BROWSE";
    private long revision=0;
    private final LinkedHashMap<String,Integer> cart=new LinkedHashMap<>();
    private final List<Map<String,Object>> searches=new ArrayList<>(), additions=new ArrayList<>();
    private final List<Map<String,Object>> operations=new ArrayList<>();

    public AppState(String episodeId) {
        if (episodeId==null || !episodeId.matches("[A-Za-z0-9_-]{1,100}"))
            throw new IllegalArgumentException("Invalid episode ID");
        this.episodeId=episodeId;
    }
    public void draft(String value) {
        if (value==null || value.length()>80) throw new IllegalArgumentException("Search is limited to 80 characters");
        if (!draft.equals(value)) {
            draft=value; revision++;
            operation("draft", "text", value);
        }
    }
    public void search() {
        if (!screen.equals("BROWSE")) throw new IllegalStateException("Return to shopping before searching");
        if (Catalog.normalize(draft).length()<2) throw new IllegalStateException("Enter at least two characters to search");
        query=draft;
        Map<String,Object> search=new LinkedHashMap<>();
        search.put("search_id", searches.size()+1);
        search.put("query",query);
        search.put("result_skus",Catalog.search(query));
        searches.add(search); revision++;
        operation("search", "query", query);
    }
    public boolean currentResults() {
        return !searches.isEmpty() && draft.equals(query);
    }
    public boolean canAdd(String sku) {
        return screen.equals("BROWSE") && currentResults() && Catalog.search(query).contains(sku) && quantity(sku)<9;
    }
    public void add(String sku) {
        Catalog.get(sku);
        if (!canAdd(sku)) throw new IllegalStateException("Search for this product first, or use the cart to change its quantity");
        cart.put(sku,quantity(sku)+1);
        Map<String,Object> proof=new LinkedHashMap<>();
        proof.put("sku",sku); proof.put("search_id",searches.size());
        proof.put("query",query); proof.put("quantity_after",quantity(sku));
        additions.add(proof); revision++;
        operation("add","sku",sku);
    }
    public void openCart() {
        screen="CART";revision++;operation("cart",null,null);
    }
    public void browse() {
        screen="BROWSE";revision++;operation("browse",null,null);
    }
    public int quantity(String sku) { return cart.getOrDefault(sku,0); }
    public void adjust(String sku,int delta) {
        Catalog.get(sku);
        if (!screen.equals("CART") || !cart.containsKey(sku) || (delta!=-1 && delta!=1))
            throw new IllegalStateException("Use a current cart item's quantity controls");
        int next=quantity(sku)+delta;
        if (next<0 || next>9) throw new IllegalArgumentException("Quantity must be between 0 and 9");
        if (next==0) cart.remove(sku); else cart.put(sku,next);
        revision++;
        Map<String,Object> op=new LinkedHashMap<>();
        op.put("type","adjust");op.put("sku",sku);op.put("delta",delta);operations.add(op);
    }
    public void remove(String sku) {
        if (!screen.equals("CART") || !cart.containsKey(sku)) throw new IllegalStateException("Product is not in the cart");
        cart.remove(sku);revision++;operation("remove","sku",sku);
    }
    private void operation(String kind,String key,Object value) {
        Map<String,Object> op=new LinkedHashMap<>();op.put("type",kind);
        if (key!=null) op.put(key,value);
        operations.add(op);
    }
    public Map<String,Object> snapshot() {
        Map<String,Object> m=new LinkedHashMap<>();
        m.put("schema_version",1);m.put("episode_id",episodeId);m.put("simulated",true);
        m.put("currency","INR");m.put("screen",screen);m.put("draft_query",draft);m.put("query",query);
        m.put("results_current",currentResults());m.put("result_skus",currentResults()?Catalog.search(query):new ArrayList<String>());
        m.put("searches",deepList(searches));m.put("additions",deepList(additions));m.put("operations",deepList(operations));
        List<Map<String,Object>> items=new ArrayList<>();
        long subtotal=0;int units=0;
        for (Map.Entry<String,Integer> item:cart.entrySet()) {
            Map<String,Object> row=Catalog.get(item.getKey()).data();
            long total=Catalog.get(item.getKey()).pricePaise*item.getValue();
            row.put("quantity",item.getValue());row.put("line_total_paise",total);
            items.add(row);subtotal+=total;units+=item.getValue();
        }
        m.put("cart_items",items);m.put("distinct_items",cart.size());m.put("total_quantity",units);
        m.put("subtotal_paise",subtotal);m.put("revision",revision);
        return m;
    }
    @SuppressWarnings("unchecked")
    private static List<Map<String,Object>> deepList(List<Map<String,Object>> input) {
        List<Map<String,Object>> out=new ArrayList<>();
        for (Map<String,Object> row:input) {
            Map<String,Object> next=new LinkedHashMap<>(row);
            if (next.get("result_skus") instanceof List) next.put("result_skus",new ArrayList<>((List<String>)next.get("result_skus")));
            out.add(next);
        }
        return out;
    }
    /** Restore by replaying accepted operations and comparing all derived business fields. */
    @SuppressWarnings("unchecked")
    public static AppState restore(Map<String,Object> data) {
        if (!(data.get("schema_version") instanceof Number) || ((Number)data.get("schema_version")).intValue()!=1 ||
            !Boolean.TRUE.equals(data.get("simulated"))) throw new IllegalArgumentException("Incompatible saved state");
        AppState state=new AppState((String)data.get("episode_id"));
        for (Map<String,Object> op:(List<Map<String,Object>>)data.get("operations")) {
            switch((String)op.get("type")) {
                case "draft":state.draft((String)op.get("text"));break;
                case "search":
                    if (!state.draft.equals(op.get("query"))) throw new IllegalArgumentException("Search replay mismatch");
                    state.search();break;
                case "add":state.add((String)op.get("sku"));break;
                case "cart":state.openCart();break;
                case "browse":state.browse();break;
                case "adjust":state.adjust((String)op.get("sku"),((Number)op.get("delta")).intValue());break;
                case "remove":state.remove((String)op.get("sku"));break;
                default:throw new IllegalArgumentException("Unknown saved operation");
            }
        }
        for (Map.Entry<String,Object> entry:state.snapshot().entrySet())
            if (!equivalent(entry.getValue(),data.get(entry.getKey())))
                throw new IllegalArgumentException("Saved state mismatch: "+entry.getKey());
        return state;
    }
    @SuppressWarnings("unchecked")
    private static boolean equivalent(Object a,Object b) {
        if (a instanceof Number && b instanceof Number) return new java.math.BigDecimal(a.toString()).compareTo(new java.math.BigDecimal(b.toString()))==0;
        if (a instanceof Map && b instanceof Map) {
            Map<String,Object> x=(Map<String,Object>)a,y=(Map<String,Object>)b;
            if (!x.keySet().equals(y.keySet())) return false;
            for (String key:x.keySet()) if(!equivalent(x.get(key),y.get(key)))return false;
            return true;
        }
        if (a instanceof List && b instanceof List) {
            List<?> x=(List<?>)a,y=(List<?>)b;if(x.size()!=y.size())return false;
            for(int i=0;i<x.size();i++)if(!equivalent(x.get(i),y.get(i)))return false;
            return true;
        }
        return a==null?b==null:a.equals(b);
    }
}
