package com.bazor.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.window.OnBackInvokedDispatcher;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private WebView webView;
    private volatile boolean running = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setDatabaseEnabled(true);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.loadUrl("file:///android_asset/index.html");

        startPcDiscovery();

        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                () -> {
                    if (webView.canGoBack()) webView.goBack();
                    else finish();
                }
            );
        }
    }

    private void startPcDiscovery() {
        new Thread(() -> {
            while (running) {
                boolean found = false;
                String foundName = "";
                try (DatagramSocket socket = new DatagramSocket()) {
                    socket.setBroadcast(true);
                    socket.setSoTimeout(1800);

                    byte[] out = "BAZOR_DISCOVER_V1".getBytes(StandardCharsets.UTF_8);
                    DatagramPacket packet = new DatagramPacket(
                        out, out.length,
                        InetAddress.getByName("255.255.255.255"), 8766
                    );
                    socket.send(packet);

                    byte[] buf = new byte[512];
                    DatagramPacket reply = new DatagramPacket(buf, buf.length);
                    socket.receive(reply);
                    String msg = new String(reply.getData(), 0, reply.getLength(), StandardCharsets.UTF_8);

                    if (msg.startsWith("BAZOR_PC_OK")) {
                        found = true;
                        String[] parts = msg.split("\\|", 2);
                        if (parts.length > 1) foundName = parts[1];
                    }
                } catch (Exception ignored) {}

                final boolean online = found;
                final String safeName = foundName.replace("\\", "\\\\").replace("'", "\\'");
                runOnUiThread(() -> {
                    String js =
                        "(function(){" +
                        "var b=document.querySelector('header .badge');" +
                        "var s=document.querySelector('header .sub');" +
                        "if(!b||!s)return;" +
                        "if(" + online + "){" +
                        "b.className='badge ok';b.textContent='PC EN LIGNE';" +
                        "s.textContent='Mobile • relais détecté" + (safeName.isEmpty() ? "" : " • " + safeName) + "';" +
                        "}else{" +
                        "b.className='badge blocked';b.textContent='PC HORS LIGNE';" +
                        "s.textContent='Mobile • relais PC introuvable sur ce Wi-Fi';" +
                        "}" +
                        "})();";
                    webView.evaluateJavascript(js, null);
                });

                try {
                    Thread.sleep(4000);
                } catch (InterruptedException ignored) {}
            }
        }).start();
    }

    @Override
    protected void onDestroy() {
        running = false;
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (android.os.Build.VERSION.SDK_INT < 33 && webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
