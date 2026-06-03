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

public class MainActivity extends Activity {
  private static final String PREFS = "dummy_state";

  private EditText searchInput;
  private EditText nameInput;
  private EditText emailInput;
  private TextView searchResult;
  private TextView statusText;

  @Override
  protected void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);

    LinearLayout root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(48, 64, 48, 48);
    root.setGravity(Gravity.CENTER_HORIZONTAL);

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
    searchButton.setText("Search");
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
    root.addView(nameInput, matchWrap());

    emailInput = new EditText(this);
    emailInput.setId(R.id.email_input);
    emailInput.setHint("Email");
    emailInput.setSingleLine(true);
    root.addView(emailInput, matchWrap());

    Button submitButton = new Button(this);
    submitButton.setId(R.id.submit_button);
    submitButton.setText("Submit Form");
    root.addView(submitButton, matchWrap());

    statusText = new TextView(this);
    statusText.setId(R.id.status_text);
    statusText.setText("Status: waiting");
    statusText.setTextSize(18);
    root.addView(statusText, matchWrap());

    searchButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        String query = clean(searchInput.getText().toString());
        searchResult.setText("Search result: " + query);
        saveState(false);
        hideKeyboard();
      }
    });

    submitButton.setOnClickListener(new View.OnClickListener() {
      @Override
      public void onClick(View view) {
        String name = clean(nameInput.getText().toString());
        String email = clean(emailInput.getText().toString());
        if (name.length() == 0 || email.length() == 0) {
          statusText.setText("Status: missing fields");
        } else {
          statusText.setText("Submitted: " + name + " <" + email + ">");
          saveState(true);
        }
        hideKeyboard();
      }
    });

    ScrollView scrollView = new ScrollView(this);
    scrollView.addView(root);
    setContentView(scrollView);
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
    SharedPreferences.Editor editor = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
    editor.putString("query", clean(searchInput.getText().toString()));
    editor.putString("name", clean(nameInput.getText().toString()));
    editor.putString("email", clean(emailInput.getText().toString()));
    editor.putBoolean("submitted", submitted);
    editor.apply();
  }

  private void hideKeyboard() {
    InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
    if (imm != null && getCurrentFocus() != null) {
      imm.hideSoftInputFromWindow(getCurrentFocus().getWindowToken(), 0);
    }
  }
}
