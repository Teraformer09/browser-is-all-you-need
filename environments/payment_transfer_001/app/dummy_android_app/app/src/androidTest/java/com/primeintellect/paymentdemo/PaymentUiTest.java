package com.primeintellect.paymentdemo;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;
import org.json.JSONObject;

/** Separate instrumentation APK. Does not add a production-app test endpoint. */
public final class PaymentUiTest extends Instrumentation {
    private Activity activity;
    private int checks;
    private View view(int id) { return activity.findViewById(id); }
    private void check(boolean ok, String message) { if (!ok) throw new AssertionError(message); checks++; }
    private void assertions() {
        check(!view(R.id.review_button).isEnabled(), "Review enabled without draft");
        check(!view(R.id.review_card).isShown(), "Review card initially visible");
        view(R.id.confirm_transfer_button).performClick();
        check(((TextView)view(R.id.status_text)).getText().toString().contains("Review"), "Early confirm not rejected");
        view(R.id.recipient_alex).performClick();
        ((EditText)view(R.id.amount_input)).setText("500");
        view(R.id.account_1234).performClick();
        ((EditText)view(R.id.note_input)).setText("Lunch");
        check(view(R.id.review_button).isEnabled(), "Valid draft cannot be reviewed");
        view(R.id.review_button).performClick();
        check(view(R.id.review_card).isShown(), "Review missing");
        check(((TextView)view(R.id.review_summary)).getText().toString().contains("500.00"), "Review amount wrong");
        ((EditText)view(R.id.amount_input)).setText("600");
        check(!view(R.id.review_card).isShown(), "Stale review remained visible");
        ((EditText)view(R.id.amount_input)).setText("500");
        view(R.id.review_button).performClick();
        view(R.id.confirm_transfer_button).performClick();
        check(view(R.id.receipt_text).isShown(), "Receipt missing");
        check(!view(R.id.amount_input).isEnabled(), "Committed transfer still editable");
        check(((TextView)view(R.id.recipient_label)).getText().toString().contains("Alex"), "Selected recipient not readable");
        check(((TextView)view(R.id.account_label)).getText().toString().contains("1234"), "Selected account not readable");
        try {
            JSONObject before = new JSONObject(MainActivity.verifierSnapshot());
            String id = before.getJSONArray("transactions").getJSONObject(0).getString("transaction_id");
            view(R.id.confirm_transfer_button).performClick();
            JSONObject after = new JSONObject(MainActivity.verifierSnapshot());
            check(after.getJSONArray("transactions").length() == 1, "Duplicate transfer");
            check(id.equals(after.getJSONArray("transactions").getJSONObject(0).getString("transaction_id")), "Receipt changed");
            check(after.getJSONArray("transactions").getJSONObject(0).getLong("amount_paise") == 50000, "Committed amount wrong");
        } catch (Exception ex) { throw new AssertionError(ex); }
    }
    @Override public void onCreate(Bundle args) { super.onCreate(args); start(); }
    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            Intent intent = new Intent(Intent.ACTION_MAIN);
            intent.setClassName("com.primeintellect.paymentdemo", "com.primeintellect.paymentdemo.MainActivity");
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            intent.putExtra("episode_id", "payment_ui_" + System.currentTimeMillis());
            activity = startActivitySync(intent);
            waitForIdleSync();
            runOnMainSync(this::assertions);
            result.putString("stream", "PASS: " + checks + " payment UI assertions");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable ex) {
            result.putString("stream", "FAIL: " + ex.toString());
            finish(Activity.RESULT_CANCELED, result);
        }
    }
}
