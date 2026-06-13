package com.primeintellect.dummyrl;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.Locale;

public class MainActivity extends Activity {
  private static final String PREFS = "dummy_state";

  private EditText searchInput;
  private EditText nameInput;
  private EditText emailInput;
  private EditText pickupInput;
  private EditText dropInput;
  private EditText couponInput;
  private TextView searchResult;
  private TextView statusText;
  private TextView finalStatusText;
  private TextView debugStateText;
  private String episodeId;
  private String selectedRide = "";
  private String payment = "";
  private String coupon = "";
  private int seed = 1001;
  private String startScreen = "home";
  private boolean randomizationEnabled = false;
  private boolean buttonTextVariant = false;
  private boolean fieldOrderVariant = false;
  private boolean themeVariant = false;
  private boolean startScreenVariant = false;
  private int networkDelayMinMs = 0;
  private int networkDelayMaxMs = 0;

  @Override
  protected void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    episodeId = clean(getIntent().getStringExtra("episode_id"));
    seed = parseIntExtra("seed", 1001);
    startScreen = clean(getIntent().getStringExtra("start_screen"));
    if (startScreen.length() == 0) {
      startScreen = "home";
    }
    randomizationEnabled = parseBooleanExtra("randomization_enabled");
    buttonTextVariant = parseBooleanExtra("button_text_variant");
    fieldOrderVariant = parseBooleanExtra("field_order_variant");
    themeVariant = parseBooleanExtra("theme_variant");
    startScreenVariant = parseBooleanExtra("start_screen_variant");
    networkDelayMinMs = parseIntExtra("network_delay_min_ms", 0);
    networkDelayMaxMs = parseIntExtra("network_delay_max_ms", 0);
    if (randomizationEnabled && startScreenVariant && seededBit(3)) {
      startScreen = "form";
    }

    LinearLayout root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(48, 64, 48, 48);
    root.setGravity(Gravity.CENTER_HORIZONTAL);
    applyThemeVariant(root);

    TextView title = new TextView(this);
    title.setText("Dummy RL App");
    title.setTextSize(28);
    title.setTextColor(Color.rgb(20, 20, 20));
    root.addView(title, matchWrap());

    TextView subtitle = new TextView(this);
    subtitle.setText("Search, fill the form, and submit.");
    subtitle.setTextSize(16);
    subtitle.setTextColor(Color.rgb(80, 80, 80));
    root.addView(subtitle, matchWrap());

    searchInput = new EditText(this);
    searchInput.setId(R.id.search_input);
    searchInput.setHint("Search task");
    searchInput.setSingleLine(true);
    root.addView(searchInput, matchWrap());

    Button searchButton = new Button(this);
    searchButton.setId(R.id.search_button);
    searchButton.setText(seededLabel("Search", "Find", buttonTextVariant, 0));
    root.addView(searchButton, matchWrap());

    searchResult = new TextView(this);
    searchResult.setId(R.id.search_result);
    searchResult.setText("Search result: none");
    searchResult.setTextSize(18);
    root.addView(searchResult, matchWrap());

    nameInput = new EditText(this);
    nameInput.setId(R.id.name_input);
    nameInput.setHint("Name");
    nameInput.setSingleLine(true);

    emailInput = new EditText(this);
    emailInput.setId(R.id.email_input);
    emailInput.setHint("Email");
    emailInput.setSingleLine(true);
    if (randomizationEnabled && fieldOrderVariant && seededBit(1)) {
      root.addView(emailInput, matchWrap());
      root.addView(nameInput, matchWrap());
    } else {
      root.addView(nameInput, matchWrap());
      root.addView(emailInput, matchWrap());
    }

    Button submitButton = new Button(this);
    submitButton.setId(R.id.submit_button);
    submitButton.setText(seededLabel("Submit Form", "Complete Form", buttonTextVariant, 2));
    root.addView(submitButton, matchWrap());

    Button clearButton = new Button(this);
    clearButton.setId(R.id.clear_button);
    clearButton.setText("Clear");
    root.addView(clearButton, matchWrap());

