package com.primeintellect.dummyrl;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.FrameLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.Locale;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

public class MainActivity extends Activity {
  private static final String PREFS = "dummy_state";
  private static volatile MainActivity verifierActivity;
  private JSONObject previousMutationState;

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
  private TextView rideProgressText;
  private TextView routeSummaryText;
  private TextView cabHeader;
  private LinearLayout cabRow;
  private TextView paymentHeader;
  private LinearLayout paymentRow;
  private LinearLayout actionRow;
  private TextView rideDebugStateText;
  private String episodeId;
  private String rideType = "";
  private String selectedRide = "";
  private String payment = "";
  private String coupon = "";
  private int rideStage = 0;
  private int rideActionSequence = 0;
  private boolean lastRideActionAccepted = true;
  private String lastRideAction = "reset";
  private String lastRideActionError = "";
  private boolean rideSequenceError = false;
  private boolean rideConfirmed = false;
  private boolean rideCancelled = false;
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
    if ("ride".equals(startScreen)) {
      root.setBackgroundColor(Color.rgb(14, 14, 14));
    }

    TextView title = new TextView(this);
    title.setText("ride".equals(startScreen) ? "Uber" : "Dummy RL App");
    title.setTextSize(28);
    title.setTextColor(Color.rgb(20, 20, 20));
    root.addView(title, matchWrap());

    TextView subtitle = new TextView(this);
    subtitle.setText("ride".equals(startScreen) ? "Where to?" : "Search, fill the form, and submit.");
    subtitle.setTextSize(16);
    subtitle.setTextColor(Color.rgb(80, 80, 80));
    root.addView(subtitle, matchWrap());
    if ("ride".equals(startScreen)) {
      title.setVisibility(View.GONE);
      subtitle.setVisibility(View.GONE);
    }

    if (!"ride".equals(startScreen)) {
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

    }

