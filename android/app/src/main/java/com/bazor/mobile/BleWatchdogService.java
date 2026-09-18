package com.bazor.mobile;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class BleWatchdogService extends Service {
    public static final String PREFS = "bazor_watchdog";
    public static final String ACTION_RESTART_SCAN = "com.bazor.mobile.RESTART_BLE_SCAN";
    public static final String ACTION_STOP = "com.bazor.mobile.STOP_BLE_WATCHDOG";

    private static final String CHANNEL_ID = "bazor_ble_watchdog";
    private static final int NOTIFICATION_ID = 4421;
    private static final long LOST_AFTER_MS = 10_000L;
    private static final long CANDIDATE_TTL_MS = 30_000L;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, Candidate> candidates = new LinkedHashMap<>();

    private SharedPreferences prefs;
    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private boolean scanning = false;
    private boolean lowLatency = false;
    private boolean wasLost = false;
    private long lastCandidatePublish = 0L;

    private final ScanCallback callback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            handleResult(result);
        }

        @Override
        public void onBatchScanResults(List<ScanResult> results) {
            for (ScanResult result : results) handleResult(result);
        }

        @Override
        public void onScanFailed(int errorCode) {
            prefs.edit()
                .putString("status", "SCAN_ERROR")
                .putInt("scanError", errorCode)
                .apply();
            scheduleBalancedRestart(2500L);
            updateNotification();
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        prefs.edit().putBoolean("serviceRunning", true).apply();

        BluetoothManager manager = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        adapter = manager != null ? manager.getAdapter() : null;

        createNotificationChannel();
        startForeground(NOTIFICATION_ID, buildNotification("Surveillance Bluetooth active"));

        startScan(ScanSettings.SCAN_MODE_BALANCED);
        handler.post(evaluateRunnable);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            prefs.edit().putBoolean("enabled", false).apply();
            stopSelf();
            return START_NOT_STICKY;
        }

        prefs.edit().putBoolean("enabled", true).apply();
        if (intent != null && ACTION_RESTART_SCAN.equals(intent.getAction())) {
            recoveryScan();
        } else if (!scanning) {
            startScan(ScanSettings.SCAN_MODE_BALANCED);
        }
        return START_STICKY;
    }

    private final Runnable evaluateRunnable = new Runnable() {
        @Override
        public void run() {
            evaluateLink();
            publishCandidates();
            handler.postDelayed(this, 1000L);
        }
    };

    private void handleResult(ScanResult result) {
        if (result == null || result.getDevice() == null) return;
        if (!hasScanPermission()) return;

        String address;
        String name = "";
        try {
            address = result.getDevice().getAddress();
            if (hasConnectPermission()) {
                String deviceName = result.getDevice().getName();
                if (deviceName != null) name = deviceName;
            }
            if ((name == null || name.isEmpty()) && result.getScanRecord() != null) {
                String advertisedName = result.getScanRecord().getDeviceName();
                if (advertisedName != null) name = advertisedName;
            }
        } catch (SecurityException e) {
            return;
        }

        if (address == null || address.isEmpty()) return;
        long now = System.currentTimeMillis();
        candidates.put(address, new Candidate(address, name == null ? "" : name, result.getRssi(), now));

        String target = prefs.getString("targetMac", "");
        if (target != null && target.equalsIgnoreCase(address)) {
            String savedName = prefs.getString("targetName", "");
            if ((savedName == null || savedName.isEmpty()) && name != null && !name.isEmpty()) {
                prefs.edit().putString("targetName", name).apply();
            }

            boolean recovering = wasLost;
            SharedPreferences.Editor editor = prefs.edit()
                .putLong("lastSeenMs", now)
                .putInt("lastRssi", result.getRssi())
                .putString("status", "OK")
                .putInt("scanError", 0);
            if (recovering) {
                editor.putInt("recoveries", prefs.getInt("recoveries", 0) + 1);
                wasLost = false;
            }
            editor.apply();

            if (recovering) {
                startScan(ScanSettings.SCAN_MODE_BALANCED);
                updateNotification();
            }
        }

        if (now - lastCandidatePublish > 1500L) publishCandidates();
    }

    private void evaluateLink() {
        if (adapter == null) {
            prefs.edit().putString("status", "NO_BLUETOOTH").apply();
            return;
        }

        try {
            if (!adapter.isEnabled()) {
                prefs.edit().putString("status", "BT_OFF").apply();
                updateNotification();
                return;
            }
        } catch (SecurityException ignored) {}

        String target = prefs.getString("targetMac", "");
        if (target == null || target.isEmpty()) {
            prefs.edit().putString("status", "NO_TARGET").apply();
            return;
        }

        long lastSeen = prefs.getLong("lastSeenMs", 0L);
        if (lastSeen <= 0L) {
            prefs.edit().putString("status", "SEARCHING").apply();
            return;
        }

        long age = System.currentTimeMillis() - lastSeen;
        if (age > LOST_AFTER_MS) {
            if (!wasLost) {
                wasLost = true;
                prefs.edit()
                    .putString("status", "LOST")
                    .putInt("outages", prefs.getInt("outages", 0) + 1)
                    .putLong("lastOutageMs", System.currentTimeMillis())
                    .apply();
                recoveryScan();
                updateNotification();
            }
        } else {
            if (!"OK".equals(prefs.getString("status", ""))) {
                prefs.edit().putString("status", "OK").apply();
            }
        }
    }

    private void recoveryScan() {
        startScan(ScanSettings.SCAN_MODE_LOW_LATENCY);
        handler.removeCallbacks(backToBalancedRunnable);
        handler.postDelayed(backToBalancedRunnable, 8000L);
    }

    private final Runnable backToBalancedRunnable = () -> startScan(ScanSettings.SCAN_MODE_BALANCED);

    private void scheduleBalancedRestart(long delayMs) {
        handler.removeCallbacks(backToBalancedRunnable);
        handler.postDelayed(backToBalancedRunnable, delayMs);
    }

    private void startScan(int mode) {
        if (adapter == null || !hasScanPermission()) {
            prefs.edit().putString("status", "PERMISSION").apply();
            return;
        }

        try {
            if (!adapter.isEnabled()) {
                prefs.edit().putString("status", "BT_OFF").apply();
                return;
            }

            BluetoothLeScanner current = adapter.getBluetoothLeScanner();
            if (current == null) {
                prefs.edit().putString("status", "SCAN_ERROR").apply();
                return;
            }

            if (scanning && scanner != null) {
                try { scanner.stopScan(callback); } catch (Exception ignored) {}
            }

            scanner = current;
            ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(mode)
                .setReportDelay(0L)
                .build();
            scanner.startScan(null, settings, callback);
            scanning = true;
            lowLatency = mode == ScanSettings.SCAN_MODE_LOW_LATENCY;
            prefs.edit()
                .putBoolean("scanning", true)
                .putBoolean("lowLatency", lowLatency)
                .putInt("scanError", 0)
                .apply();
        } catch (SecurityException e) {
            prefs.edit().putString("status", "PERMISSION").putBoolean("scanning", false).apply();
        } catch (Exception e) {
            prefs.edit().putString("status", "SCAN_ERROR").putBoolean("scanning", false).apply();
        }
    }

    private void stopScan() {
        if (scanner != null && scanning && hasScanPermission()) {
            try { scanner.stopScan(callback); } catch (Exception ignored) {}
        }
        scanning = false;
        prefs.edit().putBoolean("scanning", false).apply();
    }

    private void publishCandidates() {
        long now = System.currentTimeMillis();
        lastCandidatePublish = now;

        List<Candidate> list = new ArrayList<>();
        List<String> stale = new ArrayList<>();
        for (Map.Entry<String, Candidate> entry : candidates.entrySet()) {
            Candidate c = entry.getValue();
            if (now - c.lastSeen > CANDIDATE_TTL_MS) stale.add(entry.getKey());
            else list.add(c);
        }
        for (String key : stale) candidates.remove(key);

        list.sort(Comparator.comparingInt((Candidate c) -> c.rssi).reversed());
        JSONArray array = new JSONArray();
        int max = Math.min(12, list.size());
        for (int i = 0; i < max; i++) {
            Candidate c = list.get(i);
            JSONObject o = new JSONObject();
            try {
                o.put("mac", c.address);
                o.put("name", c.name);
                o.put("rssi", c.rssi);
                o.put("lastSeenMs", c.lastSeen);
                array.put(o);
            } catch (Exception ignored) {}
        }
        prefs.edit().putString("candidates", array.toString()).apply();
    }

    private boolean hasScanPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasConnectPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true;
        return checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "BAZOR liaison montre",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Surveillance locale de la liaison Bluetooth de la montre.");
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification(String text) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(
            this,
            0,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);

        return builder
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle("BAZOR • Liaison montre")
            .setContentText(text)
            .setContentIntent(pending)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build();
    }

    private void updateNotification() {
        String status = prefs.getString("status", "");
        String text;
        if ("OK".equals(status)) text = "Montre détectée • liaison surveillée";
        else if ("LOST".equals(status)) text = "Micro-coupure détectée • relance BLE en cours";
        else if ("BT_OFF".equals(status)) text = "Bluetooth désactivé";
        else if ("NO_TARGET".equals(status)) text = "Choisis la montre dans BAZOR";
        else text = "Recherche de la montre…";

        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(NOTIFICATION_ID, buildNotification(text));
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        stopScan();
        prefs.edit().putBoolean("serviceRunning", false).apply();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private static class Candidate {
        final String address;
        final String name;
        final int rssi;
        final long lastSeen;

        Candidate(String address, String name, int rssi, long lastSeen) {
            this.address = address;
            this.name = name;
            this.rssi = rssi;
            this.lastSeen = lastSeen;
        }
    }
}
