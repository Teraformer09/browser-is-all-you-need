package com.primeintellect.amazonuidemo;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.provider.MediaStore;
import android.speech.RecognizerIntent;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.RelativeSizeSpan;
import android.text.style.StrikethroughSpan;
import android.text.style.SuperscriptSpan;
import android.view.GestureDetector;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.text.NumberFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Pure Android Java controller with read-only evaluation evidence. No cloud SDK or real checkout. */
public class MainActivity extends Activity {
    private static final int INK = 0xff0f1111, MUTED = 0xff565959, TEAL = 0xff007185;
    private static final int VOICE = 201, CAMERA = 202, SCAN = 203;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Deque<String> backStack = new ArrayDeque<>();
    private final List<View> tabs = new ArrayList<>();
    private final String[] tabKeys = {"home","you","wallet","cart","menu","assistant"};
    private final String[] tabNames = {"Home","You","Wallet","Cart","Menu","Rufus"};
    private Store db;
    private Store.Snapshot data;
    private LinearLayout body;
    private ScrollView scroll;
    private AutoCompleteTextView search;
    private TextView notice;
    private volatile boolean alive = true;
    private String page = "home", query = "", category = "", sort = "Featured";
    private int detailId = 1, banner = 0, noticeVersion = 0;
    private String assistantQuery = "";
    private Bitmap cameraPreview;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
            | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        setContentView(R.layout.main);
        View header = findViewById(R.id.header);
        header.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(0, insets.getSystemWindowInsetTop(), 0, 0);
            return insets;
        });
        header.requestApplyInsets();
        body = findViewById(R.id.body); scroll = findViewById(R.id.scroll);
        search = findViewById(R.id.etSearchBox); notice = findViewById(R.id.notice);
        db = new Store(getApplicationContext());
        if (saved != null) {
            page = saved.getString("page","home"); query = saved.getString("query","");
            category = saved.getString("category",""); sort = saved.getString("sort","Featured");
            detailId = saved.getInt("detail",1); banner = saved.getInt("banner",0);
            assistantQuery = saved.getString("assistant","");
            ArrayList<String> stack = saved.getStringArrayList("back");
            if (stack != null) backStack.addAll(stack);
        }
        final String evaluationId = getIntent().getStringExtra("episode_id");
        io.execute(() -> db.startEvaluation(evaluationId));
        setupQuickActions(); setupNavigation(); setupSearch();
        findViewById(R.id.btnDeliverLocation).setOnClickListener(v -> locationPicker());
        search.setText(query, false);
        body.addView(text("Loading your local store…",16,true));
        work(() -> {}, null, true);
    }

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private TextView text(String value, int size, boolean medium) {
        TextView t = new TextView(this); t.setText(value); t.setTextSize(size);
        t.setTextColor(INK); t.setIncludeFontPadding(false);
        if (medium) t.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        t.setPadding(dp(14),dp(7),dp(14),dp(7)); return t;
    }
    private GradientDrawable background(int color, int radius, int stroke) {
        GradientDrawable g = new GradientDrawable(); g.setColor(color); g.setCornerRadius(dp(radius));
        if (stroke != 0) g.setStroke(dp(1),stroke); return g;
    }
    private LinearLayout column() {
        LinearLayout l = new LinearLayout(this); l.setOrientation(LinearLayout.VERTICAL); return l;
    }
    private LinearLayout section() {
        LinearLayout l = column(); l.setBackgroundColor(Color.WHITE);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1,-2); p.bottomMargin = dp(8);
        l.setLayoutParams(p); l.setPadding(0,dp(6),0,dp(8)); body.addView(l); return l;
    }
    private Button button(String title, String description, boolean yellow, Runnable action) {
        Button b = new Button(this); b.setText(title); b.setAllCaps(false); b.setTextSize(13);
        b.setTextColor(INK); b.setStateListAnimator(null); b.setMinimumWidth(0); b.setMinimumHeight(0);
        b.setBackground(yellow ? getDrawable(R.drawable.btn_amazon_yellow) : background(Color.WHITE,24,0xffd5d9d9));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,dp(48));
        lp.setMargins(dp(14),dp(5),dp(14),dp(6)); b.setLayoutParams(lp);
        b.setContentDescription(description); b.setOnClickListener(v -> action.run()); return b;
    }
    private String money(long paise) {
        NumberFormat f = NumberFormat.getIntegerInstance(new Locale("en","IN"));
        return "₹" + f.format(paise / 100) + (paise % 100 == 0 ? "" : String.format(Locale.ROOT,".%02d",paise % 100));
    }
    private CharSequence styledPrice(long paise) {
        SpannableString s = new SpannableString(money(paise));
        s.setSpan(new RelativeSizeSpan(0.64f),0,1,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        s.setSpan(new SuperscriptSpan(),0,1,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE); return s;
    }
    private void announce(String message) {
        if (!alive) return;
        int version = ++noticeVersion; notice.setText(message); notice.setVisibility(View.VISIBLE);
        notice.postDelayed(() -> { if (alive && noticeVersion == version) notice.setVisibility(View.GONE); }, 3000);
    }
    private void work(Runnable operation, String success, boolean redraw) {
        io.execute(() -> {
            try {
                operation.run();
                Store.Snapshot snapshot = db.snapshot();
                runOnUiThread(() -> {
                    if (!alive) return;
                    data = snapshot; refreshChrome();
                    if (redraw || body.getChildCount() == 0) {
                        int oldY = scroll.getScrollY(); render();
                        scroll.post(() -> { if (alive) scroll.scrollTo(0,oldY); });
                    }
                    if (success != null) announce(success);
                });
            } catch (RuntimeException error) {
                android.util.Log.e("DemoCart","Local operation failed",error);
                runOnUiThread(() -> { if (alive) announce("Could not save: " + error.getMessage()); });
            }
        });
    }
    private String route() {
        return page + "|" + detailId + "|" + android.net.Uri.encode(category) + "|" + android.net.Uri.encode(query);
    }
    private void restoreRoute(String route) {
        String[] parts = route.split("\\|",-1);
        if (parts.length != 4) { page = "home"; return; }
        page = parts[0]; detailId = Integer.parseInt(parts[1]);
        category = android.net.Uri.decode(parts[2]); query = android.net.Uri.decode(parts[3]);
    }
    private void navigate(String target) {
        hideKeyboard();
        if (!page.equals(target)) backStack.push(route());
        page = target;
        if (target.equals("home")) { query = ""; category = ""; search.setText("",false); }
        render(); scroll.post(() -> scroll.scrollTo(0,0));
    }
    private void hideKeyboard() {
        search.dismissDropDown(); search.clearFocus();
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(search.getWindowToken(),0);
        findViewById(R.id.root).requestFocus();
    }

    private void setupQuickActions() {
        LinearLayout quick = findViewById(R.id.quickActions);
        String[] names = {"Pay","Fresh","Bazaar","Video","Pharma"};
        int[] icons = {R.drawable.ic_wallet,R.drawable.ic_fresh,R.drawable.ic_bag,R.drawable.ic_video,R.drawable.ic_pharma};
        int[] colors = {0xfff9df78,0xffe5eed7,0xffffddd4,0xffc3e5f6,0xffe4ddef};
        for (int i = 0; i < names.length; i++) {
            final int index = i;
            LinearLayout tile = column(); tile.setGravity(Gravity.CENTER);
            quick.addView(tile,new LinearLayout.LayoutParams(0,-1,1));
            ImageView icon = new ImageView(this); icon.setImageResource(icons[i]); icon.setPadding(dp(13),dp(8),dp(13),dp(8));
            icon.setBackground(background(colors[i],14,0));
            tile.addView(icon,new LinearLayout.LayoutParams(dp(52),dp(42)));
            TextView label = text(names[i],11,false); label.setPadding(0,dp(5),0,0); label.setGravity(Gravity.CENTER); tile.addView(label);
            tile.setContentDescription("Open " + names[i]); tile.setFocusable(true); tile.setClickable(true);
            tile.setOnClickListener(v -> {
                if (index == 0) openWallet();
                else if (index == 1) openCategory("Fresh");
                else if (index == 2) openCategory("Bazaar");
                else if (index == 3) navigate("video");
                else openCategory("Wellness");
            });
        }
    }
    private void setupNavigation() {
        int[] icons = {R.drawable.ic_home,R.drawable.ic_profile,R.drawable.ic_wallet,R.drawable.ic_cart,R.drawable.ic_menu_bars,R.drawable.ic_sparkle};
        LinearLayout nav = findViewById(R.id.bottomNav);
        for (int i = 0; i < tabKeys.length; i++) {
            final int index = i;
            View tab = getLayoutInflater().inflate(R.layout.item_nav,nav,false);
            ((ImageView)tab.findViewById(R.id.navIcon)).setImageResource(icons[i]);
            ((TextView)tab.findViewById(R.id.navLabel)).setText(tabNames[i]);
            tab.setContentDescription(tabNames[i]+" tab");
            tab.setOnClickListener(v -> { if(index == 2) openWallet(); else navigate(tabKeys[index]); });
            tabs.add(tab); nav.addView(tab);
        }
    }
    private void refreshChrome() {
        if (data == null) return;
        ((TextView)findViewById(R.id.tvDeliverTo)).setText("Deliver to " + data.profile + " · " + data.address);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,android.R.layout.simple_dropdown_item_1line,data.history);
        search.setAdapter(adapter);
        for(int i = 0; i < tabs.size(); i++) {
            View t = tabs.get(i); boolean active = page.equals(tabKeys[i]);
            t.setSelected(active); t.findViewById(R.id.navIndicator).setVisibility(active ? View.VISIBLE : View.INVISIBLE);
            ((ImageView)t.findViewById(R.id.navIcon)).setImageTintList(ColorStateList.valueOf(active ? TEAL : MUTED));
            ((TextView)t.findViewById(R.id.navLabel)).setTextColor(active ? TEAL : MUTED);
            TextView badge = t.findViewById(R.id.navBadge);
            if (i == 3) {
                badge.setText(data.count > 99 ? "99+" : String.valueOf(data.count));
                badge.setVisibility(data.count > 0 ? View.VISIBLE : View.GONE);
                t.setContentDescription("Cart tab, "+data.count+" items");
            } else if (i == 2) {
                badge.setText("•"); badge.setTextColor(0xffcc0c39); badge.setBackgroundColor(Color.TRANSPARENT);
                badge.setVisibility(data.walletSeen ? View.GONE : View.VISIBLE);
            }
        }
    }
    private void recordViewport() {
        final String shownPage=page, draft=search.getText().toString(), committed=query;
        io.execute(() -> db.viewport(shownPage,draft,committed));
    }
    private void setupSearch() {
        search.addTextChangedListener(new android.text.TextWatcher() {
            public void beforeTextChanged(CharSequence s,int start,int count,int after) {}
            public void onTextChanged(CharSequence s,int start,int before,int count) { recordViewport(); }
            public void afterTextChanged(android.text.Editable s) {}
        });
        search.setOnEditorActionListener((v, actionId, event) -> {
            if(actionId == EditorInfo.IME_ACTION_SEARCH ||
               (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER && event.getAction() == KeyEvent.ACTION_DOWN)) {
                executeSearch(search.getText().toString()); return true;
            }
            return false;
        });
        search.setOnItemClickListener((parent,v,pos,id) -> executeSearch(parent.getItemAtPosition(pos).toString()));
        search.setOnClickListener(v -> { if (data != null && !data.history.isEmpty()) search.showDropDown(); });
        search.setOnFocusChangeListener((v,focused) -> {
            if (focused && data != null && !data.history.isEmpty()) search.post(search::showDropDown);
        });
        findViewById(R.id.btnSearch).setOnClickListener(v -> executeSearch(search.getText().toString()));
        findViewById(R.id.btnLensSearch).setOnClickListener(v -> lensOptions());
        findViewById(R.id.btnVoiceSearch).setOnClickListener(v -> voiceSearch());
        findViewById(R.id.btnQrScanner).setOnClickListener(v -> barcodeOptions());
    }
    private void executeSearch(String value) {
        backStack.push(route()); query = value.trim(); category = ""; page = "results";
        search.setText(query,false); hideKeyboard(); render(); scroll.scrollTo(0,0);
        final String saved = query; work(() -> db.saveSearch(saved),null,false);
    }
    private void openCategory(String value) {
        backStack.push(route()); category = value; query = ""; page = "results";
        search.setText("",false); hideKeyboard(); render(); scroll.scrollTo(0,0);
    }
    private void openProduct(Store.Product product) {
        if (product == null) return;
        backStack.push(route()); detailId = product.id; page = "detail"; hideKeyboard(); render(); scroll.scrollTo(0,0);
        work(() -> db.viewed(product.id),null,false);
    }
    private void add(Store.Product product) {
        work(() -> db.add(product.id),"Added to cart · " + product.name,page.equals("cart"));
    }
    private List<Store.Product> filtered(String value, String filter) {
        List<Store.Product> result = new ArrayList<>();
        if (data == null) return result;
        String q = value.trim().toLowerCase(Locale.ROOT);
        for (Store.Product p : data.products) {
            boolean matches = q.isEmpty();
            if (!q.isEmpty()) {
                matches = true;
                for(String term : q.split("\\s+")) {
                    if (!(p.name+" "+p.category+" "+p.sku).toLowerCase(Locale.ROOT).contains(term)) { matches=false; break; }
                }
            }
            boolean categoryMatches = filter.isEmpty() || filter.equals("Deals") ||
                (filter.equals("Bazaar") ? p.price <= 99900 : p.category.equals(filter));
            if(matches && categoryMatches) result.add(p);
        }
        if(sort.equals("Price: low to high")) Collections.sort(result,Comparator.comparingLong(p -> p.price));
        if(sort.equals("Price: high to low")) Collections.sort(result,(a,b) -> Long.compare(b.price,a.price));
        return result;
    }

    private void render() {
        if (data == null) return;
        recordViewport();
        body.removeAllViews();
        findViewById(R.id.quickScroll).setVisibility(page.equals("home") ? View.VISIBLE : View.GONE);
        refreshChrome();
        switch(page) {
            case "home": home(); break;
            case "results": results(); break;
            case "detail": detail(); break;
            case "cart": cart(); break;
            case "you": profile(); break;
            case "wallet": wallet(); break;
            case "menu": menu(); break;
            case "assistant": assistant(); break;
            case "video": video(); break;
            default: page="home"; home();
        }
    }
    private void home() {
        FrameLayout promoHost = new FrameLayout(this);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2); lp.setMargins(dp(14),dp(6),dp(14),0);
        body.addView(promoHost,lp);
        LinearLayout dots = new LinearLayout(this); dots.setGravity(Gravity.CENTER);
        body.addView(dots,new LinearLayout.LayoutParams(-1,dp(34)));
        drawPromo(promoHost,dots);
        HorizontalScrollView categories = new HorizontalScrollView(this); categories.setHorizontalScrollBarEnabled(false);
        LinearLayout row = new LinearLayout(this); row.setPadding(dp(8),0,dp(8),0); row.setBackgroundColor(Color.WHITE);
        categories.addView(row); body.addView(categories);
        String[] names={"Deals","Electronics","Home","Travel","Fresh","Wellness"};
        int[] icons={R.drawable.ic_deal,R.drawable.ic_headphones,R.drawable.ic_home,R.drawable.ic_travel,R.drawable.ic_fresh,R.drawable.ic_pharma};
        for(int i=0;i<names.length;i++) {
            final String name=names[i];
            View tile=getLayoutInflater().inflate(R.layout.item_category_bubble,row,false);
            ((TextView)tile.findViewById(R.id.tvCategoryName)).setText(name);
            ((ImageView)tile.findViewById(R.id.ivCategoryIcon)).setImageResource(icons[i]);
            tile.setContentDescription("Shop "+name); tile.setOnClickListener(v -> openCategory(name)); row.addView(tile);
        }
        LinearLayout deals=section();
        LinearLayout heading=new LinearLayout(this); heading.setGravity(Gravity.CENTER_VERTICAL);
        TextView title=text("Deals inspired by your day",18,true); heading.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        TextView see=text("See all",12,true); see.setTextColor(TEAL); see.setMinHeight(dp(48)); see.setGravity(Gravity.CENTER);
        see.setContentDescription("See all deals"); see.setOnClickListener(v->openCategory("Deals")); heading.addView(see); deals.addView(heading);
        HorizontalScrollView scroller=new HorizontalScrollView(this); scroller.setHorizontalScrollBarEnabled(false);
        LinearLayout cards=new LinearLayout(this); cards.setPadding(dp(9),dp(2),dp(9),dp(8)); scroller.addView(cards);
        for(int id : new int[]{1,2,3,8}) cards.addView(dealCard(data.byId(id),cards));
        deals.addView(scroller);
        if(!data.viewed.isEmpty()) {
            LinearLayout viewed=section(); viewed.addView(text("Pick up where you left off",18,true));
            for(int id : data.viewed) {
                Store.Product p=data.byId(id);
                if(p!=null) viewed.addView(button(p.name,"View recently browsed "+p.name,false,()->openProduct(p)));
            }
        }
        TextView disclosure=text("DemoCart · Offline UI demo · No real orders or Amazon affiliation",10,false);
        disclosure.setTextColor(MUTED); body.addView(disclosure);
    }
    private void drawPromo(FrameLayout host, LinearLayout dots) {
        host.removeAllViews(); dots.removeAllViews();
        int[] ids={7,1,3}; Store.Product p=data.byId(ids[banner%3]);
        View card=getLayoutInflater().inflate(R.layout.promo_banner,host,false);
        String[] headlines={"40% off on\n55″ QLED","Sound that\nmoves with you","Made for your\neveryday journey"};
        String[] sub={"Bring every detail to life","Wireless freedom. Thoughtfully designed.","Carry more. Go further."};
        ((TextView)card.findViewById(R.id.promoTitle)).setText(headlines[banner%3]);
        ((TextView)card.findViewById(R.id.promoSubtitle)).setText(sub[banner%3]);
        ((TextView)card.findViewById(R.id.promoEyebrow)).setText(banner==0?"BIG-SCREEN MOMENTS":banner==1?"TUNE INTO SOMETHING GOOD":"YOUR NEXT ADVENTURE");
        ((TextView)card.findViewById(R.id.promoBrand)).setText(banner==0?"nimbus\nVISION":banner==1?"nimbus\nAUDIO":"metro\nEVERYDAY");
        ((FrameLayout)card.findViewById(R.id.promoArt)).addView(new ProductArt(this,p.kind),new FrameLayout.LayoutParams(-1,-1));
        host.addView(card);
        GestureDetector gesture=new GestureDetector(this,new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e){return true;}
            @Override public boolean onSingleTapUp(MotionEvent e){openProduct(p);return true;}
            @Override public boolean onFling(MotionEvent a,MotionEvent b,float vx,float vy){
                if(a==null || Math.abs(b.getX()-a.getX())<dp(30)) return false;
                banner=(banner+(b.getX()<a.getX()?1:2))%3; drawPromo(host,dots); return true;
            }
        });
        card.setContentDescription("Featured deal: "+p.name+"; tap for details, swipe for next offer");
        card.setFocusable(true); card.setOnClickListener(v->openProduct(p));
        card.setOnTouchListener((v,event)->gesture.onTouchEvent(event));
        for(int i=0;i<3;i++){
            final int selected=i; FrameLayout target=new FrameLayout(this);
            dots.addView(target,new LinearLayout.LayoutParams(dp(32),dp(32)));
            View dot=new View(this); dot.setBackground(background(i==banner?INK:0xffc7b6ad,5,0));
            FrameLayout.LayoutParams d=new FrameLayout.LayoutParams(dp(i==banner?16:6),dp(6),Gravity.CENTER); target.addView(dot,d);
            target.setContentDescription("Show promotion "+(i+1)); target.setFocusable(true); target.setOnClickListener(v->{banner=selected;drawPromo(host,dots);});
        }
    }
    private View dealCard(Store.Product p, ViewGroup parent) {
        View card=getLayoutInflater().inflate(R.layout.item_deal_card,parent,false);
        ((FrameLayout)card.findViewById(R.id.productArtSlot)).addView(new ProductArt(this,p.kind),new FrameLayout.LayoutParams(-1,-1));
        ((TextView)card.findViewById(R.id.tvDealTag)).setText(((p.mrp-p.price)*100/p.mrp)+"% off");
        ((TextView)card.findViewById(R.id.tvProductName)).setText(p.name);
        ((TextView)card.findViewById(R.id.tvPrice)).setText(styledPrice(p.price));
        TextView mrp=card.findViewById(R.id.tvOriginalPrice); mrp.setText(originalPrice(p.mrp));
        card.findViewById(R.id.productArtSlot).setContentDescription("View "+p.name);
        card.findViewById(R.id.productArtSlot).setOnClickListener(v->openProduct(p));
        card.findViewById(R.id.tvProductName).setOnClickListener(v->openProduct(p));
        Button add=card.findViewById(R.id.btnAddToCart); add.setContentDescription("Add "+p.name+" to cart");
        add.setOnClickListener(v->add(p)); return card;
    }
    private CharSequence originalPrice(long paise) {
        String value="M.R.P.: "+money(paise); SpannableString s=new SpannableString(value);
        s.setSpan(new StrikethroughSpan(),8,value.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE); return s;
    }
    private void results() {
        LinearLayout head=section();
        head.addView(text(category.isEmpty() ? (query.isEmpty()?"All products":"Results for “"+query+"”") : category,18,true));
        head.addView(button(sort+"  ▾","Sort products",false,()->new AlertDialog.Builder(this).setTitle("Sort results")
            .setItems(new String[]{"Featured","Price: low to high","Price: high to low"},(d,n)->{
                sort=new String[]{"Featured","Price: low to high","Price: high to low"}[n];render();
            }).show()));
        List<Store.Product> products=filtered(query,category);
        head.addView(text(products.size()+" local products · Demonstration prices",11,false));
        if(products.isEmpty()) {
            head.addView(text("No matches in the offline catalog.",18,true));
            head.addView(button("Browse all products","Clear filters",true,()->openCategory("")));
        }
        for(Store.Product p:products) productRow(p,false);
    }
    private void productRow(Store.Product p, boolean inCart) {
        LinearLayout card=section(); LinearLayout row=new LinearLayout(this);
        ProductArt art=new ProductArt(this,p.kind); art.setBackgroundColor(0xfff7f8fa);
        row.addView(art,new LinearLayout.LayoutParams(dp(126),dp(142)));
        LinearLayout info=column(); row.addView(info,new LinearLayout.LayoutParams(0,-2,1));
        info.addView(text(p.name,14,true));
        if(!inCart){TextView stars=text("★★★★☆  4.4 · Demo rating",10,false);stars.setTextColor(0xff996000);info.addView(stars);}
        TextView price=text("",22,true);price.setText(styledPrice(p.price));info.addView(price);
        TextView mrp=text("",10,false);mrp.setText(originalPrice(p.mrp));mrp.setTextColor(MUTED);info.addView(mrp);
        TextView stock=text("In stock · Offline catalog",11,false);stock.setTextColor(0xff007600);info.addView(stock);
        row.setContentDescription("View "+p.name); row.setOnClickListener(v->openProduct(p));card.addView(row);
        if(inCart) {
            LinearLayout controls=new LinearLayout(this);controls.setGravity(Gravity.CENTER_VERTICAL);
            Button minus=button("−","Decrease quantity of "+p.name,false,()->work(()->db.decrease(p.id),null,true));
            Button plus=button("+","Increase quantity of "+p.name,false,()->add(p));
            controls.addView(minus,new LinearLayout.LayoutParams(dp(48),dp(48)));
            TextView qty=text(String.valueOf(p.quantity),14,true);qty.setContentDescription("Quantity "+p.quantity+" for "+p.name);controls.addView(qty);
            controls.addView(plus,new LinearLayout.LayoutParams(dp(48),dp(48)));
            Button remove=button("Delete","Delete "+p.name,false,()->work(()->db.remove(p.id),"Removed "+p.name,true));
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(48),1);lp.setMargins(dp(14),0,dp(14),0);
            controls.addView(remove,lp);controls.setPadding(dp(14),dp(8),0,dp(4));card.addView(controls);
        } else card.addView(button("Add to cart","Add "+p.name+" to cart",true,()->add(p)));
    }
    private void detail() {
        Store.Product p=data.byId(detailId);
        if(p==null){body.addView(text("Product is unavailable",18,true));return;}
        LinearLayout s=section();TextView brand=text("Visit the "+p.name.split(" ")[0]+" demo store",12,false);brand.setTextColor(TEAL);s.addView(brand);
        s.addView(text(p.name,22,true));TextView stars=text("★★★★☆  4.4 · Illustrative rating",12,false);stars.setTextColor(0xff996000);s.addView(stars);
        s.addView(new ProductArt(this,p.kind),new LinearLayout.LayoutParams(-1,dp(240)));
        TextView price=text("",28,true);price.setText(styledPrice(p.price));s.addView(price);
        TextView mrp=text("",12,false);mrp.setText(originalPrice(p.mrp));mrp.setTextColor(MUTED);s.addView(mrp);
        s.addView(text(p.description,14,false));s.addView(text("Product code: "+p.sku+" · In stock",12,true));
        s.addView(button("Add to cart","Add "+p.name+" to cart",true,()->add(p)));
        s.addView(button("Go to cart","Go to cart",false,()->navigate("cart")));
    }
    private void cart() {
        LinearLayout top=section();top.addView(text("Subtotal ("+data.count+" items): "+money(data.total),22,true));
        top.addView(text("Your cart is saved on this device.",12,false));
        if(data.count>0) top.addView(button("Review demo cart ("+data.count+" items)","Review demo cart",true,()->{
            new AlertDialog.Builder(this).setTitle("Demo cart review")
                .setMessage(data.count+" items · "+money(data.total)+"\nDeliver to "+data.profile+", "+data.address+
                    "\n\nThis is an offline prototype. No order is placed and no money is charged.")
                .setPositiveButton("Keep shopping",(d,n)->navigate("home")).setNegativeButton("Back to cart",null).show();
        }));
        else {
            top.addView(text("Your cart is waiting for something good.",20,true));
            top.addView(button("Explore today's deals","Shop from empty cart",true,()->openCategory("Deals")));
        }
        for(Store.Product p:data.products) if(p.quantity>0) productRow(p,true);
    }

    private void locationPicker() {
        if(data==null)return;
        new AlertDialog.Builder(this).setTitle("Choose your delivery location")
            .setItems(new String[]{"Home · New Delhi 110001","Office · New Delhi 110002","Enter another PIN code"},(d,n)->{
                if(n<2) {String address=n==0?"New Delhi 110001":"New Delhi 110002";work(()->db.setting("address",address),"Delivery location updated",page.equals("you"));}
                else inputDialog("Enter a 6-digit demo PIN","110001",true,value->{
                    if(!value.matches("[1-9][0-9]{5}"))return "Enter a valid six-digit PIN";
                    work(()->db.setting("address","PIN "+value),"Delivery location updated",page.equals("you"));return null;
                });
            }).setNegativeButton("Cancel",null).show();
    }
    private interface InputAction { String submit(String value); }
    private void inputDialog(String title, String hint, boolean numeric, InputAction action) {
        EditText input=new EditText(this);input.setSingleLine(true);input.setHint(hint);
        input.setPadding(dp(18),dp(12),dp(18),dp(12));
        if(numeric)input.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        LinearLayout form=column(); form.addView(input);
        TextView validation=text("",12,false); validation.setTextColor(0xffb12704);
        validation.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        validation.setVisibility(View.GONE); form.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(title).setView(form)
            .setPositiveButton("Apply",null).setNegativeButton("Cancel",null).create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String error=action.submit(input.getText().toString().trim());
            if(error==null){((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(),0);dialog.dismiss();}
            else { validation.setText(error); validation.setVisibility(View.VISIBLE); input.requestFocus(); }
        }));dialog.show();
    }
    private void profile() {
        LinearLayout s=section();s.addView(text("Hello, "+data.profile,25,true));
        s.addView(text("Your local profile",12,false));
        s.addView(button("Edit display name","Edit display name",false,()->inputDialog("Demo display name","Your name",false,value->{
            if(value.isEmpty()||value.length()>30)return "Use 1–30 characters";
            work(()->db.setting("profile",value),"Profile saved",true);return null;
        })));
        s.addView(button("Delivery: "+data.address,"Edit saved delivery address",false,this::locationPicker));
        s.addView(text("No Amazon account is connected. Orders and sign-in are not part of this demo.",13,false));
        LinearLayout history=section();history.addView(text("Your recent searches",18,true));
        if(data.history.isEmpty())history.addView(text("Search for a product to start your history.",13,false));
        for(String q:data.history)history.addView(button(q,"Repeat search "+q,false,()->executeSearch(q)));
        if(!data.history.isEmpty())history.addView(button("Clear search history","Clear search history",false,()->work(db::clearHistory,"Search history cleared",true)));
    }
    private void openWallet() {
        navigate("wallet");work(()->db.setting("wallet_seen","true"),null,false);
    }
    private void wallet() {
        LinearLayout s=section();s.addView(text("Your demo wallet",25,true));s.addView(text("SIMULATED BALANCE",11,true));
        s.addView(text(money(data.wallet),34,true));s.addView(text("Demo credits only. Not money, UPI or an Amazon Pay account.",14,false));
        s.addView(button("Add ₹500 demo credits","Add 500 simulated wallet credits",true,()->work(db::topUp,"Added demo credits",true)));
        s.addView(button("Reset demo balance","Reset simulated wallet balance",false,()->work(()->db.setting("wallet_paise","125000"),"Demo balance reset",true)));
        s.addView(text("Balance is stored locally in SQLite. No bank connection or payment SDK.",12,false));
    }
    private void menu() {
        LinearLayout s=section();s.addView(text("Shop by category",23,true));
        for(String name:new String[]{"Deals","Electronics","Home","Travel","Fresh","Wellness","Bazaar"})
            s.addView(button(name+"  ›","Browse "+name,false,()->openCategory(name)));
        s.addView(button("Search by product code","Open product-code lookup",false,this::barcodeOptions));
        s.addView(button("About this demo","About DemoCart",false,()->new AlertDialog.Builder(this).setTitle("DemoCart 2.0")
            .setMessage("Pure Java + XML + SQLite. Independent offline UI prototype. No real Amazon services, ordering, medical advice or model calls.")
            .setPositiveButton("OK",null).show()));
    }
    private void assistant() {
        LinearLayout s=section();s.addView(text("Rufus · offline demo",23,true));
        s.addView(text("A local catalog helper, not Amazon's AI. Try “headphones”, “travel” or “under 1000”.",13,false));
        EditText ask=new EditText(this);ask.setSingleLine(true);ask.setHint("Ask about the demo catalog");
        ask.setText(assistantQuery);ask.setPadding(dp(14),dp(12),dp(14),dp(12));s.addView(ask);
        s.addView(button("Find products","Ask offline catalog helper",true,()->{
            assistantQuery=ask.getText().toString().trim();hideKeyboard();render();
        }));
        if(!assistantQuery.isEmpty()) {
            String q=assistantQuery.toLowerCase(Locale.ROOT);
            boolean budget=q.contains("1000")||q.contains("budget")||q.contains("cheap");
            String term=q.contains("headphone")?"headphones":q.contains("bottle")?"bottle":
                q.contains("backpack")?"backpack":q.contains("tv")?"tv":q.contains("travel")?"travel":q;
            List<Store.Product> suggestions=filtered(budget?"":term,budget?"Bazaar":"");
            s.addView(text(suggestions.isEmpty()?"I couldn't match that to the local catalog. Try a product type.":
                "Here are "+suggestions.size()+" matching demo products:",14,true));
            for(Store.Product p:suggestions)s.addView(button(p.name+" · "+money(p.price),"Assistant suggestion "+p.name,false,()->openProduct(p)));
        }
    }
    private void video() {
        LinearLayout s=section();s.addView(text("Product previews",24,true));
        s.addView(text("Local illustrated clips — not Prime Video or streaming.",13,false));
        s.addView(button("Play the QLED display preview","Play local display animation",true,()->{
            ProductArt art=new ProductArt(this,3);art.setMinimumHeight(dp(240));art.setAnimated(true);
            AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Demo display preview").setView(art)
                .setPositiveButton("View TV",(d,n)->openProduct(data.byId(7))).setNegativeButton("Close",null).create();
            dialog.setOnDismissListener(d->art.setAnimated(false));dialog.show();
        }));
    }

    private void voiceSearch() {
        new AlertDialog.Builder(this).setTitle("Voice search")
            .setMessage("Use your device's speech service? Offline recognition will be requested; availability and data handling depend on that service.")
            .setPositiveButton("Use device voice",(d,n)->{
                Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE,Locale.getDefault().toLanguageTag());
                intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE,true);
                intent.putExtra(RecognizerIntent.EXTRA_PROMPT,"Search the DemoCart catalog");
                if(!launch(intent,VOICE)) typedVoiceFallback();
            }).setNeutralButton("Type instead",(d,n)->typedVoiceFallback()).setNegativeButton("Cancel",null).show();
    }
    private void typedVoiceFallback() {
        inputDialog("Voice unavailable? Type your search","headphones",false,value->{
            if(value.isEmpty())return "Enter a product name";executeSearch(value);return null;
        });
    }
    private void lensOptions() {
        new AlertDialog.Builder(this).setTitle("Lens · local demo")
            .setMessage("Capture a photo, then choose its product category manually. This demo does not perform image recognition.")
            .setPositiveButton("Open camera",(d,n)->{
                if(!launch(new Intent(MediaStore.ACTION_IMAGE_CAPTURE),CAMERA)) manualLens();
            }).setNeutralButton("Choose category",(d,n)->manualLens()).setNegativeButton("Cancel",null).show();
    }
    private void manualLens() {
        new AlertDialog.Builder(this).setTitle("Match the photo manually")
            .setItems(new String[]{"Headphones","Water bottle","Backpack","Television"},(d,n)->executeSearch(new String[]{"headphones","bottle","backpack","TV"}[n]))
            .setNegativeButton("Cancel",null).show();
    }
    private void barcodeOptions() {
        new AlertDialog.Builder(this).setTitle("Find by product code")
            .setMessage("Use DC001–DC009 from product details. Camera scanning requires a compatible installed scanner; manual lookup always works.")
            .setPositiveButton("Enter code",(d,n)->manualCode())
            .setNeutralButton("Device scanner",(d,n)->{
                Intent scan=new Intent("com.google.zxing.client.android.SCAN");
                if(!launch(scan,SCAN))manualCode();
            }).setNegativeButton("Cancel",null).show();
    }
    private void manualCode() {
        inputDialog("Enter demo product code","DC001",false,value->{
            Store.Product found=productCode(value);
            if(found==null)return "Unknown demo code. Try DC001–DC009.";
            openProduct(found);return null;
        });
    }
    private Store.Product productCode(String code) {
        if(data==null)return null;
        for(Store.Product p:data.products)if(p.sku.equalsIgnoreCase(code.trim()))return p;
        return null;
    }
    private boolean launch(Intent intent,int request) {
        try { startActivityForResult(intent,request); return true; }
        catch(ActivityNotFoundException | SecurityException error) {
            announce("Device service unavailable. Use the local fallback."); return false;
        }
    }
    @Override protected void onActivityResult(int request,int result,Intent intent) {
        super.onActivityResult(request,result,intent);
        if(result!=RESULT_OK){announce("Cancelled. Nothing changed.");return;}
        if(request==VOICE){
            ArrayList<String> words=intent==null?null:intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if(words==null||words.isEmpty()||words.get(0).trim().isEmpty())typedVoiceFallback();
            else executeSearch(words.get(0));
        }else if(request==CAMERA){
            Object thumbnail=intent==null||intent.getExtras()==null?null:intent.getExtras().get("data");
            if(thumbnail instanceof Bitmap){
                cameraPreview=(Bitmap)thumbnail;
                ImageView image=new ImageView(this);image.setAdjustViewBounds(true);image.setImageBitmap(cameraPreview);
                new AlertDialog.Builder(this).setTitle("Captured photo · manual matching").setView(image)
                    .setPositiveButton("Choose category",(d,n)->manualLens()).setNegativeButton("Cancel",null).show();
            }else manualLens();
        }else if(request==SCAN){
            String code=intent==null?null:intent.getStringExtra("SCAN_RESULT");
            Store.Product p=code==null?null:productCode(code);
            if(p==null){announce("No matching local product code.");manualCode();}else openProduct(p);
        }
    }
    @Override public void onBackPressed() {
        if(!backStack.isEmpty()){restoreRoute(backStack.pop());search.setText(query,false);hideKeyboard();render();scroll.scrollTo(0,0);}
        else if(!page.equals("home")){page="home";render();}
        else super.onBackPressed();
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);state.putString("page",page);state.putString("query",query);
        state.putString("category",category);state.putString("sort",sort);state.putInt("detail",detailId);
        state.putInt("banner",banner);state.putString("assistant",assistantQuery);
        state.putStringArrayList("back",new ArrayList<>(backStack));
    }
    @Override protected void onDestroy() {
        alive=false;
        // Close after queued reads/writes, never while a worker owns a cursor.
        io.execute(db::close);io.shutdown();super.onDestroy();
    }
}

