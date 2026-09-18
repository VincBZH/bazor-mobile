package com.bazor.mobile;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.window.OnBackInvokedDispatcher;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {
    private static final int REQ_BLE = 4101;

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
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(new WatchBridge(), "BazorWatch");
        webView.loadUrl("file:///android_asset/index_v3.html");

        startPcDiscovery();
        ensureWatchdogStarted();

        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                () -> {
                    if (webView.canGoBack()) webView.goBack();
                    else finish();
                }
            );
        }
    }

    private void ensureWatchdogStarted() {
        SharedPreferences prefs = getSharedPreferences(BleWatchdogService.PREFS, MODE_PRIVATE);
        if (!prefs.contains("enabled")) prefs.edit().putBoolean("enabled", true).apply();

        if (!prefs.getBoolean("enabled", true)) return;

        if (!watchPermissionsGranted()) {
            requestWatchPermissions();
            return;
        }
        startWatchdogService(null);
    }

    private boolean watchPermissionsGranted() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestWatchPermissions() {
        List<String> permissions = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.BLUETOOTH_SCAN);
            }
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.BLUETOOTH_CONNECT);
            }
        } else {
            if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.ACCESS_FINE_LOCATION);
            }
        }
        if (Build.VERSION.SDK_INT >= 33
            && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS);
        }

        if (permissions.isEmpty()) {
            startWatchdogService(null);
        } else {
            requestPermissions(permissions.toArray(new String[0]), REQ_BLE);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_BLE && watchPermissionsGranted()) {
            startWatchdogService(null);
        }
    }

    private void startWatchdogService(String action) {
        Intent intent = new Intent(this, BleWatchdogService.class);
        if (action != null) intent.setAction(action);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent);
            } else {
                startService(intent);
            }
        } catch (Exception ignored) {}
    }

    private void stopWatchdogService() {
        Intent intent = new Intent(this, BleWatchdogService.class);
        intent.setAction(BleWatchdogService.ACTION_STOP);
        try { startService(intent); } catch (Exception ignored) {
            try { stopService(new Intent(this, BleWatchdogService.class)); } catch (Exception ignoredAgain) {}
        }
    }

    private void startPcDiscovery() {
        new Thread(() -> {
            while (running) {
                boolean found = false;
                String foundName = "";
                String apiBase = "";
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
                        String[] parts = msg.split("\\|");
                        if (parts.length > 1) foundName = parts[1];
                        String port = parts.length > 2 ? parts[2] : "8765";
                        apiBase = "http://" + reply.getAddress().getHostAddress() + ":" + port;
                    }
                } catch (Exception ignored) {}

                final boolean online = found;
                final String safeName = jsSafe(foundName);
                final String safeApi = jsSafe(apiBase);
                runOnUiThread(() -> {
                    String js =
                        "(function(){" +
                        "if(window.setPcStatus)window.setPcStatus(" + online + ",'" + safeName + "');" +
                        (online
                            ? "if(window.setBazorApi)window.setBazorApi('" + safeApi + "');"
                            : "if(window.setBazorApi)window.setBazorApi('');") +
                        "})();";
                    webView.evaluateJavascript(js, null);
                });

                try {
                    Thread.sleep(4000);
                } catch (InterruptedException ignored) {}
            }
        }).start();
    }

    private String jsSafe(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\").replace("'", "\\'");
    }

    @Override
    protected void onDestroy() {
        running = false;
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (Build.VERSION.SDK_INT < 33 && webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    public class WatchBridge {
        @JavascriptInterface
        public String getStatus() {
            SharedPreferences p = getSharedPreferences(BleWatchdogService.PREFS, MODE_PRIVATE);
            JSONObject o = new JSONObject();
            try {
                o.put("enabled", p.getBoolean("enabled", true));
                o.put("serviceRunning", p.getBoolean("serviceRunning", false));
                o.put("scanning", p.getBoolean("scanning", false));
                o.put("lowLatency", p.getBoolean("lowLatency", false));
                o.put("status", p.getString("status", "STARTING"));
                o.put("targetMac", p.getString("targetMac", ""));
                o.put("targetName", p.getString("targetName", ""));
                o.put("lastSeenMs", p.getLong("lastSeenMs", 0L));
                o.put("lastRssi", p.getInt("lastRssi", -127));
                o.put("outages", p.getInt("outages", 0));
                o.put("recoveries", p.getInt("recoveries", 0));
                o.put("lastOutageMs", p.getLong("lastOutageMs", 0L));
                o.put("scanError", p.getInt("scanError", 0));
                String rawCandidates = p.getString("candidates", "[]");
                try {
                    o.put("candidates", new JSONArray(rawCandidates));
                } catch (Exception ignored) {
                    o.put("candidates", new JSONArray());
                }
            } catch (Exception ignored) {}
            return o.toString();
        }

        @JavascriptInterface
        public void start() {
            runOnUiThread(() -> {
                getSharedPreferences(BleWatchdogService.PREFS, MODE_PRIVATE)
                    .edit().putBoolean("enabled", true).apply();
                if (watchPermissionsGranted()) startWatchdogService(null);
                else requestWatchPermissions();
            });
        }

        @JavascriptInterface
        public void stop() {
            runOnUiThread(() -> {
                getSharedPreferences(BleWatchdogService.PREFS, MODE_PRIVATE)
                    .edit().putBoolean("enabled", false).apply();
                stopWatchdogService();
            });
        }

        @JavascriptInterface
        public void restartScan() {
            runOnUiThread(() -> {
                if (watchPermissionsGranted()) {
                    startWatchdogService(BleWatchdogService.ACTION_RESTART_SCAN);
                } else {
                    requestWatchPermissions();
                }
            });
        }

        @JavascriptInterface
        public boolean setTarget(String mac, String name) {
            if (mac == null) return false;
            String clean = mac.trim().toUpperCase();
            if (!BluetoothAdapter.checkBluetoothAddress(clean)) return false;

            SharedPreferences.Editor e = getSharedPreferences(BleWatchdogService.PREFS, MODE_PRIVATE).edit();
            e.putString("targetMac", clean);
            e.putString("targetName", name == null ? "" : name.trim());
            e.putLong("lastSeenMs", 0L);
            e.putInt("lastRssi", -127);
            e.putInt("outages", 0);
            e.putInt("recoveries", 0);
            e.putString("status", "SEARCHING");
            e.apply();

            runOnUiThread(() -> {
                if (watchPermissionsGranted()) startWatchdogService(BleWatchdogService.ACTION_RESTART_SCAN);
                else requestWatchPermissions();
            });
            return true;
        }

        @JavascriptInterface
        public void clearTarget() {
            getSharedPreferences(BleWatchdogService.PREFS, MODE_PRIVATE)
                .edit()
                .remove("targetMac")
                .remove("targetName")
                .remove("lastSeenMs")
                .putString("status", "NO_TARGET")
                .apply();
        }

        @JavascriptInterface
        public void openBluetoothSettings() {
            runOnUiThread(() -> {
                try {
                    startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS));
                } catch (Exception ignored) {}
            });
        }
    }
}
