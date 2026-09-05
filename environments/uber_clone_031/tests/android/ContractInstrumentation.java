package com.primeintellect.dummyrl.contracttest;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;

/** Isolated test APK; no test backdoor is added to the production app. */
public class ContractInstrumentation extends Instrumentation {
  private Activity activity;
  private int checks = 0;
  private View view(String id) {
    return activity.findViewById(activity.getResources().getIdentifier(id, "id", "com.primeintellect.dummyrl"));
  }
  private SharedPreferences state() { return activity.getSharedPreferences("dummy_state", 0); }
  private void check(boolean value, String message) {
    if (!value) { throw new AssertionError(message); }
    checks++;
  }
  private void click(String id) { view(id).performClick(); }
  private void text(String id, String value) { ((EditText)view(id)).setText(value); }
  private void assertions() {
    check(!view("destination_search_button").isEnabled(), "Now enabled before ride type");
    check(!view("location_suggestion_1").isEnabled(), "suggestion enabled before ride type");
    check(!view("payment_card").isShown(), "payment visible before cab");
    click("payment_card"); // Deliberately bypass visibility to test the actual app guard.
    check(state().getString("payment", "").equals(""), "rejected Card mutated payment");
    check(state().getInt("journey_stage", -1) == 0, "rejection advanced stage");
    check(!state().getBoolean("last_action_accepted", true), "rejection claimed acceptance");
    check(((TextView)view("final_status_text")).getText().toString().contains("Choose a cab"),
          "rejection reason missing from UI");
    check(!state().getBoolean("sequence_error", true), "rejection poisoned progression");
    text("pickup_input", "Airport Road");
    check(state().getString("ride_pickup", "").equals("Airport Road"), "pickup input not persisted");
    click("ride_type_premium");
    check(!view("destination_search_button").isEnabled(), "Now enabled with empty destination");
    click("destination_search_button");
    check(!state().getBoolean("last_action_accepted", true), "empty search accepted");
    text("drop_input", "City Centre");
    check(state().getString("ride_drop", "").equals("City Centre"), "destination input not persisted");
    check(view("destination_search_button").isEnabled(), "valid search remains disabled");
    click("destination_search_button");
    check(state().getInt("journey_stage", -1) == 2, "recovery after rejection failed");
    check(!view("payment_card").isShown(), "payment visible before cab selection");
    click("ride_option_premium");
    check(view("payment_card").isShown(), "payment not shown after cab");
    click("payment_card");
    check(state().getString("payment", "").equals("card"), "valid Card not committed");
    text("drop_input", "Changed destination");
    check(state().getInt("journey_stage", -1) == 1, "destination edit did not reset dependents");
    check(state().getString("selected_ride", "").equals(""), "stale cab after destination edit");
    check(state().getString("payment", "").equals(""), "stale payment after destination edit");
    check(!view("confirm_ride_button").isShown(), "booking visible after dependent invalidation");
    text("drop_input", "City Centre");
    click("destination_search_button"); click("ride_option_premium"); click("payment_card");
    text("pickup_input", "");
    check(!view("confirm_ride_button").isEnabled(), "Book enabled with empty pickup");
    click("confirm_ride_button");
    check(!state().getBoolean("ride_confirmed", true), "empty pickup booking accepted");
    check(state().getInt("journey_stage", -1) == 4, "invalid booking corrupted stage");
    text("pickup_input", "Airport Road");
    click("confirm_ride_button");
    check(state().getBoolean("ride_confirmed", false), "recovered booking did not confirm");
    check(state().getInt("journey_stage", -1) == 5, "final stage missing");
    check(state().getString("screen", "").equals("ride_booked"), "booked screen missing");
    text("pickup_input", "Other pickup");
    check(!state().getBoolean("ride_confirmed", true), "editing pickup retained stale confirmed booking");
    check(state().getInt("journey_stage", -1) == 4, "pickup edit not recoverable");
  }
  @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
  @Override public void onStart() {
    Bundle result = new Bundle();
    try {
      Intent intent = new Intent();
      intent.setClassName("com.primeintellect.dummyrl", "com.primeintellect.dummyrl.MainActivity");
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
      intent.putExtra("episode_id", "android-contract-test");
      intent.putExtra("start_screen", "ride");
      activity = startActivitySync(intent);
      runOnMainSync(new Runnable() { public void run() { assertions(); } });
      result.putString("stream", "PASS: " + checks + " app-side contract assertions\n");
      finish(Activity.RESULT_OK, result);
    } catch (Throwable error) {
      result.putString("stream", "FAIL after " + checks + " assertions: " + error.toString() + "\n");
      finish(Activity.RESULT_CANCELED, result);
    }
  }
}
