package com.primeintellect.shoppingdemo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Fixed, offline demo merchandise. These are not Amazon listings or real offers. */
public final class Catalog {
    public static final class Product {
        public final String sku, name, detail, category;
        public final long pricePaise;
        Product(String sku, String name, String detail, String category, long price) {
            this.sku=sku; this.name=name; this.detail=detail; this.category=category; pricePaise=price;
        }
        public Map<String,Object> data() {
            Map<String,Object> m=new LinkedHashMap<>();
            m.put("sku",sku); m.put("name",name); m.put("detail",detail);
            m.put("category",category); m.put("unit_price_paise",pricePaise);
            return m;
        }
    }
    public static final List<Product> PRODUCTS;
    static {
        List<Product> p=new ArrayList<>();
        p.add(new Product("headphones_wireless_001","Nimbus Wireless Headphones","Over-ear | Bluetooth | Midnight black","Electronics",249900));
        p.add(new Product("headphones_wired_001","Nimbus Wired Headphones","Over-ear | 3.5 mm cable | Graphite","Electronics",79900));
        p.add(new Product("bottle_steel_001","Trail Steel Water Bottle","1 litre | Stainless steel | Ocean blue","Outdoors",69900));
        p.add(new Product("bottle_sport_001","Trail Sports Water Bottle","750 ml | Lightweight | Mint","Outdoors",39900));
        p.add(new Product("backpack_laptop_001","Metro Laptop Backpack","15.6 inch | Padded sleeve | Navy","Bags",179900));
        p.add(new Product("backpack_daypack_001","Metro Everyday Daypack","12 litre | Compact | Stone","Bags",89900));
        PRODUCTS=Collections.unmodifiableList(p);
    }
    public static Product get(String sku) {
        for (Product p:PRODUCTS) if (p.sku.equals(sku)) return p;
        throw new IllegalArgumentException("Unknown product");
    }
    public static String normalize(String value) {
        return value.trim().toLowerCase(Locale.ROOT).replaceAll("\\s+"," ");
    }
    public static List<String> search(String query) {
        String clean=normalize(query);
        List<String> found=new ArrayList<>();
        if (clean.length()<2) return found;
        for (Product p:PRODUCTS) {
            String haystack=(p.name+" "+p.detail+" "+p.category).toLowerCase(Locale.ROOT);
            boolean match=true;
            for (String token:clean.split(" ")) if (!haystack.contains(token)) match=false;
            if (match) found.add(p.sku);
        }
        return found;
    }
    private Catalog() { }
}
