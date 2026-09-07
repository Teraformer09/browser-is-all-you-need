package com.primeintellect.paymentdemo;

import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.TextView;
import android.widget.ScrollView;
import androidx.appcompat.app.AppCompatActivity;
import com.google.android.material.button.MaterialButtonToggleGroup;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.progressindicator.LinearProgressIndicator;
import org.json.JSONObject;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class MainActivity extends AppCompatActivity {
    private static volatile MainActivity active;
    private AppState model;
    private StateStore store;
    private JSONObject persisted;
    private boolean storageFailed, rendering;
    private TextInputEditText amount, note;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        setContentView(R.layout.activity_payment);
        active = this;
        store = new StateStore(this);
        amount = findViewById(R.id.amount_input);
        note = findViewById(R.id.note_input);
        try {
            model = store.load(getIntent().getStringExtra("episode_id"));
            Map<String, Object> data = model.snapshot();
            amount.setText((String) data.get("amount_input"));
            note.setText((String) data.get("note"));
            persist("open", true, "");
        } catch (Exception ex) {
            storageFailed = true;
            ((TextView) findViewById(R.id.status_text)).setText("State unavailable. Start a new explicit test episode.");
            findViewById(R.id.review_button).setEnabled(false);
            return;
        }
        findViewById(R.id.recipient_alex).setOnClickListener(v -> act("select_recipient", () -> model.recipient("alex")));
        findViewById(R.id.recipient_blair).setOnClickListener(v -> act("select_recipient", () -> model.recipient("blair")));
        findViewById(R.id.account_1234).setOnClickListener(v -> act("select_account", () -> model.account("account_1234")));
        findViewById(R.id.account_5678).setOnClickListener(v -> act("select_account", () -> model.account("account_5678")));
        amount.addTextChangedListener(watcher("enter_amount", () -> model.amount(amount.getText().toString())));
        note.addTextChangedListener(watcher("enter_note", () -> model.note(note.getText().toString())));
        findViewById(R.id.review_button).setOnClickListener(v -> act("review", () -> model.review()));
        findViewById(R.id.confirm_transfer_button).setOnClickListener(v -> act("confirm", () -> model.confirm()));
        render("");
    }
    private TextWatcher watcher(String action, Runnable change) {
        return new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { }
            @Override public void afterTextChanged(Editable value) { if (!rendering) act(action, change); }
        };
    }
    private void act(String action, Runnable change) {
        if (storageFailed) return;
        String error = "";
        boolean accepted = true;
        try { change.run(); }
        catch (IllegalArgumentException | IllegalStateException ex) { accepted = false; error = ex.getMessage(); }
        try { persist(action, accepted, error); }
        catch (Exception ex) { storageFailed = true; error = "Storage failed; this episode cannot be verified."; }
        render(error);
    }
    private void persist(String action, boolean accepted, String error) throws Exception {
        persisted = store.save(model, action, accepted, error);
    }
    @SuppressWarnings("unchecked")
    private void render(String error) {
        rendering = true;
        Map<String, Object> data = model.snapshot();
        boolean complete = "COMPLETED".equals(data.get("status"));
        boolean reviewed = "REVIEW".equals(data.get("status"));
        String recipient = (String) data.get("recipient_id"), account = (String) data.get("account_id");
        MaterialButtonToggleGroup recipients = findViewById(R.id.recipient_group);
        MaterialButtonToggleGroup accounts = findViewById(R.id.account_group);
        if (!recipient.isEmpty()) recipients.check(recipient.equals("alex") ? R.id.recipient_alex : R.id.recipient_blair);
        if (!account.isEmpty()) accounts.check(account.equals("account_1234") ? R.id.account_1234 : R.id.account_5678);
        ((TextView) findViewById(R.id.recipient_label)).setText(recipient.isEmpty() ? "1 · Choose a recipient" : "1 · Recipient: " + (recipient.equals("alex") ? "Alex" : "Blair"));
        ((TextView) findViewById(R.id.account_label)).setText(account.isEmpty() ? "3 · Select a mock account" : "3 · Mock account: " + account.replace("account_", ""));
        boolean editable = !complete && !storageFailed;
        for (int id : new int[]{R.id.recipient_alex, R.id.recipient_blair, R.id.account_1234,
            R.id.account_5678, R.id.amount_input, R.id.note_input}) findViewById(id).setEnabled(editable);
        findViewById(R.id.review_button).setEnabled(editable && model.validationError().isEmpty());
        findViewById(R.id.review_card).setVisibility(reviewed && !storageFailed ? View.VISIBLE : View.GONE);
        findViewById(R.id.confirm_transfer_button).setEnabled(reviewed && !storageFailed);
        long paise = ((Number) data.get("amount_paise")).longValue();
        String summary = "Recipient: " + recipient + "\nAmount: INR " +
            String.format(Locale.ROOT, "%d.%02d", paise / 100, paise % 100) +
            "\nAccount: " + account.replace("account_", "Mock • ") + "\nNote: " + data.get("note");
        ((TextView) findViewById(R.id.review_summary)).setText(summary);
        int stages = (recipient.isEmpty() ? 0 : 1) + (paise > 0 ? 1 : 0) + (account.isEmpty() ? 0 : 1) +
            (((String) data.get("note")).isEmpty() ? 0 : 1) + (reviewed || complete ? 1 : 0) + (complete ? 1 : 0);
        ((LinearProgressIndicator) findViewById(R.id.stage_progress)).setProgress(stages);
        ((TextView) findViewById(R.id.progress_text)).setText(stages + "/6 workflow steps • not an evaluation reward");
        ((TextView) findViewById(R.id.status_text)).setText(!error.isEmpty() ? error :
            complete ? "Simulated payment complete. No money moved." :
            reviewed ? "Check the details, then confirm. Editing any value requires a new review." :
            model.validationError().isEmpty() ? "Ready to review your transfer." : model.validationError());
        TextView receipt = findViewById(R.id.receipt_text);
        receipt.setVisibility(complete && !storageFailed ? View.VISIBLE : View.GONE);
        if (complete) {
            Map<String, Object> transaction = ((List<Map<String, Object>>) data.get("transactions")).get(0);
            receipt.setText(summary + "\nReceipt: " + transaction.get("transaction_id"));
        }
        if (complete && !storageFailed) {
            ScrollView scroll = findViewById(R.id.payment_scroll);
            scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
        }
        rendering = false;
    }
    public static String verifierSnapshot() {
        MainActivity activity = active;
        if (activity == null || activity.model == null || activity.storageFailed || activity.persisted == null)
            throw new IllegalStateException("Live, persisted payment evidence unavailable");
        try {
            JSONObject result = new JSONObject(activity.model.snapshot());
            result.put("events", activity.persisted.getJSONArray("events"));
            result.put("last_action", activity.persisted.getString("last_action"));
            result.put("last_action_accepted", activity.persisted.getBoolean("last_action_accepted"));
            result.put("last_error", activity.persisted.getString("last_error"));
            return result.toString();
        } catch (Exception ex) { throw new IllegalStateException(ex); }
    }
    @Override protected void onDestroy() { if (active == this) active = null; super.onDestroy(); }
}
