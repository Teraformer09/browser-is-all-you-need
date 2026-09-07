package com.primeintellect.paymentdemo;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

/** One atomic SharedPreferences value contains both state and action receipts. */
public final class StateStore {
    private final android.content.SharedPreferences preferences;
    private JSONArray events = new JSONArray();
    public StateStore(Context context) { preferences = context.getSharedPreferences("payment_state", Context.MODE_PRIVATE); }
    public AppState load(String requestedEpisode) throws Exception {
        String saved = preferences.getString("snapshot", null);
        if (saved == null) return new AppState(requestedEpisode == null ? java.util.UUID.randomUUID().toString() : requestedEpisode);
        JSONObject json = new JSONObject(saved);
        if (requestedEpisode != null && !requestedEpisode.equals(json.getString("episode_id")))
            return new AppState(requestedEpisode);
        events = json.getJSONArray("events");
        return AppState.restore(objectMap(json));
    }
    public JSONObject save(AppState state, String action, boolean accepted, String error) throws Exception {
        JSONObject event = new JSONObject();
        event.put("sequence", events.length());
        event.put("action", action);
        event.put("accepted", accepted);
        event.put("error", error);
        event.put("state", new JSONObject(state.snapshot()));
        JSONArray next = new JSONArray(events.toString());
        next.put(event);
        JSONObject snapshot = new JSONObject(state.snapshot());
        snapshot.put("events", next);
        snapshot.put("last_action", action);
        snapshot.put("last_action_accepted", accepted);
        snapshot.put("last_error", error);
        if (!preferences.edit().putString("snapshot", snapshot.toString()).commit())
            throw new IllegalStateException("Payment state could not be persisted");
        events = next;
        return snapshot;
    }
    public static Map<String, Object> objectMap(JSONObject json) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        Iterator<String> keys = json.keys();
        while (keys.hasNext()) { String key = keys.next(); result.put(key, convert(json.get(key))); }
        return result;
    }
    private static Object convert(Object value) throws Exception {
        if (value instanceof JSONObject) return objectMap((JSONObject) value);
        if (value instanceof JSONArray) {
            ArrayList<Object> list = new ArrayList<>();
            JSONArray array = (JSONArray) value;
            for (int i = 0; i < array.length(); i++) list.add(convert(array.get(i)));
            return list;
        }
        return value == JSONObject.NULL ? null : value;
    }
}
