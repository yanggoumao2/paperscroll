package org.kunyu.paperscroll;

import android.os.Bundle;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        lockTextZoom();
    }

    @Override
    public void onResume() {
        super.onResume();
        lockTextZoom();   // the system font size may have changed while we were in the background
    }

    /** The WebView scales all text by the system font size, which breaks the card layout; the app has its own 字号 setting. */
    private void lockTextZoom() {
        if (bridge == null) return;
        WebView wv = bridge.getWebView();
        if (wv != null) wv.getSettings().setTextZoom(100);
    }
}
