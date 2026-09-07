package com.primeintellect.paymentdemo;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Business logic only: no Android UI, network, bank access or task expected answers. */
public final class AppState {
    public final String episodeId;
    private String recipient = "", account = "", amountInput = "", note = "";
    private long revision = 0, reviewedRevision = -1;
    private Map<String, Object> transaction;

    public AppState(String episodeId) {
        if (episodeId == null || !episodeId.matches("[A-Za-z0-9_-]{1,100}"))
            throw new IllegalArgumentException("Invalid episode ID");
        this.episodeId = episodeId;
    }
    public void recipient(String value) {
        editable();
        if (!value.equals("alex") && !value.equals("blair")) throw new IllegalArgumentException("Choose a listed recipient");
        if (!recipient.equals(value)) { recipient = value; changed(); }
    }
    public void account(String value) {
        editable();
        if (!value.equals("account_1234") && !value.equals("account_5678"))
            throw new IllegalArgumentException("Choose a listed mock account");
        if (!account.equals(value)) { account = value; changed(); }
    }
    public void amount(String value) {
        editable();
        if (value == null || value.length() > 20) throw new IllegalArgumentException("Amount is too long");
        if (!amountInput.equals(value)) { amountInput = value; changed(); }
    }
    public void note(String value) {
        editable();
        if (value == null || value.length() > 80) throw new IllegalArgumentException("Note must be at most 80 characters");
        if (!note.equals(value)) { note = value; changed(); }
    }
    private void editable() {
        if (transaction != null) throw new IllegalStateException("This simulated transfer is already complete");
    }
    private void changed() { revision++; reviewedRevision = -1; }

    public static long parsePaise(String input) {
        String value = input.trim();
        if (!value.matches("[0-9]{1,7}(\\.[0-9]{1,2})?"))
            throw new IllegalArgumentException("Enter a positive amount with at most two decimal places");
        long paise = new BigDecimal(value).movePointRight(2).longValueExact();
        if (paise <= 0 || paise > 100000000L) throw new IllegalArgumentException("Amount must be between INR 0.01 and 1,000,000.00");
        return paise;
    }
    public String validationError() {
        if (recipient.isEmpty()) return "Choose a recipient";
        try { parsePaise(amountInput); } catch (IllegalArgumentException | ArithmeticException ex) { return ex.getMessage(); }
        if (account.isEmpty()) return "Choose a mock account";
        return "";
    }
    public void review() {
        editable();
        String error = validationError();
        if (!error.isEmpty()) throw new IllegalStateException(error);
        reviewedRevision = revision;
    }
    public Map<String, Object> confirm() {
        // Repeated taps return the same receipt, never another transaction.
        if (transaction != null) return new LinkedHashMap<>(transaction);
        if (reviewedRevision != revision) throw new IllegalStateException("Review the current details before confirming");
        String error = validationError();
        if (!error.isEmpty()) throw new IllegalStateException(error);
        transaction = new LinkedHashMap<>();
        transaction.put("transaction_id", UUID.randomUUID().toString());
        transaction.put("episode_id", episodeId);
        transaction.put("recipient_id", recipient);
        transaction.put("amount_paise", parsePaise(amountInput));
        transaction.put("currency", "INR");
        transaction.put("account_id", account);
        transaction.put("note", note);
        transaction.put("reviewed_revision", revision);
        transaction.put("status", "COMPLETED");
        transaction.put("simulated", true);
        return new LinkedHashMap<>(transaction);
    }
    public Map<String, Object> snapshot() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("schema_version", 1);
        result.put("episode_id", episodeId);
        result.put("recipient_id", recipient);
        result.put("account_id", account);
        result.put("amount_input", amountInput);
        long paise = 0;
        try { paise = parsePaise(amountInput); } catch (IllegalArgumentException | ArithmeticException ignored) { }
        result.put("amount_paise", paise);
        result.put("currency", "INR");
        result.put("note", note);
        result.put("revision", revision);
        result.put("reviewed_revision", reviewedRevision);
        result.put("status", transaction != null ? "COMPLETED" : reviewedRevision == revision ? "REVIEW" : "DRAFT");
        result.put("simulated", true);
        List<Map<String, Object>> transactions = new ArrayList<>();
        if (transaction != null) transactions.add(new LinkedHashMap<>(transaction));
        result.put("transactions", transactions);
        return result;
    }

    /** Restore persisted state without creating a second transaction or trusting UI labels. */
    @SuppressWarnings("unchecked")
    public static AppState restore(Map<String, Object> data) {
        if (((Number) data.get("schema_version")).intValue() != 1 || !Boolean.TRUE.equals(data.get("simulated")))
            throw new IllegalArgumentException("Unsupported state");
        AppState state = new AppState((String) data.get("episode_id"));
        String recipient = (String) data.get("recipient_id");
        String account = (String) data.get("account_id");
        if (!recipient.isEmpty()) state.recipient(recipient);
        if (!account.isEmpty()) state.account(account);
        state.amount((String) data.get("amount_input"));
        state.note((String) data.get("note"));
        state.revision = ((Number) data.get("revision")).longValue();
        state.reviewedRevision = ((Number) data.get("reviewed_revision")).longValue();
        if (state.revision < 0 || (state.reviewedRevision != -1 && state.reviewedRevision != state.revision))
            throw new IllegalArgumentException("Invalid review revision");
        List<?> records = (List<?>) data.get("transactions");
        if (records.size() > 1) throw new IllegalArgumentException("Duplicate transactions");
        if (state.reviewedRevision == state.revision && !state.validationError().isEmpty())
            throw new IllegalArgumentException("Invalid reviewed draft");
        if (records.size() == 1) {
            Map<String, Object> tx = (Map<String, Object>) records.get(0);
            if (!state.episodeId.equals(tx.get("episode_id")) || !recipient.equals(tx.get("recipient_id")) ||
                !account.equals(tx.get("account_id")) || !state.note.equals(tx.get("note")) ||
                !"INR".equals(tx.get("currency")) || !"COMPLETED".equals(tx.get("status")) ||
                !Boolean.TRUE.equals(tx.get("simulated")) || !(tx.get("transaction_id") instanceof String) ||
                ((String) tx.get("transaction_id")).isEmpty() ||
                state.reviewedRevision != state.revision ||
                ((Number) tx.get("amount_paise")).longValue() != parsePaise(state.amountInput) ||
                ((Number) tx.get("reviewed_revision")).longValue() != state.revision)
                throw new IllegalArgumentException("Persisted transaction does not match its reviewed draft");
            state.transaction = new LinkedHashMap<>(tx);
        }
        Map<String, Object> restored = state.snapshot();
        if (!restored.get("status").equals(data.get("status")) ||
            ((Number) restored.get("amount_paise")).longValue() != ((Number) data.get("amount_paise")).longValue() ||
            !"INR".equals(data.get("currency")))
            throw new IllegalArgumentException("Inconsistent persisted state");
        return state;
    }
}
