package com.primeintellect.shoppingdemo;

import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;
import org.json.JSONObject;
import java.text.NumberFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class MainActivity extends AppCompatActivity {
    private static volatile MainActivity active;
    private AppState model;
    private StateStore store;
    private JSONObject persisted;
    private boolean storageFailed;
    private LinearLayout root,searchArea,products,cartRows,footer;
    private ScrollView browseScroll,cartScroll;
    private TextInputEditText input;
    private MaterialButton searchButton,cartButton;
    private TextView feedback,resultsTitle,cartTitle,total;
    private static final int INK=Color.rgb(19,25,33), TEAL=Color.rgb(0,113,133), MUTED=Color.rgb(86,101,115);
    private int dp(float value) { return Math.round(value*getResources().getDisplayMetrics().density); }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        active=this;
        store=new StateStore(this);
        try {
            model=store.load(getIntent().getStringExtra("episode_id"));
            persisted=store.save(model,"open",true,"");
            buildUi();
            render("");
        } catch(Exception error) {
            storageFailed=true;
            TextView notice=new TextView(this);
            notice.setText("DemoCart state is unavailable. Start a new explicit demo episode.");
            notice.setPadding(dp(24),dp(48),dp(24),dp(24));
            setContentView(notice);
        }
    }
    private LinearLayout vertical() {
        LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;
    }
    private TextView text(String value,int size,int color,boolean bold) {
        TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);
        if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return t;
    }
    private MaterialButton button(String label,int id) {
        MaterialButton b=new MaterialButton(this);b.setId(id);b.setText(label);b.setAllCaps(false);
        b.setTextSize(14);b.setCornerRadius(dp(20));b.setInsetTop(0);b.setInsetBottom(0);
        b.setMinWidth(0);b.setMinimumWidth(0);b.setMinHeight(0);b.setMinimumHeight(0);
        b.setPadding(dp(12),0,dp(12),0);b.setSingleLine(true);b.setGravity(Gravity.CENTER);
        return b;
    }
    private LinearLayout.LayoutParams lp(int w,int h) { return new LinearLayout.LayoutParams(w<0?w:dp(w),h<0?h:dp(h)); }
    private void buildUi() {
        root=vertical();root.setBackgroundColor(Color.rgb(234,237,237));root.setFocusableInTouchMode(true);
        setContentView(root);
        LinearLayout nav=new LinearLayout(this);nav.setGravity(Gravity.CENTER_VERTICAL);
        nav.setPadding(dp(16),dp(10),dp(16),dp(10));nav.setBackgroundColor(INK);
        LinearLayout brand=vertical();
        TextView logo=text("democart",29,Color.WHITE,true);logo.setId(R.id.brand_text);
        TextView sub=text("AMAZON-STYLE • OFFLINE DEMO",9,Color.rgb(255,216,20),false);
        sub.setLetterSpacing(0.08f);brand.addView(logo);brand.addView(sub);
        nav.addView(brand,new LinearLayout.LayoutParams(0,dp(60),1));
        cartButton=button("Cart · 0",R.id.cart_button);cartButton.setTextColor(Color.WHITE);
        cartButton.setBackgroundTintList(ColorStateList.valueOf(Color.rgb(35,47,62)));
        cartButton.setStrokeColor(ColorStateList.valueOf(Color.rgb(82,99,113)));cartButton.setStrokeWidth(dp(1));
        cartButton.setOnClickListener(v->act("open_cart",()->model.openCart()));
        nav.addView(cartButton,lp(105,44));root.addView(nav,lp(-1,80));

        searchArea=vertical();searchArea.setBackgroundColor(Color.rgb(35,47,62));
        searchArea.setPadding(dp(16),0,dp(16),dp(8));
        LinearLayout row=new LinearLayout(this);row.setGravity(Gravity.CENTER_VERTICAL);
        TextInputLayout box=new TextInputLayout(this);box.setBoxBackgroundMode(TextInputLayout.BOX_BACKGROUND_OUTLINE);
        box.setBoxBackgroundColor(Color.WHITE);box.setBoxCornerRadii(dp(10),dp(10),dp(10),dp(10));
        box.setHint("Search DemoCart");box.setDefaultHintTextColor(ColorStateList.valueOf(MUTED));
        GradientDrawable searchSurface=new GradientDrawable();searchSurface.setColor(Color.WHITE);
        searchSurface.setCornerRadius(dp(10));box.setBackground(searchSurface);
        input=new TextInputEditText(this);input.setId(R.id.search_input);input.setSingleLine(true);
        input.setBackground(null);input.setTextColor(INK);input.setTextSize(16);input.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        input.setPadding(dp(12),dp(12),dp(12),dp(12));
        input.setText((String)model.snapshot().get("draft_query"));
        box.addView(input,new LinearLayout.LayoutParams(-1,-1));
        row.addView(box,new LinearLayout.LayoutParams(0,dp(60),1));
        searchButton=button("Search",R.id.search_button);
        LinearLayout.LayoutParams go=lp(88,48);go.setMargins(dp(8),dp(5),0,0);
        row.addView(searchButton,go);searchArea.addView(row,lp(-1,65));
        feedback=text("Search the catalog, then add your picks.",12,Color.rgb(226,234,239),false);
        feedback.setId(R.id.feedback_text);feedback.setPadding(0,dp(6),0,dp(2));searchArea.addView(feedback);
        root.addView(searchArea,lp(-1,-2));
        searchButton.setOnClickListener(v->search());
        input.setOnEditorActionListener((v,action,event)-> { if(action==EditorInfo.IME_ACTION_SEARCH){search();return true;}return false; });
        input.addTextChangedListener(new TextWatcher(){
            public void beforeTextChanged(CharSequence s,int start,int count,int after){}
            public void onTextChanged(CharSequence s,int start,int before,int count){}
            public void afterTextChanged(Editable value){act("edit_query",()->model.draft(value.toString()));}
        });

        browseScroll=new ScrollView(this);browseScroll.setId(R.id.catalog_scroll);browseScroll.setFillViewport(true);
        LinearLayout browse=vertical();browse.setPadding(dp(16),dp(18),dp(16),dp(18));
        resultsTitle=text("",23,INK,true);resultsTitle.setId(R.id.results_title);browse.addView(resultsTitle);
        TextView categories=text("ELECTRONICS   /   OUTDOORS   /   BAGS",10,TEAL,true);
        categories.setPadding(0,dp(7),0,dp(15));browse.addView(categories);
        products=vertical();products.setId(R.id.results_list);browse.addView(products);
        browseScroll.addView(browse);root.addView(browseScroll,new LinearLayout.LayoutParams(-1,0,1));

        cartScroll=new ScrollView(this);cartScroll.setId(R.id.cart_scroll);cartScroll.setFillViewport(true);
        LinearLayout cart=vertical();cart.setPadding(dp(16),dp(18),dp(16),dp(12));
        cartTitle=text("",25,INK,true);cartTitle.setId(R.id.cart_title);cart.addView(cartTitle);
        TextView local=text("Saved on this device. Nothing has been ordered.",12,MUTED,false);
        local.setPadding(0,dp(5),0,dp(16));cart.addView(local);
        cartRows=vertical();cartRows.setId(R.id.cart_list);cart.addView(cartRows);
        MaterialButton keep=button("Continue shopping",R.id.continue_shopping_button);
        keep.setBackgroundTintList(ColorStateList.valueOf(Color.WHITE));keep.setStrokeWidth(dp(1));
        keep.setStrokeColor(ColorStateList.valueOf(Color.LTGRAY));keep.setTextColor(TEAL);
        keep.setOnClickListener(v->act("continue_shopping",()->model.browse()));
        LinearLayout.LayoutParams keepParams=lp(-1,44);keepParams.setMargins(0,dp(10),0,0);
        cart.addView(keep,keepParams);cartScroll.addView(cart);root.addView(cartScroll,new LinearLayout.LayoutParams(-1,0,1));

        footer=vertical();footer.setBackgroundColor(Color.WHITE);footer.setPadding(dp(20),dp(14),dp(20),dp(14));
        total=text("",22,INK,true);total.setId(R.id.cart_subtotal);footer.addView(total);
        TextView noOrder=text("SIMULATION ONLY  •  Checkout is not available",11,TEAL,true);
        noOrder.setPadding(0,dp(5),0,0);footer.addView(noOrder);root.addView(footer,lp(-1,-2));
        root.requestFocus();
    }
    private void search() {
        act("search",()->model.search());
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(),0);
        input.clearFocus();root.requestFocus();browseScroll.smoothScrollTo(0,0);
    }
    private void act(String action,Runnable change) {
        if(storageFailed)return;
        boolean accepted=true;String error="";
        try{change.run();}catch(IllegalArgumentException|IllegalStateException ex){accepted=false;error=ex.getMessage();}
        try{persisted=store.save(model,action,accepted,error);}
        catch(Exception ex){storageFailed=true;error="Local storage failed; this episode cannot be verified.";}
        render(error);
    }
    private String money(long paise) {
        return NumberFormat.getCurrencyInstance(new Locale("en","IN")).format(paise/100.0);
    }
    private int id(String name) {
        int value=getResources().getIdentifier(name,"id",getPackageName());
        if(value==0)throw new IllegalArgumentException("Missing stable UI ID: "+name);
        return value;
    }
    private int illustration(Catalog.Product p) {
        return p.sku.startsWith("headphones")?R.drawable.product_headphones:p.sku.startsWith("bottle")?R.drawable.product_bottle:R.drawable.product_backpack;
    }
    private MaterialCardView productCard(Catalog.Product p,boolean inCart) {
        MaterialCardView card=new MaterialCardView(this);card.setId(id((inCart?"cart_":"product_")+p.sku));
        card.setRadius(dp(12));card.setCardElevation(0);card.setStrokeWidth(dp(1));
        card.setStrokeColor(Color.rgb(218,225,229));card.setCardBackgroundColor(Color.WHITE);
        LinearLayout inside=vertical();inside.setPadding(dp(12),dp(12),dp(12),dp(12));
        LinearLayout row=new LinearLayout(this);row.setGravity(Gravity.CENTER_VERTICAL);
        ImageView image=new ImageView(this);image.setImageResource(illustration(p));image.setContentDescription(p.category+" product illustration");
        image.setPadding(dp(8),dp(8),dp(8),dp(8));image.setBackgroundColor(Color.rgb(244,247,248));
        row.addView(image,lp(72,82));
        LinearLayout description=vertical();description.setPadding(dp(13),0,0,0);
        TextView title=text(p.name,16,INK,true);title.setId(id("title_"+p.sku));description.addView(title);
        TextView details=text(p.detail.replace(" | "," · "),11,MUTED,false);details.setPadding(0,dp(4),0,dp(4));description.addView(details);
        description.addView(text(money(p.pricePaise),21,INK,true));
        row.addView(description,new LinearLayout.LayoutParams(0,-2,1));inside.addView(row,lp(-1,-2));
        if(inCart) {
            LinearLayout controls=new LinearLayout(this);controls.setGravity(Gravity.CENTER_VERTICAL);
            MaterialButton minus=button("−",id("decrease_"+p.sku));
            minus.setOnClickListener(v->act("decrease_quantity",()->model.adjust(p.sku,-1)));
            MaterialButton plus=button("+",id("increase_"+p.sku));plus.setEnabled(model.quantity(p.sku)<9);
            plus.setOnClickListener(v->act("increase_quantity",()->model.adjust(p.sku,1)));
            TextView quantity=text(String.valueOf(model.quantity(p.sku)),17,INK,true);quantity.setId(id("quantity_"+p.sku));quantity.setGravity(Gravity.CENTER);
            minus.setContentDescription("Decrease quantity of "+p.name);plus.setContentDescription("Increase quantity of "+p.name);
            controls.addView(minus,lp(48,48));controls.addView(quantity,lp(35,48));controls.addView(plus,lp(48,48));
            View spacer=new View(this);controls.addView(spacer,new LinearLayout.LayoutParams(0,1,1));
            MaterialButton remove=button("Remove",id("remove_"+p.sku));
            remove.setBackgroundTintList(ColorStateList.valueOf(Color.WHITE));remove.setTextColor(TEAL);
            remove.setOnClickListener(v->act("remove_item",()->model.remove(p.sku)));
            controls.addView(remove,lp(90,48));
            LinearLayout.LayoutParams cp=lp(-1,48);cp.setMargins(0,dp(12),0,0);inside.addView(controls,cp);
        } else {
            MaterialButton add=button(model.quantity(p.sku)>0?"Add another · "+model.quantity(p.sku)+" in cart":"Add to cart",id("add_"+p.sku));
            add.setEnabled(model.canAdd(p.sku)&&!storageFailed);
            add.setOnClickListener(v->act("add_to_cart",()->model.add(p.sku)));
            LinearLayout.LayoutParams bp=lp(-1,39);bp.setMargins(0,dp(12),0,0);inside.addView(add,bp);
        }
        card.addView(inside);
        LinearLayout.LayoutParams margin=lp(-1,-2);margin.setMargins(0,0,0,dp(12));card.setLayoutParams(margin);
        return card;
    }
    @SuppressWarnings("unchecked")
    private void render(String error) {
        Map<String,Object> state=model.snapshot();
        boolean cart="CART".equals(state.get("screen"));
        cartButton.setText("Cart · "+state.get("total_quantity"));cartButton.setEnabled(!storageFailed);
        searchArea.setVisibility(cart?View.GONE:View.VISIBLE);
        browseScroll.setVisibility(cart?View.GONE:View.VISIBLE);cartScroll.setVisibility(cart?View.VISIBLE:View.GONE);
        footer.setVisibility(cart?View.VISIBLE:View.GONE);
        input.setEnabled(!storageFailed);searchButton.setEnabled(!storageFailed&&Catalog.normalize(input.getText().toString()).length()>=2);
        feedback.setText(!error.isEmpty()?error:model.currentResults()?"Local results · No purchase or checkout":"Search the catalog, then add your picks.");
        products.removeAllViews();
        if(model.currentResults()){
            List<String> results=(List<String>)state.get("result_skus");
            resultsTitle.setText(results.size()+" result"+(results.size()==1?"":"s"));
            for(String sku:results)products.addView(productCard(Catalog.get(sku),false));
            if(results.isEmpty()){
                TextView empty=text("No matches found.\nTry a product name, such as headphones, bottle or backpack.",17,MUTED,false);
                empty.setId(R.id.empty_results);empty.setPadding(0,dp(20),0,0);products.addView(empty);
            }
        } else if(((String)state.get("draft_query")).isEmpty()) {
            resultsTitle.setText("Everyday finds");
            for(Catalog.Product p:Catalog.PRODUCTS)products.addView(productCard(p,false));
        } else {
            resultsTitle.setText("Ready to search?");
            products.addView(text("Tap Search to see matching products.\nYour current cart is kept.",16,MUTED,false));
        }
        cartTitle.setText("Your cart ("+state.get("total_quantity")+")");
        cartRows.removeAllViews();
        List<Map<String,Object>> items=(List<Map<String,Object>>)state.get("cart_items");
        if(items.isEmpty()){
            TextView empty=text("Your cart is empty.\nSearch the demo catalog to add something.",18,MUTED,false);
            empty.setId(R.id.empty_cart);empty.setPadding(0,dp(30),0,dp(30));cartRows.addView(empty);
        }
        for(Map<String,Object> item:items)cartRows.addView(productCard(Catalog.get((String)item.get("sku")),true));
        total.setText("Subtotal ("+state.get("total_quantity")+" items): "+money(((Number)state.get("subtotal_paise")).longValue()));
        if(storageFailed){cartRows.setVisibility(View.GONE);products.setVisibility(View.GONE);}
    }
    public static String verifierSnapshot(){
        MainActivity a=active;
        if(a==null||a.model==null||a.storageFailed||a.persisted==null)throw new IllegalStateException("Live shopping state unavailable");
        try{
            JSONObject result=new JSONObject(a.model.snapshot());
            result.put("events",a.persisted.getJSONArray("events"));
            result.put("last_action",a.persisted.getString("last_action"));
            result.put("last_action_accepted",a.persisted.getBoolean("last_action_accepted"));
            result.put("last_error",a.persisted.getString("last_error"));
            return result.toString();
        }catch(Exception ex){throw new IllegalStateException(ex);}
    }
    @Override protected void onDestroy(){if(active==this)active=null;super.onDestroy();}
}
