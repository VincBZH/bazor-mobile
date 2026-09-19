package com.bazor.watch;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanFilter;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class BleWatchService extends Service {
    public static final String PREFS = "bazor_watch";
    public static final String ACTION_RESTART_SCAN = "com.bazor.watch.RESTART_SCAN";
    public static final String ACTION_STOP = "com.bazor.watch.STOP";

    private static final String CHANNEL = "bazor_watch_link";
    private static final int NOTIF_ID = 7001;
    private static final long LOST_AFTER_MS = 10_000L;
    private static final long CANDIDATE_TTL_MS = 30_000L;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, Candidate> candidates = new LinkedHashMap<>();

    private SharedPreferences prefs;
    private BluetoothManager bluetoothManager;
    private BluetoothAdapter adapter;
    private BluetoothProfile a2dpProxy;
    private BluetoothProfile headsetProxy;
    private BluetoothLeScanner scanner;
    private boolean scanning = false;
    private boolean lowLatency = false;
    private boolean outageOpen = false;
    private long lastPublish = 0L;

    private final ScanCallback callback = new ScanCallback() {
        @Override public void onScanResult(int callbackType, ScanResult result) { handleResult(result); }
        @Override public void onBatchScanResults(List<ScanResult> results) {
            for (ScanResult r : results) handleResult(r);
        }
        @Override public void onScanFailed(int errorCode) {
            prefs.edit().putString("status", "SCAN_ERROR").putInt("scanError", errorCode).apply();
            scheduleBalanced(2500L);
            updateNotification();
        }
    };

    @Override public void onCreate() {
        super.onCreate();
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        prefs.edit().putBoolean("serviceRunning", true).apply();

        bluetoothManager = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        adapter = bluetoothManager != null ? bluetoothManager.getAdapter() : null;
        requestClassicProfileProxies();

        createChannel();
        startForeground(NOTIF_ID, notification("Veille Bluetooth active"));
        startScan(ScanSettings.SCAN_MODE_BALANCED);
        handler.post(evaluateRunnable);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
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
        @Override public void run() {
            evaluateLink();
            publishCandidates();
            handler.postDelayed(this, 1000L);
        }
    };

    private void handleResult(ScanResult result) {
        if (result == null || result.getDevice() == null || !hasScanPermission()) return;

        String address;
        String name = "";
        try {
            address = result.getDevice().getAddress();
            if (hasConnectPermission()) {
                String n = result.getDevice().getName();
                if (n != null) name = n;
            }
            if ((name == null || name.isEmpty()) && result.getScanRecord() != null) {
                String advertised = result.getScanRecord().getDeviceName();
                if (advertised != null) name = advertised;
            }
        } catch (SecurityException e) {
            return;
        }

        if (address == null || address.isEmpty()) return;
        long now = System.currentTimeMillis();
        candidates.put(address, new Candidate(address, name == null ? "" : name, result.getRssi(), now));

        String target = prefs.getString("targetMac", "");
        if (target != null && target.equalsIgnoreCase(address)) {
            SharedPreferences.Editor e = prefs.edit()
                .putLong("lastSeenMs", now)
                .putInt("lastRssi", result.getRssi())
                .putString("status", "OK")
                .putInt("scanError", 0);

            String saved = prefs.getString("targetName", "");
            if ((saved == null || saved.isEmpty()) && name != null && !name.isEmpty()) {
                e.putString("targetName", name);
            }

            if (outageOpen) {
                e.putInt("recoveries", prefs.getInt("recoveries", 0) + 1);
                e.putLong("lastRecoveryMs", now);
                outageOpen = false;
                startScan(ScanSettings.SCAN_MODE_BALANCED);
            }
            e.apply();
            updateNotification();
        }

        if (now - lastPublish > 1500L) publishCandidates();
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

        long now = System.currentTimeMillis();
        if (isSystemConnected(target)) {
            SharedPreferences.Editor e = prefs.edit()
                .putString("status", "CONNECTED")
                .putLong("lastSystemConnectedMs", now)
                .putInt("scanError", 0);
            if (outageOpen) {
                e.putInt("recoveries", prefs.getInt("recoveries", 0) + 1)
                    .putLong("lastRecoveryMs", now);
                outageOpen = false;
            }
            e.apply();
            updateNotification();
            return;
        }

        long lastSeen = prefs.getLong("lastSeenMs", 0L);
        long lastSystemConnected = prefs.getLong("lastSystemConnectedMs", 0L);

        if (lastSeen <= 0L) {
            if (lastSystemConnected > 0L && now - lastSystemConnected > LOST_AFTER_MS && !outageOpen) {
                outageOpen = true;
                prefs.edit()
                    .putString("status", "LOST")
                    .putInt("outages", prefs.getInt("outages", 0) + 1)
                    .putLong("lastOutageMs", now)
                    .apply();
                recoveryScan();
                updateNotification();
            } else if (!outageOpen) {
                prefs.edit().putString("status", "SEARCHING").apply();
            }
            return;
        }

        long age = now - lastSeen;
        if (age > LOST_AFTER_MS && !outageOpen) {
            outageOpen = true;
            prefs.edit()
                .putString("status", "LOST")
                .putInt("outages", prefs.getInt("outages", 0) + 1)
                .putLong("lastOutageMs", now)
                .apply();
            recoveryScan();
            updateNotification();
        } else if (age <= LOST_AFTER_MS && !"OK".equals(prefs.getString("status", ""))) {
            prefs.edit().putString("status", "OK").apply();
        }
    }

    private final BluetoothProfile.ServiceListener classicProfileListener = new BluetoothProfile.ServiceListener() {
        @Override public void onServiceConnected(int profile, BluetoothProfile proxy) {
            if (profile == BluetoothProfile.A2DP) a2dpProxy = proxy;
            else if (profile == BluetoothProfile.HEADSET) headsetProxy = proxy;
            handler.post(BleWatchService.this::evaluateLink);
        }

        @Override public void onServiceDisconnected(int profile) {
            if (profile == BluetoothProfile.A2DP) a2dpProxy = null;
            else if (profile == BluetoothProfile.HEADSET) headsetProxy = null;
            handler.post(BleWatchService.this::evaluateLink);
        }
    };

    private void requestClassicProfileProxies() {
        if (adapter == null || !hasConnectPermission()) return;
        try { adapter.getProfileProxy(this, classicProfileListener, BluetoothProfile.A2DP); }
        catch (Exception ignored) {}
        try { adapter.getProfileProxy(this, classicProfileListener, BluetoothProfile.HEADSET); }
        catch (Exception ignored) {}
    }

    private boolean isSystemConnected(String target) {
        if (!hasConnectPermission() || target == null ||
            !BluetoothAdapter.checkBluetoothAddress(target)) return false;

        if (bluetoothManager != null) {
            try {
                List<BluetoothDevice> connected = bluetoothManager.getConnectedDevices(BluetoothProfile.GATT);
                if (containsTarget(connected, target)) return true;
            } catch (SecurityException ignored) {
            } catch (Exception ignored) {}
        }

        try {
            if (a2dpProxy != null && containsTarget(a2dpProxy.getConnectedDevices(), target)) return true;
        } catch (SecurityException ignored) {
        } catch (Exception ignored) {}

        try {
            if (headsetProxy != null && containsTarget(headsetProxy.getConnectedDevices(), target)) return true;
        } catch (SecurityException ignored) {
        } catch (Exception ignored) {}

        return false;
    }

    private boolean containsTarget(List<BluetoothDevice> devices, String target) {
        if (devices == null) return false;
        for (BluetoothDevice d : devices) {
            try {
                if (d != null && target.equalsIgnoreCase(d.getAddress())) return true;
            } catch (SecurityException ignored) {}
        }
        return false;
    }

    private void recoveryScan() {
        startScan(ScanSettings.SCAN_MODE_LOW_LATENCY);
        handler.removeCallbacks(backToBalanced);
        handler.postDelayed(backToBalanced, 8000L);
    }

    private final Runnable backToBalanced = () -> startScan(ScanSettings.SCAN_MODE_BALANCED);

    private void scheduleBalanced(long delayMs) {
        handler.removeCallbacks(backToBalanced);
        handler.postDelayed(backToBalanced, delayMs);
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
            ScanSettings settings = new ScanSettings.Builder().setScanMode(mode).setReportDelay(0L).build();
            List<ScanFilter> filters = Collections.singletonList(new ScanFilter.Builder().build());
            scanner.startScan(filters, settings, callback);
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
        lastPublish = now;

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
        for (int i = 0; i < Math.min(16, list.size()); i++) {
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

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL, "BAZOR Watch", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Surveillance locale des micro-coupures Bluetooth.");
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private Notification notification(String text) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(
            this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL)
            : new Notification.Builder(this);

        return b.setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle("BAZOR Watch")
            .setContentText(text)
            .setContentIntent(pi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build();
    }

    private void updateNotification() {
        String status = prefs.getString("status", "");
        String text;
        if ("OK".equals(status)) text = "Montre détectée • liaison surveillée";
        else if ("CONNECTED".equals(status)) text = "Montre connectée via Android • liaison surveillée";
        else if ("LOST".equals(status)) text = "Micro-coupure • recherche rapide";
        else if ("BT_OFF".equals(status)) text = "Bluetooth désactivé";
        else if ("NO_TARGET".equals(status)) text = "Choisis ta montre dans l'application";
        else text = "Recherche de la montre…";

        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(NOTIF_ID, notification(text));
    }

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        stopScan();
        if (adapter != null) {
            try { if (a2dpProxy != null) adapter.closeProfileProxy(BluetoothProfile.A2DP, a2dpProxy); } catch (Exception ignored) {}
            try { if (headsetProxy != null) adapter.closeProfileProxy(BluetoothProfile.HEADSET, headsetProxy); } catch (Exception ignored) {}
        }
        a2dpProxy = null;
        headsetProxy = null;
        prefs.edit().putBoolean("serviceRunning", false).apply();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }

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