    statusText = new TextView(this);
    statusText.setId(R.id.status_text);
    statusText.setText("Status: waiting");
    statusText.setTextSize(18);
    root.addView(statusText, matchWrap());

    debugStateText = new TextView(this);
    debugStateText.setId(R.id.debug_state_text);
    debugStateText.setText("{}");
    debugStateText.setTextSize(10);
    root.addView(debugStateText, matchWrap());

    TextView rideTitle = new TextView(this);
    rideTitle.setText("Ride Booking Dummy App");
    rideTitle.setTextSize(24);
    rideTitle.setTextColor(Color.rgb(20, 20, 20));
    root.addView(rideTitle, matchWrap());

    pickupInput = new EditText(this);
    pickupInput.setId(R.id.pickup_input);
    pickupInput.setHint("Pickup");
    pickupInput.setSingleLine(true);
    root.addView(pickupInput, matchWrap());

    dropInput = new EditText(this);
    dropInput.setId(R.id.drop_input);
    dropInput.setHint("Drop");
    dropInput.setSingleLine(true);
    root.addView(dropInput, matchWrap());

    Button suggestion1 = new Button(this);
    suggestion1.setId(R.id.location_suggestion_1);
    suggestion1.setText("Use suggestion 1");
    root.addView(suggestion1, matchWrap());

    Button suggestion2 = new Button(this);
    suggestion2.setId(R.id.location_suggestion_2);
    suggestion2.setText("Use suggestion 2");
    root.addView(suggestion2, matchWrap());

    TextView cheapestBadge = new TextView(this);
    cheapestBadge.setId(R.id.cheapest_badge);
    cheapestBadge.setText("Cheapest: Mini");
    cheapestBadge.setTextSize(16);
    root.addView(cheapestBadge, matchWrap());

    Button miniButton = new Button(this);
    miniButton.setId(R.id.ride_option_mini);
    miniButton.setText("Mini");
    root.addView(miniButton, matchWrap());

    Button sedanButton = new Button(this);
    sedanButton.setId(R.id.ride_option_sedan);
    sedanButton.setText("Sedan");
    root.addView(sedanButton, matchWrap());

    Button premiumButton = new Button(this);
    premiumButton.setId(R.id.ride_option_premium);
    premiumButton.setText("Premium");
    root.addView(premiumButton, matchWrap());

    Button applyCouponButton = new Button(this);
    applyCouponButton.setId(R.id.apply_coupon_button);
    applyCouponButton.setText("Apply Coupon");
    root.addView(applyCouponButton, matchWrap());

    couponInput = new EditText(this);
    couponInput.setId(R.id.coupon_input);
    couponInput.setHint("Coupon");
    couponInput.setSingleLine(true);
    root.addView(couponInput, matchWrap());

    Button couponApplyButton = new Button(this);
    couponApplyButton.setId(R.id.coupon_apply_button);
    couponApplyButton.setText("Save Coupon");
    root.addView(couponApplyButton, matchWrap());

    Button cashButton = new Button(this);
    cashButton.setId(R.id.payment_cash);
    cashButton.setText("Cash");
    root.addView(cashButton, matchWrap());

    Button upiButton = new Button(this);
    upiButton.setId(R.id.payment_upi);
    upiButton.setText("UPI");
    root.addView(upiButton, matchWrap());

    Button confirmRideButton = new Button(this);
    confirmRideButton.setId(R.id.confirm_ride_button);
    confirmRideButton.setText("Confirm Ride");
    root.addView(confirmRideButton, matchWrap());

    Button cancelRideButton = new Button(this);
    cancelRideButton.setId(R.id.cancel_ride_button);
    cancelRideButton.setText("Cancel Ride");
    root.addView(cancelRideButton, matchWrap());

    finalStatusText = new TextView(this);
    finalStatusText.setId(R.id.final_status_text);
    finalStatusText.setText("Ride status: waiting");
    finalStatusText.setTextSize(18);
    root.addView(finalStatusText, matchWrap());

    searchButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        String query = clean(searchInput.getText().toString());
        searchResult.setText("Search result: " + query);
        simulateDelayIfNeeded();
        saveState(false);
        hideKeyboard();
      }
    });

    submitButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        String name = clean(nameInput.getText().toString());
        String email = clean(emailInput.getText().toString());
        simulateDelayIfNeeded();
        if (name.length() == 0 || email.length() == 0) {
          statusText.setText("Status: missing fields");
          saveState(false, "validation_error");
        } else {
          statusText.setText("Submitted: " + name + " <" + email + ">");
          saveState(true, "submitted");
        }
        hideKeyboard();
      }
    });

    clearButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        searchInput.setText("");
        nameInput.setText("");
        emailInput.setText("");
        searchResult.setText("Search result: none");
        statusText.setText("Status: waiting");
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().clear().apply();
        hideKeyboard();
      }
    });

    miniButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        selectedRide = "Mini";
        finalStatusText.setText("Ride selected: Mini");
        saveRideState(false, false, "ride_options");
      }
    });

    sedanButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        selectedRide = "Sedan";
        finalStatusText.setText("Ride selected: Sedan");
        saveRideState(false, false, "ride_options");
      }
    });

    premiumButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        selectedRide = "Premium";
        finalStatusText.setText("Ride selected: Premium");
        saveRideState(false, false, "ride_options");
      }
    });

    applyCouponButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        couponInput.requestFocus();
      }
    });

    couponApplyButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        coupon = clean(couponInput.getText().toString());
        finalStatusText.setText("Coupon saved: " + coupon);
        saveRideState(false, false, "coupon");
        hideKeyboard();
      }
    });

    cashButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        payment = "cash";
        finalStatusText.setText("Payment: cash");
        saveRideState(false, false, "payment");
      }
    });

    upiButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        payment = "upi";
        finalStatusText.setText("Payment: upi");
        saveRideState(false, false, "payment");
      }
    });

    confirmRideButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        String pickup = clean(pickupInput.getText().toString());
        String drop = clean(dropInput.getText().toString());
        if (pickup.length() == 0 || drop.length() == 0 || selectedRide.length() == 0) {
          finalStatusText.setText("Ride status: missing fields");
          saveRideState(false, false, "ride_validation_error");
        } else {
          finalStatusText.setText("Driver assigned: " + selectedRide);
          saveRideState(true, false, "driver_assigned");
        }
        hideKeyboard();
      }
    });

    cancelRideButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        finalStatusText.setText("Ride cancelled");
        saveRideState(false, true, "ride_cancelled");
      }
    });

    ScrollView scrollView = new ScrollView(this);
    scrollView.addView(root);
    setContentView(scrollView);
    saveState(false, startScreen);
  }

  private LinearLayout.LayoutParams matchWrap() {
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT);
    params.setMargins(0, 16, 0, 16);
    return params;
  }

  private String clean(String value) {
    return value == null ? "" : value.trim();
  }

  private void saveState(boolean submitted) {
    saveState(submitted, submitted ? "submitted" : "form");
  }

  private void saveState(boolean submitted, String screen) {
    long now = System.currentTimeMillis();
    SharedPreferences.Editor editor = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
    editor.putString("episode_id", episodeId);
    editor.putString("query", clean(searchInput.getText().toString()));
    editor.putString("name", clean(nameInput.getText().toString()));
    editor.putString("email", clean(emailInput.getText().toString()));
    editor.putBoolean("submitted", submitted);
    editor.putString("screen", screen);
    editor.putLong("updated_at_ms", now);
    editor.putInt("seed", seed);
    editor.apply();
    updateDebugState(
        screen,
        submitted,
        false,
        false,
        clean(searchInput.getText().toString()),
        clean(nameInput.getText().toString()),
        clean(emailInput.getText().toString()),
        clean(pickupInput == null ? "" : pickupInput.getText().toString()),
        clean(dropInput == null ? "" : dropInput.getText().toString()));
  }

  private void saveRideState(boolean confirmed, boolean cancelled, String screen) {
    long now = System.currentTimeMillis();
    SharedPreferences.Editor editor = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
    editor.putString("episode_id", episodeId);
    editor.putString("ride_pickup", clean(pickupInput.getText().toString()));
    editor.putString("ride_drop", clean(dropInput.getText().toString()));
    editor.putString("selected_ride", selectedRide);
    editor.putString("payment", payment);
    editor.putString("coupon", coupon);
    editor.putBoolean("ride_confirmed", confirmed);
    editor.putBoolean("ride_cancelled", cancelled);
    editor.putString("screen", screen);
    editor.putLong("updated_at_ms", now);
    editor.putInt("seed", seed);
    editor.apply();
    updateDebugState(
        screen,
        false,
        confirmed,
        cancelled,
        clean(searchInput.getText().toString()),
        clean(nameInput.getText().toString()),
        clean(emailInput.getText().toString()),
        clean(pickupInput.getText().toString()),
        clean(dropInput.getText().toString()));
  }

  private void hideKeyboard() {
    InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
    if (imm != null && getCurrentFocus() != null) {
      imm.hideSoftInputFromWindow(getCurrentFocus().getWindowToken(), 0);
    }
  }

  private void updateDebugState(
      String screen,
      boolean submitted,
      boolean rideConfirmed,
      boolean rideCancelled,
      String query,
      String name,
      String email,
      String pickup,
      String drop) {
    long updatedAtMs = System.currentTimeMillis();
    String debugState = String.format(
        Locale.US,
        "{\"coupon\":\"%s\",\"email\":\"%s\",\"episode_id\":\"%s\",\"name\":\"%s\",\"payment\":\"%s\",\"query\":\"%s\",\"ride_cancelled\":%s,\"ride_confirmed\":%s,\"ride_drop\":\"%s\",\"ride_pickup\":\"%s\",\"screen\":\"%s\",\"seed\":%d,\"selected_ride\":\"%s\",\"submitted\":%s,\"updated_at_ms\":%d}",
        escapeJson(coupon),
        escapeJson(email),
        escapeJson(episodeId),
        escapeJson(name),
        escapeJson(payment),
        escapeJson(query),
        rideCancelled ? "true" : "false",
        rideConfirmed ? "true" : "false",
        escapeJson(drop),
        escapeJson(pickup),
        escapeJson(screen),
        seed,
        escapeJson(selectedRide),
        submitted ? "true" : "false",
        updatedAtMs);
    debugStateText.setText(debugState);
  }

  private void simulateDelayIfNeeded() {
    if (!randomizationEnabled) {
      return;
    }
    int max = Math.max(networkDelayMinMs, networkDelayMaxMs);
    int min = Math.min(networkDelayMinMs, networkDelayMaxMs);
    if (max <= 0) {
      return;
    }
    int spread = Math.max(0, max - min);
    int delay = min + Math.abs(seed % (spread + 1));
    if (delay <= 0) {
      return;
    }
    try {
      Thread.sleep(delay);
    } catch (InterruptedException exc) {
      Thread.currentThread().interrupt();
    }
  }

  private void applyThemeVariant(LinearLayout root) {
    if (randomizationEnabled && themeVariant && seededBit(2)) {
      root.setBackgroundColor(Color.rgb(24, 28, 32));
    } else {
      root.setBackgroundColor(Color.WHITE);
    }
  }

  private String seededLabel(String primary, String alternate, boolean enabled, int salt) {
    if (randomizationEnabled && enabled && seededBit(salt)) {
      return alternate;
    }
    return primary;
  }

  private boolean seededBit(int salt) {
    return ((seed + salt) & 1) == 0;
  }

  private boolean parseBooleanExtra(String key) {
    return getIntent().getBooleanExtra(key, false);
  }

  private int parseIntExtra(String key, int defaultValue) {
    return getIntent().getIntExtra(key, defaultValue);
  }

  private String escapeJson(String value) {
    return clean(value).replace("\\", "\\\\").replace("\"", "\\\"");
  }
}
