package com.primeintellect.paymentdemo;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.Map;
import java.util.List;

public class AppStateTest {
    private AppState draft() {
        AppState state = new AppState("unit_episode");
        state.recipient("alex"); state.amount("500.00"); state.account("account_1234"); state.note("Lunch");
        return state;
    }
    @Test public void exactMoney() { assertEquals(50000L, AppState.parsePaise("500")); assertEquals(1L, AppState.parsePaise("0.01")); }
    @Test public void invalidMoneyRejected() {
        for (String s : new String[]{"0","-1","1.001","NaN","1e3","1000000.01","", "Infinity"}) {
            assertThrows(IllegalArgumentException.class, () -> AppState.parsePaise(s));
        }
    }
    @Test public void confirmationRequiresReview() {
        AppState state = draft();
        assertThrows(IllegalStateException.class, () -> state.confirm());
        assertEquals("DRAFT", state.snapshot().get("status"));
    }
    @Test public void prerequisitesRequired() {
        assertThrows(IllegalStateException.class, () -> new AppState("empty").review());
    }
    @Test public void successfulTransaction() {
        AppState state = draft(); state.review();
        Map<String,Object> tx = state.confirm();
        assertEquals(50000L, tx.get("amount_paise")); assertEquals("alex", tx.get("recipient_id"));
        assertEquals("account_1234", tx.get("account_id")); assertEquals("Lunch", tx.get("note"));
        assertEquals("COMPLETED", state.snapshot().get("status"));
    }
    @Test public void doubleConfirmationIsIdempotent() {
        AppState state = draft(); state.review();
        assertEquals(state.confirm(), state.confirm());
        assertEquals(1, ((List<?>) state.snapshot().get("transactions")).size());
    }
    @Test public void amountEditInvalidatesReviewAndRecovers() {
        AppState state = draft(); state.review(); state.amount("600");
        assertThrows(IllegalStateException.class, () -> state.confirm());
        state.review(); assertEquals(60000L, state.confirm().get("amount_paise"));
    }
    @Test public void everyDraftFieldInvalidatesReview() {
        AppState state = draft(); state.review(); state.recipient("blair");
        assertThrows(IllegalStateException.class, () -> state.confirm());
        state.review(); state.account("account_5678");
        assertThrows(IllegalStateException.class, () -> state.confirm());
        state.review(); state.note("Dinner");
        assertThrows(IllegalStateException.class, () -> state.confirm());
    }
    @Test public void committedStateCannotBeEdited() {
        AppState state = draft(); state.review(); state.confirm();
        assertThrows(IllegalStateException.class, () -> state.amount("1"));
        assertThrows(IllegalStateException.class, () -> state.recipient("blair"));
    }
    @Test public void selectionsAreAllowlisted() {
        AppState state = draft();
        assertThrows(IllegalArgumentException.class, () -> state.account("real_bank"));
        assertThrows(IllegalArgumentException.class, () -> state.recipient("unknown"));
    }
    @Test public void completedStateRestoresWithoutDuplicate() {
        AppState state = draft(); state.review(); Map<String,Object> tx = state.confirm();
        AppState restored = AppState.restore(state.snapshot());
        assertEquals(tx, restored.confirm()); assertEquals(state.snapshot(), restored.snapshot());
    }
    @Test public void draftAndReviewRestore() {
        AppState state = draft();
        assertEquals(state.snapshot(), AppState.restore(state.snapshot()).snapshot());
        state.review();
        assertEquals(state.snapshot(), AppState.restore(state.snapshot()).snapshot());
    }
    @Test public void corruptedStateRejected() {
        Map<String,Object> data = draft().snapshot(); data.put("amount_paise", 1L);
        assertThrows(IllegalArgumentException.class, () -> AppState.restore(data));
    }
}