    View mapPanel = new UberMapBackdropView(this);
    LinearLayout.LayoutParams mapParams = new LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        340);
    root.addView(mapPanel, mapParams);

    LinearLayout rideSheet = new LinearLayout(this);
    rideSheet.setOrientation(LinearLayout.VERTICAL);
    rideSheet.setPadding(20, 14, 20, 18);
    rideSheet.setBackgroundDrawable(roundedDrawable(Color.WHITE, Color.TRANSPARENT, 28, 0));
    rideSheet.setBackgroundColor(Color.WHITE);
    LinearLayout.LayoutParams sheetParams = new LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT);
    root.addView(rideSheet, sheetParams);

    TextView rideTitle = new TextView(this);
    rideTitle.setText("Where to?");
    rideTitle.setTextSize(26);
    rideTitle.setTextColor(Color.rgb(18, 18, 18));
    rideTitle.setVisibility(View.VISIBLE);
    rideSheet.addView(rideTitle, matchWrap());

    TextView rideSubtitle = new TextView(this);
    rideSubtitle.setText("Current location");
    rideSubtitle.setTextSize(14);
    rideSubtitle.setTextColor(Color.rgb(110, 110, 110));
    rideSubtitle.setVisibility(View.VISIBLE);
    rideSheet.addView(rideSubtitle, matchWrap());

    View sheetHandle = new View(this);
    LinearLayout.LayoutParams handleParams = new LinearLayout.LayoutParams(dp(72), dp(6));
    handleParams.gravity = Gravity.CENTER_HORIZONTAL;
    sheetHandle.setBackgroundDrawable(roundedDrawable(Color.rgb(218, 218, 218), Color.TRANSPARENT, 12, 0));
    rideSheet.addView(sheetHandle, handleParams);

    LinearLayout tabsRow = new LinearLayout(this);
    tabsRow.setOrientation(LinearLayout.HORIZONTAL);
    TextView ridesTab = new TextView(this);
    ridesTab.setText("Rides");
    ridesTab.setTextColor(Color.WHITE);
    ridesTab.setPadding(dp(16), dp(10), dp(16), dp(10));
    ridesTab.setBackgroundDrawable(roundedDrawable(Color.rgb(18, 18, 18), Color.rgb(18, 18, 18), 20, 0));
    tabsRow.addView(ridesTab);
    TextView eatsTab = new TextView(this);
    eatsTab.setText("Eats");
    eatsTab.setTextColor(Color.rgb(40, 40, 40));
    eatsTab.setPadding(dp(16), dp(10), dp(16), dp(10));
    eatsTab.setBackgroundDrawable(roundedDrawable(Color.rgb(244, 244, 244), Color.rgb(235, 235, 235), 20, 1));
    tabsRow.addView(eatsTab, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
    TextView shopsTab = new TextView(this);
    shopsTab.setText("Shops");
    shopsTab.setTextColor(Color.rgb(40, 40, 40));
    shopsTab.setPadding(dp(16), dp(10), dp(16), dp(10));
    shopsTab.setBackgroundDrawable(roundedDrawable(Color.rgb(244, 244, 244), Color.rgb(235, 235, 235), 20, 1));
    tabsRow.addView(shopsTab, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
    TextView courierTab = new TextView(this);
    courierTab.setText("Courier");
    courierTab.setTextColor(Color.rgb(40, 40, 40));
    courierTab.setPadding(dp(16), dp(10), dp(16), dp(10));
    courierTab.setBackgroundDrawable(roundedDrawable(Color.rgb(244, 244, 244), Color.rgb(235, 235, 235), 20, 1));
    tabsRow.addView(courierTab, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
    rideSheet.addView(tabsRow, matchWrap());

    rideProgressText = new TextView(this);
    rideProgressText.setId(R.id.ride_progress_text);
    rideProgressText.setText("Plan your trip");
    rideProgressText.setTextSize(12);
    rideProgressText.setTextColor(Color.rgb(110, 110, 110));
    rideProgressText.setVisibility(View.VISIBLE);
    rideSheet.addView(rideProgressText, matchWrap());

    pickupInput = new EditText(this);
    pickupInput.setId(R.id.pickup_input);
    pickupInput.setHint("Current location");
    pickupInput.setBackgroundDrawable(roundedDrawable(Color.rgb(244, 244, 244), Color.rgb(228, 228, 228), 20, 1));
    pickupInput.setPadding(24, 20, 24, 20);
    pickupInput.setSingleLine(true);
    rideSheet.addView(pickupInput, matchWrap());

    TextView savedPlacesLabel = new TextView(this);
    savedPlacesLabel.setText("Saved places");
    savedPlacesLabel.setTextSize(16);
    savedPlacesLabel.setTextColor(Color.rgb(20, 20, 20));
    rideSheet.addView(savedPlacesLabel, matchWrap());

    TextView rideTypeLabel = new TextView(this);
    rideTypeLabel.setText("Ride type");
    rideTypeLabel.setTextSize(16);
    rideTypeLabel.setTextColor(Color.rgb(20, 20, 20));
    rideTypeLabel.setVisibility(View.GONE);
    rideSheet.addView(rideTypeLabel, matchWrap());

    LinearLayout rideTypeRow = new LinearLayout(this);
    rideTypeRow.setOrientation(LinearLayout.HORIZONTAL);
    Button rideTypeRideButton = new Button(this);
    rideTypeRideButton.setId(R.id.ride_type_ride);
    rideTypeRideButton.setText("Ride");
    rideTypeRideButton.setAllCaps(false);
    applyPillStyle(rideTypeRideButton, false);
    rideTypeRow.addView(rideTypeRideButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button rideTypeReserveButton = new Button(this);
    rideTypeReserveButton.setId(R.id.ride_type_reserve);
    rideTypeReserveButton.setText("Reserve");
    rideTypeReserveButton.setAllCaps(false);
    applyPillStyle(rideTypeReserveButton, false);
    rideTypeRow.addView(rideTypeReserveButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button rideTypePremiumButton = new Button(this);
    rideTypePremiumButton.setId(R.id.ride_type_premium);
    rideTypePremiumButton.setText("Premium");
    rideTypePremiumButton.setAllCaps(false);
    applyPillStyle(rideTypePremiumButton, false);
    rideTypeRow.addView(rideTypePremiumButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    rideSheet.addView(rideTypeRow, matchWrap());

    dropInput = new EditText(this);
    dropInput.setId(R.id.drop_input);
    dropInput.setHint("Where to?");
    dropInput.setBackgroundDrawable(roundedDrawable(Color.WHITE, Color.rgb(216, 216, 216), 20, 1));
    dropInput.setPadding(24, 22, 24, 22);
    dropInput.setSingleLine(true);
    rideSheet.addView(dropInput, matchWrap());

    Button destinationSearchButton = new Button(this);
    destinationSearchButton.setId(R.id.destination_search_button);
    destinationSearchButton.setText("Now");
    destinationSearchButton.setEnabled(false);
    destinationSearchButton.setAllCaps(false);
    applyDarkActionStyle(destinationSearchButton);
    rideSheet.addView(destinationSearchButton, matchWrap());

    LinearLayout suggestionRow = new LinearLayout(this);
    suggestionRow.setOrientation(LinearLayout.HORIZONTAL);
    Button suggestion1 = new Button(this);
    suggestion1.setId(R.id.location_suggestion_1);
    suggestion1.setText("Home");
    suggestion1.setAllCaps(false);
    applyPillStyle(suggestion1, false);
    suggestion1.setTextAlignment(View.TEXT_ALIGNMENT_TEXT_START);
    suggestionRow.addView(suggestion1, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button suggestion2 = new Button(this);
    suggestion2.setId(R.id.location_suggestion_2);
    suggestion2.setText("Work");
    suggestion2.setAllCaps(false);
    applyPillStyle(suggestion2, false);
    suggestion2.setTextAlignment(View.TEXT_ALIGNMENT_TEXT_START);
    suggestionRow.addView(suggestion2, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    rideSheet.addView(suggestionRow, matchWrap());

    View sectionSpacer = new View(this);
    rideSheet.addView(sectionSpacer, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(160)));

    routeSummaryText = new TextView(this);
    routeSummaryText.setId(R.id.route_summary_text);
    routeSummaryText.setText("Pickup: Current location | Ride: not set | Destination: not set | Cab: not set | Payment: not set");
    routeSummaryText.setTextSize(12);
    routeSummaryText.setTextColor(Color.rgb(50, 50, 50));
    routeSummaryText.setBackgroundColor(Color.rgb(245, 245, 245));
    routeSummaryText.setPadding(16, 16, 16, 16);
    routeSummaryText.setVisibility(View.GONE);
    rideSheet.addView(routeSummaryText, matchWrap());

    cabHeader = new TextView(this);
    cabHeader.setText("Choose your ride");
    cabHeader.setTextSize(16);
    cabHeader.setTextColor(Color.rgb(20, 20, 20));
    cabHeader.setVisibility(View.GONE);
    rideSheet.addView(cabHeader, matchWrap());

    cabRow = new LinearLayout(this);
    cabRow.setOrientation(LinearLayout.HORIZONTAL);
    Button miniButton = new Button(this);
    miniButton.setId(R.id.ride_option_mini);
    miniButton.setText("Mini");
    miniButton.setAllCaps(false);
    applyPillStyle(miniButton, false);
    cabRow.addView(miniButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button sedanButton = new Button(this);
    sedanButton.setId(R.id.ride_option_sedan);
    sedanButton.setText("Sedan");
    sedanButton.setAllCaps(false);
    applyPillStyle(sedanButton, false);
    cabRow.addView(sedanButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button premiumButton = new Button(this);
    premiumButton.setId(R.id.ride_option_premium);
    premiumButton.setText("Premium");
    premiumButton.setAllCaps(false);
    applyPillStyle(premiumButton, false);
    cabRow.addView(premiumButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    cabHeader.setVisibility(View.GONE);
    cabRow.setVisibility(View.GONE);
    rideSheet.addView(cabRow, matchWrap());

    paymentHeader = new TextView(this);
    paymentHeader.setText("Payment method");
    paymentHeader.setTextSize(16);
    paymentHeader.setTextColor(Color.rgb(20, 20, 20));
    paymentHeader.setVisibility(View.GONE);
    rideSheet.addView(paymentHeader, matchWrap());

    paymentRow = new LinearLayout(this);
    paymentRow.setOrientation(LinearLayout.HORIZONTAL);
    Button cashButton = new Button(this);
    cashButton.setId(R.id.payment_cash);
    cashButton.setText("Cash");
    cashButton.setAllCaps(false);
    applyPillStyle(cashButton, false);
    paymentRow.addView(cashButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button cardButton = new Button(this);
    cardButton.setId(R.id.payment_card);
    cardButton.setText("Card");
    cardButton.setAllCaps(false);
    applyPillStyle(cardButton, false);
    paymentRow.addView(cardButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button upiButton = new Button(this);
    upiButton.setId(R.id.payment_upi);
    upiButton.setText("UPI");
    upiButton.setAllCaps(false);
    applyPillStyle(upiButton, false);
    paymentRow.addView(upiButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    paymentRow.setVisibility(View.GONE);
    rideSheet.addView(paymentRow, matchWrap());

    actionRow = new LinearLayout(this);
    actionRow.setOrientation(LinearLayout.HORIZONTAL);
    Button confirmRideButton = new Button(this);
    confirmRideButton.setId(R.id.confirm_ride_button);
    confirmRideButton.setText("Book ride");
    confirmRideButton.setAllCaps(false);
    applyDarkActionStyle(confirmRideButton);
    actionRow.addView(confirmRideButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    Button cancelRideButton = new Button(this);
    cancelRideButton.setId(R.id.cancel_ride_button);
    cancelRideButton.setText("Cancel");
    cancelRideButton.setAllCaps(false);
    applyPillStyle(cancelRideButton, false);
    actionRow.addView(cancelRideButton, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
    actionRow.setVisibility(View.GONE);
    rideSheet.addView(actionRow, matchWrap());

    finalStatusText = new TextView(this);
    finalStatusText.setId(R.id.final_status_text);
    finalStatusText.setText("Enter pickup and choose a ride type.");
    finalStatusText.setTextSize(14);
    finalStatusText.setTextColor(Color.rgb(40, 40, 40));
    finalStatusText.setBackgroundColor(Color.rgb(245, 245, 245));
    finalStatusText.setPadding(16, 16, 16, 16);
    rideSheet.addView(finalStatusText, matchWrap());

    rideDebugStateText = new TextView(this);
    rideDebugStateText.setId(R.id.ride_debug_state_text);
    rideDebugStateText.setText("{}");
    rideDebugStateText.setTextSize(10);
    rideDebugStateText.setTextColor(Color.rgb(120, 120, 120));
    rideDebugStateText.setVisibility(View.GONE);
    rideSheet.addView(rideDebugStateText, matchWrap());

    rideTypeRideButton.setOnClickListener(rideAction("ride_type", "Ride"));
    rideTypeReserveButton.setOnClickListener(rideAction("ride_type", "Reserve"));
    rideTypePremiumButton.setOnClickListener(rideAction("ride_type", "Premium"));
    destinationSearchButton.setOnClickListener(rideAction("destination", ""));
    suggestion1.setOnClickListener(rideAction("destination", "Airport"));
    suggestion2.setOnClickListener(rideAction("destination", "City Center"));
    miniButton.setOnClickListener(rideAction("cab", "Mini"));
    sedanButton.setOnClickListener(rideAction("cab", "Sedan"));
    premiumButton.setOnClickListener(rideAction("cab", "Premium"));
    cashButton.setOnClickListener(rideAction("payment", "cash"));
    cardButton.setOnClickListener(rideAction("payment", "card"));
    upiButton.setOnClickListener(rideAction("payment", "upi"));
    confirmRideButton.setOnClickListener(rideAction("booking", ""));
    cancelRideButton.setOnClickListener(rideAction("cancel", ""));
    pickupInput.addTextChangedListener(rideInputWatcher(false));
    dropInput.addTextChangedListener(rideInputWatcher(true));

    updateRideSummary();
    if ("ride".equals(startScreen)) {
      ScrollView scrollView = new ScrollView(this);
      scrollView.addView(root);
      setContentView(scrollView);
    } else {
      ScrollView scrollView = new ScrollView(this);
      scrollView.addView(root);
      setContentView(scrollView);
    }
    updateRideSummary(); // Controls are now attached: enforce initial enabled states.
    if ("ride".equals(startScreen)) {
      saveRideState(false, false, "ride");
      verifierActivity = this;
      appendRideMutation(true);
    } else {
      saveState(false, startScreen);
    }
  }

  private LinearLayout.LayoutParams matchWrap() {
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT);
    params.setMargins(0, 4, 0, 4);
    return params;
  }

  private String clean(String value) {
    return value == null ? "" : value.trim();
  }

  private String displayValue(String value, String fallback) {
    return value == null || value.trim().isEmpty() ? fallback : value.trim();
  }

  private void saveState(boolean submitted) {
    saveState(submitted, submitted ? "submitted" : "form");
  }

  private void saveState(boolean submitted, String screen) {
    long now = System.currentTimeMillis();
    SharedPreferences.Editor editor = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
    editor.putString("episode_id", episodeId);
    editor.putString("query", fieldText(searchInput));
    editor.putString("name", fieldText(nameInput));
    editor.putString("email", fieldText(emailInput));
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
        fieldText(searchInput),
        fieldText(nameInput),
        fieldText(emailInput),
        fieldText(pickupInput),
        fieldText(dropInput));
  }

  private void saveRideState(boolean confirmed, boolean cancelled, String screen) {
    long now = System.currentTimeMillis();
    SharedPreferences.Editor editor = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
    editor.putString("episode_id", episodeId);
    editor.putString("ride_pickup", fieldText(pickupInput));
    editor.putString("pickup_location", fieldText(pickupInput));
    editor.putString("ride_type", clean(rideType));
    editor.putString("ride_drop", fieldText(dropInput));
    editor.putString("destination_query", fieldText(dropInput));
    editor.putString("selected_ride", clean(selectedRide));
    editor.putString("selected_cab_type", clean(selectedRide));
    editor.putString("payment", clean(payment));
    editor.putString("payment_type", clean(payment));
    editor.putString("coupon", coupon);
    editor.putInt("journey_stage", rideStage);
    editor.putInt("ride_action_sequence", rideActionSequence);
    editor.putBoolean("last_action_accepted", lastRideActionAccepted);
    editor.putString("last_action_name", lastRideAction);
    editor.putString("last_action_error", lastRideActionError);
    editor.putBoolean("sequence_error", rideSequenceError);
    editor.putBoolean("ride_confirmed", confirmed);
    editor.putBoolean("ride_cancelled", cancelled);
    editor.putString("screen", screen);
    editor.putLong("updated_at_ms", now);
    editor.putInt("seed", seed);
    editor.commit(); // Small controlled state: persist before reporting acceptance.
    rideConfirmed = confirmed;
    rideCancelled = cancelled;
    updateDebugState(
        screen,
        false,
        confirmed,
        cancelled,
        fieldText(searchInput),
        fieldText(nameInput),
        fieldText(emailInput),
        fieldText(pickupInput),
        fieldText(dropInput));
  }

  private void updateRideSummary() {
    View search = findViewById(R.id.destination_search_button);
    boolean canSearch = rideStage >= 1 && clean(rideType).length() > 0 && fieldText(dropInput).length() > 0;
    if (search != null) {
      search.setEnabled(canSearch);
      search.setAlpha(canSearch ? 1.0f : 0.4f);
    }
    int[] suggestions = {R.id.location_suggestion_1, R.id.location_suggestion_2};
    for (int id : suggestions) {
      View suggestion = findViewById(id);
      if (suggestion != null) {
        suggestion.setEnabled(rideStage >= 1);
        suggestion.setAlpha(rideStage >= 1 ? 1.0f : 0.4f);
      }
    }
    int[] selectionIds = {R.id.ride_type_ride, R.id.ride_type_reserve, R.id.ride_type_premium,
        R.id.ride_option_mini, R.id.ride_option_sedan, R.id.ride_option_premium,
        R.id.payment_cash, R.id.payment_card, R.id.payment_upi};
    String[] selectionValues = {"Ride", "Reserve", "Premium", "Mini", "Sedan", "Premium", "cash", "card", "upi"};
    for (int i = 0; i < selectionIds.length; i++) {
      Button button = (Button)findViewById(selectionIds[i]);
      String selected = i < 3 ? rideType : (i < 6 ? selectedRide : payment);
      if (button != null) { applyPillStyle(button, selectionValues[i].equals(selected)); }
    }
    if (routeSummaryText != null) { routeSummaryText.setVisibility(rideStage >= 2 ? View.VISIBLE : View.GONE); }
    if (cabHeader != null) { cabHeader.setVisibility(rideStage >= 2 ? View.VISIBLE : View.GONE); }
    if (cabRow != null) { cabRow.setVisibility(rideStage >= 2 ? View.VISIBLE : View.GONE); }
    if (paymentHeader != null) { paymentHeader.setVisibility(rideStage >= 3 ? View.VISIBLE : View.GONE); }
    if (paymentRow != null) { paymentRow.setVisibility(rideStage >= 3 ? View.VISIBLE : View.GONE); }
    if (actionRow != null) {
      actionRow.setVisibility(rideStage >= 4 ? View.VISIBLE : View.GONE);
      actionRow.getChildAt(0).setEnabled(rideStage == 4 && fieldText(pickupInput).length() > 0);
      actionRow.getChildAt(1).setVisibility(rideConfirmed ? View.VISIBLE : View.GONE);
    }
    if (rideProgressText != null) {
      rideProgressText.setText(String.format(Locale.US, "Booking step %d/5 • Pickup: %s", rideStage, fieldText(pickupInput).length() > 0 ? "set" : "not set"));
    }
    if (routeSummaryText != null) {
      routeSummaryText.setText(String.format(
          Locale.US,
          "Pickup: %s | Ride: %s | Destination: %s | Cab: %s | Payment: %s",
          displayValue(pickupInput == null ? "" : pickupInput.getText().toString(), "Current location"),
          displayValue(rideType, "not set"),
          displayValue(dropInput == null ? "" : dropInput.getText().toString(), "not set"),
          displayValue(selectedRide, "not set"),
          displayValue(payment, "not set")));
    }
    if (rideDebugStateText != null) {
      rideDebugStateText.setText(String.format(
          Locale.US,
          "{\"ride_type\":\"%s\",\"destination\":\"%s\",\"cab_type\":\"%s\",\"payment\":\"%s\",\"stage\":%d,\"sequence_error\":%s}",
          escapeJson(rideType),
          escapeJson(clean(dropInput == null ? "" : dropInput.getText().toString())),
          escapeJson(selectedRide),
          escapeJson(payment),
          rideStage,
          rideSequenceError ? "true" : "false"));
    }
  }

  // Called only by the permission-protected, read-only verifier provider.
  public static String verifierSnapshot() {
    MainActivity activity = verifierActivity;
    if (activity == null) { throw new IllegalStateException("No active ride episode"); }
    return activity.rideSnapshot().toString();
  }

  private JSONObject rideSnapshot() {
    try {
      JSONObject state = new JSONObject();
      state.put("contract_version", "uber031-evidence-v1");
      state.put("episode_id", episodeId);
      state.put("ride_action_sequence", Integer.toString(rideActionSequence));
      state.put("ride_pickup", fieldText(pickupInput));
      state.put("ride_type", rideType);
      state.put("ride_drop", fieldText(dropInput));
      state.put("selected_ride", selectedRide);
      state.put("payment", payment);
      state.put("journey_stage", Integer.toString(rideStage));
      state.put("ride_confirmed", Boolean.toString(rideConfirmed));
      state.put("ride_cancelled", Boolean.toString(rideCancelled));
      state.put("sequence_error", Boolean.toString(rideSequenceError));
      state.put("screen", currentRideScreen());
      return state;
    } catch (Exception error) { throw new IllegalStateException(error); }
  }

  private void appendRideMutation(boolean initial) {
    try {
      JSONObject state = rideSnapshot();
      JSONObject event = new JSONObject();
      event.put("episode_id", episodeId);
      event.put("seq", rideActionSequence);
      event.put("initial", initial);
      event.put("action", lastRideAction);
      event.put("accepted", lastRideActionAccepted);
      event.put("reason", lastRideActionError);
      event.put("before", initial ? JSONObject.NULL : previousMutationState);
      event.put("state", state);
      event.put("time_ms", System.currentTimeMillis());
      FileOutputStream stream = openFileOutput("ride_mutations.jsonl", initial ? MODE_PRIVATE : MODE_APPEND);
      try {
        stream.write((event.toString() + "\n").getBytes(StandardCharsets.UTF_8));
        stream.getFD().sync();
      } finally { stream.close(); }
      previousMutationState = state;
    } catch (Exception error) {
      // Never fabricate a complete log when a write failed.
      getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("mutation_log_error", error.toString()).commit();
    }
  }

  @Override protected void onDestroy() {
    if (verifierActivity == this) { verifierActivity = null; }
    super.onDestroy();
  }

  private String currentRideScreen() {
    if (rideCancelled) { return "ride_cancelled"; }
    if (rideConfirmed) { return "ride_booked"; }
    String[] screens = {"ride", "ride_type", "destination", "cab_type", "payment"};
    return screens[Math.min(rideStage, 4)];
  }

  private void recordRideAction(String action, boolean accepted, String message) {
    rideActionSequence++;
    lastRideAction = action;
    lastRideActionAccepted = accepted;
    lastRideActionError = accepted ? "" : message;
    // A rejected action is recoverable; it never poisons subsequent transitions.
    rideSequenceError = false;
    finalStatusText.setText(accepted ? message : "Action rejected: " + message);
    saveRideState(rideConfirmed, rideCancelled, currentRideScreen());
    updateRideSummary();
    appendRideMutation(false);
  }

  private TextWatcher rideInputWatcher(final boolean destination) {
    return new TextWatcher() {
      public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
      public void onTextChanged(CharSequence s, int start, int before, int count) {}
      public void afterTextChanged(Editable text) {
        // Editing an upstream value invalidates only its dependent selections.
        if (destination && rideStage >= 2) {
          rideStage = rideType.length() == 0 ? 0 : 1;
          selectedRide = "";
          payment = "";
        } else if (!destination && rideStage == 5) {
          rideStage = 4;
        }
        rideConfirmed = false;
        rideCancelled = false;
        recordRideAction(destination ? "destination_input" : "pickup_input", true,
            destination ? (rideStage >= 1 ? "Destination updated; tap Now to search." : "Destination entered; choose a ride type before searching.") : "Pickup updated.");
      }
    };
  }

  private View.OnClickListener rideAction(final String action, final String value) {
    return new View.OnClickListener() {
      public void onClick(View view) {
        if ("ride_type".equals(action)) {
          rideType = value;
          rideStage = 1;
          selectedRide = "";
          payment = "";
          rideConfirmed = false;
          rideCancelled = false;
          recordRideAction(action, true, "Ride type selected: " + value + ". Search the destination next.");
        } else if ("destination".equals(action)) {
          if (value.length() > 0) { dropInput.setText(value); }
          destinationChosenFromInput();
        } else if ("cab".equals(action)) {
          if (rideStage < 2) {
            recordRideAction(action, false, "Search a destination before choosing a cab.");
            return;
          }
          selectedRide = value;
          payment = "";
          rideStage = 3;
          rideConfirmed = false;
          rideCancelled = false;
          recordRideAction(action, true, "Cab selected: " + value + ". Choose payment next.");
        } else if ("payment".equals(action)) {
          // Validate before touching payment or completion state.
          if (rideStage < 3 || selectedRide.length() == 0) {
            recordRideAction(action, false, "Choose a cab before selecting payment.");
            return;
          }
          payment = value;
          rideStage = 4;
          rideConfirmed = false;
          rideCancelled = false;
          recordRideAction(action, true, "Payment selected: " + value + ". Book the ride next.");
        } else if ("booking".equals(action)) {
          if (rideStage != 4 || fieldText(pickupInput).length() == 0
              || fieldText(dropInput).length() == 0 || selectedRide.length() == 0 || payment.length() == 0) {
            recordRideAction(action, false, "Set pickup, ride type, destination, cab and payment before booking.");
            return;
          }
          rideStage = 5;
          rideConfirmed = true;
          rideCancelled = false;
          recordRideAction(action, true, "Ride booked: " + selectedRide + " to " + fieldText(dropInput));
          hideKeyboard();
        } else if ("cancel".equals(action)) {
          if (!rideConfirmed) {
            recordRideAction(action, false, "There is no confirmed booking to cancel.");
            return;
          }
          rideConfirmed = false;
          rideCancelled = true;
          recordRideAction(action, true, "Ride cancelled.");
        }
      }
    };
  }

  private void destinationChosenFromInput() {
    if (rideStage < 1 || rideType.length() == 0) {
      recordRideAction("destination", false, "Choose a ride type before searching the destination.");
      return;
    }
    String destination = fieldText(dropInput);
    if (destination.length() == 0) {
      recordRideAction("destination", false, "Enter a destination before searching.");
      return;
    }
    rideStage = 2;
    selectedRide = "";
    payment = "";
    rideConfirmed = false;
    rideCancelled = false;
    recordRideAction("destination", true, "Destination selected: " + destination + ". Choose a cab next.");
  }

  private String fieldText(EditText input) {
    return input == null ? "" : clean(input.getText().toString());
  }

  private int dp(float value) {
    return Math.round(getResources().getDisplayMetrics().density * value);
  }

  private GradientDrawable roundedDrawable(int fillColor, int strokeColor, int radiusDp, int strokeWidthDp) {
    GradientDrawable drawable = new GradientDrawable();
    drawable.setShape(GradientDrawable.RECTANGLE);
    drawable.setColor(fillColor);
    drawable.setCornerRadius(dp(radiusDp));
    if (strokeColor != Color.TRANSPARENT && strokeWidthDp > 0) {
      drawable.setStroke(dp(strokeWidthDp), strokeColor);
    }
    return drawable;
  }

  private void applyPillStyle(Button button, boolean selected) {
    button.setAllCaps(false);
    button.setPadding(dp(18), dp(14), dp(18), dp(14));
    if (selected) {
      button.setTextColor(Color.WHITE);
      button.setBackgroundDrawable(roundedDrawable(Color.rgb(18, 18, 18), Color.rgb(18, 18, 18), 22, 0));
    } else {
      button.setTextColor(Color.rgb(24, 24, 24));
      button.setBackgroundDrawable(roundedDrawable(Color.WHITE, Color.rgb(220, 220, 220), 22, 1));
    }
  }

  private void applyDarkActionStyle(Button button) {
    button.setAllCaps(false);
    button.setTextColor(Color.WHITE);
    button.setBackgroundDrawable(roundedDrawable(Color.rgb(18, 18, 18), Color.rgb(18, 18, 18), 22, 0));
    button.setPadding(dp(18), dp(16), dp(18), dp(16));
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
    if (debugStateText != null) {
      debugStateText.setText(debugState);
    }
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


  private final class UberMapBackdropView extends View {
    private final Paint backgroundPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint roadPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint minorRoadPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint parkPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint waterPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint carPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);

    UberMapBackdropView(Context context) {
      super(context);
      backgroundPaint.setColor(Color.rgb(232, 236, 240));
      roadPaint.setColor(Color.WHITE);
      roadPaint.setStrokeWidth(dp(8));
      roadPaint.setStyle(Paint.Style.STROKE);
      minorRoadPaint.setColor(Color.rgb(198, 205, 212));
      minorRoadPaint.setStrokeWidth(dp(2));
      minorRoadPaint.setStyle(Paint.Style.STROKE);
      parkPaint.setColor(Color.rgb(205, 228, 207));
      waterPaint.setColor(Color.rgb(205, 229, 243));
      carPaint.setColor(Color.rgb(28, 28, 28));
      haloPaint.setColor(Color.argb(60, 82, 149, 255));
      dotPaint.setColor(Color.rgb(82, 149, 255));
    }

    @Override
    protected void onDraw(Canvas canvas) {
      super.onDraw(canvas);
      int w = getWidth();
      int h = getHeight();
      canvas.drawRect(0, 0, w, h, backgroundPaint);
      canvas.drawRect(w * 0.70f, 0, w, h * 0.52f, waterPaint);
      canvas.drawRect(w * 0.08f, h * 0.12f, w * 0.22f, h * 0.26f, parkPaint);
      canvas.drawRect(w * 0.58f, h * 0.68f, w * 0.74f, h * 0.86f, parkPaint);
      canvas.drawRect(w * 0.18f, h * 0.62f, w * 0.30f, h * 0.76f, parkPaint);

      canvas.drawLine(w * 0.02f, h * 0.18f, w * 0.96f, h * 0.26f, roadPaint);
      canvas.drawLine(w * 0.10f, h * 0.04f, w * 0.76f, h * 0.90f, roadPaint);
      canvas.drawLine(w * 0.00f, h * 0.52f, w * 1.00f, h * 0.52f, roadPaint);
      canvas.drawLine(w * 0.20f, h * 0.02f, w * 0.92f, h * 0.72f, minorRoadPaint);
      canvas.drawLine(w * 0.02f, h * 0.76f, w * 0.98f, h * 0.68f, minorRoadPaint);
      canvas.drawLine(w * 0.46f, h * 0.06f, w * 0.46f, h * 0.94f, minorRoadPaint);

      float cx = w * 0.62f;
      float cy = h * 0.58f;
      canvas.drawCircle(cx, cy, dp(34), haloPaint);
      canvas.drawCircle(cx, cy, dp(10), dotPaint);
      canvas.drawCircle(cx + dp(22), cy - dp(5), dp(6), carPaint);
      canvas.drawRect(cx + dp(8), cy - dp(2), cx + dp(30), cy + dp(10), carPaint);
    }
  }
}
