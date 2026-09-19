package com.bazor.watch;

import android.Manifest;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.AudioDeviceInfo;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.ToneGenerator;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import android.provider.CalendarContract;
import android.provider.Settings;
import android.net.Uri;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class MainActivity extends Activity {
    private static final int REQ_BLE = 5101;
    private static final int REQ_AUDIO = 5102;
    private static final int REQ_CALENDAR = 5103;
    private static final String C28_TEST_CHANNEL = "bazor_c28_relay_test";
    private static final int C28_TEST_NOTIFICATION_ID = 7201;

    private final Handler handler = new Handler(Looper.getMainLooper());

    private SharedPreferences prefs;
    private BluetoothManager bluetoothManager;
    private BluetoothAdapter adapter;
    private BluetoothProfile a2dpProxy;
    private BluetoothProfile headsetProxy;

    private TextView linkState;
    private TextView watchName;
    private TextView linkMetrics;
    private TextView details;
    private TextView securityResult;
    private TextView profileResult;
    private TextView audioResult;
    private TextView versionState;
    private TextView agendaResult;
    private LinearLayout candidatesBox;
    private Button watchToggle;
    private Button agendaToggle;
    private Button updateButton;
    private long latestVersionCode = -1L;
    private String latestApkUrl = "";

    private long revealUntil = 0L;
    private BluetoothGatt activeGatt;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        prefs = getSharedPreferences(BleWatchService.PREFS, MODE_PRIVATE);
        bluetoothManager = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        adapter = bluetoothManager != null ? bluetoothManager.getAdapter() : null;
        requestClassicProfileProxies();

        buildUi();
        ensureBlePermissionsAndStart();
        handler.post(refreshRunnable);
        checkForUpdate(false);
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(7, 17, 31));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(18), dp(16), dp(28));
        scroll.addView(root, new ScrollView.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("⌚ BAZOR Montre", 28, Color.WHITE, true);
        root.addView(title);

        TextView subtitle = text(
            "Montre • signal BLE • sécurité • profils audio", 13,
            Color.rgb(154, 181, 207), false);
        subtitle.setPadding(0, 0, 0, dp(8));
        root.addView(subtitle);

        LinearLayout versionCard = card();
        TextView versionLabel = text("Version " + installedVersionName() + " (" + installedVersionCode() + ")", 13, Color.WHITE, true);
        versionState = text("Vérification GitHub…", 11, Color.rgb(154, 181, 207), false);
        updateButton = button("VÉRIFIER LA MAJ", v -> {
            if (latestVersionCode > installedVersionCode() && latestApkUrl != null && !latestApkUrl.isEmpty()) {
                openUpdateUrl();
            } else {
                checkForUpdate(true);
            }
        });
        versionCard.addView(versionLabel);
        versionCard.addView(versionState);
        versionCard.addView(updateButton);
        root.addView(versionCard);

        LinearLayout statusCard = card();
        linkState = text("Initialisation…", 18, Color.rgb(255, 210, 80), true);
        watchName = text("Aucune montre choisie", 15, Color.WHITE, true);
        linkMetrics = text("—", 12, Color.rgb(154, 181, 207), false);
        statusCard.addView(linkState);
        statusCard.addView(watchName);
        statusCard.addView(linkMetrics);
        root.addView(statusCard);

        LinearLayout row1 = row();
        watchToggle = button("SURVEILLANCE AUTO", v -> toggleWatch());
        Button scan = button("RELANCER BLE", v -> restartBle());
        row1.addView(watchToggle, weight());
        row1.addView(scan, weight());
        root.addView(row1);

        LinearLayout row2 = row();
        Button reveal = button("APPAIRAGE / DÉTAILS", v -> {
            revealUntil = System.currentTimeMillis() + 30_000L;
            refresh();
        });
        Button btSettings = button("RÉGLAGES BT", v -> {
            try { startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)); }
            catch (Exception ignored) {}
        });
        row2.addView(reveal, weight());
        row2.addView(btSettings, weight());
        root.addView(row2);

        details = text("", 12, Color.rgb(182, 207, 230), false);
        details.setVisibility(View.GONE);
        LinearLayout detailCard = card();
        detailCard.addView(details);
        root.addView(detailCard);

        root.addView(section("📅 BAZOR AGENDA"));
        TextView agendaInfo = text(
            "Résumé local de l’agenda Android/Google synchronisé : aujourd’hui le matin, demain le soir. Les notifications peuvent ensuite être relayées à la C28 par Da Fit.",
            12, Color.rgb(154, 181, 207), false);
        root.addView(agendaInfo);

        LinearLayout agendaButtons = row();
        agendaButtons.addView(button("AUJOURD’HUI", v -> showAgendaDay(0)), weight());
        agendaButtons.addView(button("DEMAIN", v -> showAgendaDay(1)), weight());
        root.addView(agendaButtons);

        agendaToggle = button("ACTIVER RAPPELS AGENDA", v -> toggleAgenda());
        root.addView(agendaToggle);

        Button c28Test = button("TESTER LE RELAIS C28", v -> sendC28TestNotification());
        root.addView(c28Test);

        agendaResult = text("Agenda non consulté.", 12, Color.rgb(182, 207, 230), false);
        LinearLayout agendaCard = card();
        agendaCard.addView(agendaResult);
        root.addView(agendaCard);

        root.addView(section("TEST SÉCURITÉ"));
        TextView securityInfo = text(
            "Connexion GATT temporaire et lecture seule : aucun réglage de la montre n’est modifié.",
            12, Color.rgb(154, 181, 207), false);
        root.addView(securityInfo);
        Button security = button("INSPECTER LA CONNEXION", v -> runSecurityTest());
        root.addView(security);
        securityResult = text("Pas encore testé.", 12, Color.rgb(182, 207, 230), false);
        LinearLayout secCard = card();
        secCard.addView(securityResult);
        root.addView(secCard);

        root.addView(section("PROFILS BLUETOOTH / AUDIO"));
        TextView profileInfo = text(
            "Analyse les profils Bluetooth annoncés par la montre et les routes audio Android, sans ouvrir le micro.",
            12, Color.rgb(154, 181, 207), false);
        root.addView(profileInfo);
        Button profiles = button("ANALYSER LES PROFILS", v -> analyzeProfiles());
        root.addView(profiles);
        profileResult = text("Pas encore analysé.", 12, Color.rgb(182, 207, 230), false);
        LinearLayout profileCard = card();
        profileCard.addView(profileResult);
        root.addView(profileCard);

        root.addView(section("TEST MICRO / SON"));
        TextView audioInfo = text(
            "Le test micro dure 2 s, calcule seulement un niveau sonore et ne sauvegarde aucun enregistrement.",
            12, Color.rgb(154, 181, 207), false);
        root.addView(audioInfo);

        LinearLayout audioButtons = row();
        audioButtons.addView(button("TEST MICRO 2 s", v -> testMicrophone()), weight());
        audioButtons.addView(button("TEST SON 0,5 s", v -> testTone()), weight());
        root.addView(audioButtons);

        audioResult = text("Pas encore testé.", 12, Color.rgb(182, 207, 230), false);
        LinearLayout audioCard = card();
        audioCard.addView(audioResult);
        root.addView(audioCard);

        root.addView(section("APPAREILS BLE PROCHES / CONNUS"));
        TextView hint = text(
            "Montre déjà liée à Da Fit ? BAZOR affiche aussi les appareils GATT connectés, appairés Android et routes audio Bluetooth. Choisis ta montre une seule fois.",
            12, Color.rgb(154, 181, 207), false);
        root.addView(hint);

        candidatesBox = new LinearLayout(this);
        candidatesBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(candidatesBox);

        TextView privacy = text(
            "Confidentialité : les diagnostics Bluetooth et audio restent sur le téléphone. Internet sert uniquement à vérifier les mises à jour GitHub.",
            11, Color.rgb(102, 139, 171), false);
        privacy.setPadding(0, dp(18), 0, 0);
        root.addView(privacy);

        setContentView(scroll);
    }

    private LinearLayout card() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(13), dp(12), dp(13), dp(12));
        box.setBackgroundColor(Color.rgb(17, 38, 62));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(8), 0, dp(8));
        box.setLayoutParams(lp);
        return box;
    }

    private LinearLayout row() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setPadding(0, dp(4), 0, dp(4));
        return r;
    }

    private LinearLayout.LayoutParams weight() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        p.setMargins(dp(3), 0, dp(3), 0);
        return p;
    }

    private TextView section(String label) {
        TextView t = text(label, 15, Color.rgb(32, 200, 255), true);
        t.setPadding(0, dp(15), 0, dp(5));
        return t;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
        t.setPadding(0, dp(3), 0, dp(3));
        return t;
    }

    private Button button(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(11);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.rgb(24, 70, 106));
        b.setOnClickListener(listener);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(4), 0, dp(4));
        b.setLayoutParams(lp);
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private long installedVersionCode() {
        try {
            PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0);
            if (Build.VERSION.SDK_INT >= 28) return pi.getLongVersionCode();
            return pi.versionCode;
        } catch (Exception e) {
            return 0L;
        }
    }

    private String installedVersionName() {
        try {
            PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0);
            return pi.versionName == null ? "?" : pi.versionName;
        } catch (Exception e) {
            return "?";
        }
    }

    private void checkForUpdate(boolean manual) {
        if (versionState != null) versionState.setText(manual ? "Vérification GitHub en cours…" : "Vérification GitHub…");
        if (updateButton != null) {
            updateButton.setEnabled(false);
            updateButton.setText("VÉRIFICATION…");
        }

        new Thread(() -> {
            HttpURLConnection con = null;
            try {
                URL url = new URL("https://raw.githubusercontent.com/VincBZH/bazor-mobile/main/watch-update.json");
                con = (HttpURLConnection) url.openConnection();
                con.setConnectTimeout(7000);
                con.setReadTimeout(7000);
                con.setUseCaches(false);
                con.setRequestProperty("User-Agent", "BAZOR-Montre/" + installedVersionName());

                int code = con.getResponseCode();
                if (code < 200 || code >= 300) throw new Exception("HTTP " + code);

                BufferedReader br = new BufferedReader(new InputStreamReader(con.getInputStream()));
                StringBuilder raw = new StringBuilder();
                String line;
                while ((line = br.readLine()) != null) raw.append(line);
                br.close();

                JSONObject json = new JSONObject(raw.toString());
                long remoteCode = json.optLong("versionCode", 0L);
                String remoteName = json.optString("versionName", "?");
                String apk = json.optString("apkUrl", "");
                String notes = json.optString("notes", "");
                latestVersionCode = remoteCode;
                latestApkUrl = apk;

                runOnUiThread(() -> {
                    if (remoteCode > installedVersionCode()) {
                        versionState.setText("MAJ disponible : " + remoteName + (notes.isEmpty() ? "" : " • " + notes));
                        versionState.setTextColor(Color.rgb(255, 210, 80));
                        updateButton.setText("METTRE À JOUR VIA GITHUB");
                    } else {
                        versionState.setText("À jour • GitHub vérifié");
                        versionState.setTextColor(Color.rgb(69, 212, 131));
                        updateButton.setText("VÉRIFIER LA MAJ");
                    }
                    updateButton.setEnabled(true);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    if (versionState != null) {
                        versionState.setText("GitHub indisponible • la montre reste utilisable");
                        versionState.setTextColor(Color.rgb(154, 181, 207));
                    }
                    if (updateButton != null) {
                        updateButton.setEnabled(true);
                        updateButton.setText("RÉESSAYER");
                    }
                });
            } finally {
                if (con != null) con.disconnect();
            }
        }, "bazor-update-check").start();
    }

    private void openUpdateUrl() {
        if (latestApkUrl == null || latestApkUrl.isEmpty()) {
            checkForUpdate(true);
            return;
        }
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(latestApkUrl));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) {
            if (versionState != null) versionState.setText("Impossible d’ouvrir le téléchargement GitHub.");
        }
    }

    private void ensureBlePermissionsAndStart() {
        if (blePermissionsGranted()) {
            startWatchService(null);
            return;
        }

        List<String> perms = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED)
                perms.add(Manifest.permission.BLUETOOTH_SCAN);
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED)
                perms.add(Manifest.permission.BLUETOOTH_CONNECT);
        } else if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            perms.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS);
        }

        requestPermissions(perms.toArray(new String[0]), REQ_BLE);
    }

    private boolean blePermissionsGranted() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_BLE && blePermissionsGranted()) startWatchService(null);
        if (requestCode == REQ_AUDIO &&
            checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            testMicrophone();
        }
        if (requestCode == REQ_CALENDAR && calendarPermissionGranted()) {
            prefs.edit().putBoolean("agendaEnabled", true).apply();
            if (agendaResult != null) agendaResult.setText(loadAgendaSummary(0));
            if (agendaToggle != null) agendaToggle.setText("DÉSACTIVER RAPPELS AGENDA");
        }
    }

    private boolean calendarPermissionGranted() {
        return checkSelfPermission(Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED;
    }

    private void toggleAgenda() {
        boolean enabled = prefs.getBoolean("agendaEnabled", false);
        if (enabled) {
            prefs.edit().putBoolean("agendaEnabled", false).apply();
            if (agendaToggle != null) agendaToggle.setText("ACTIVER RAPPELS AGENDA");
            if (agendaResult != null) agendaResult.setText("Rappels agenda désactivés.");
            return;
        }

        if (!calendarPermissionGranted()) {
            requestPermissions(new String[]{Manifest.permission.READ_CALENDAR}, REQ_CALENDAR);
            return;
        }

        prefs.edit().putBoolean("agendaEnabled", true).apply();
        if (agendaToggle != null) agendaToggle.setText("DÉSACTIVER RAPPELS AGENDA");
        if (agendaResult != null) agendaResult.setText(loadAgendaSummary(0));
    }

    private void sendC28TestNotification() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_BLE);
            if (agendaResult != null) {
                agendaResult.setText("Autorise les notifications puis relance TESTER LE RELAIS C28.");
            }
            return;
        }

        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) {
            if (agendaResult != null) agendaResult.setText("Service de notifications Android indisponible.");
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                C28_TEST_CHANNEL, "BAZOR vers C28", NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("Notifications de test et rappels destinés au relais vers la montre.");
            channel.enableVibration(true);
            nm.createNotificationChannel(channel);
        }

        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(
            this, C28_TEST_NOTIFICATION_ID, open,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, C28_TEST_CHANNEL)
            : new Notification.Builder(this).setPriority(Notification.PRIORITY_HIGH);

        Notification n = b
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle("BAZOR TEST C28")
            .setContentText("Si ce message apparaît sur la montre, le relais Da Fit fonctionne.")
            .setStyle(new Notification.BigTextStyle().bigText(
                "BAZOR TEST C28 — Si ce message apparaît sur la montre, le relais Da Fit fonctionne."))
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build();

        nm.notify(C28_TEST_NOTIFICATION_ID, n);

        boolean skypeRelay = relayToC28(
            "BAZOR TEST C28",
            "Si ce message apparaît sur la montre, le relais Skype/Da Fit fonctionne.");

        if (agendaResult != null) {
            agendaResult.setText(skypeRelay
                ? "Test envoyé par BAZOR + canal Skype de compatibilité. Dans Da Fit, active Skype dans les applications de notifications si nécessaire."
                : "Test BAZOR envoyé, mais le relais Skype de compatibilité n’est pas installé.");
        }
    }

    private boolean relayToC28(String title, String text) {
        try {
            getPackageManager().getPackageInfo("com.skype.raider", 0);
            Intent relay = new Intent("com.bazor.montre.RELAY_TO_C28");
            relay.setPackage("com.skype.raider");
            relay.putExtra("title", title == null ? "BAZOR" : title);
            relay.putExtra("text", text == null ? "" : text);
            sendBroadcast(relay);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private void showAgendaDay(int dayOffset) {
        if (!calendarPermissionGranted()) {
            requestPermissions(new String[]{Manifest.permission.READ_CALENDAR}, REQ_CALENDAR);
            if (agendaResult != null) agendaResult.setText("Autorise l’accès au calendrier pour afficher l’agenda.");
            return;
        }
        if (agendaResult != null) agendaResult.setText(loadAgendaSummary(dayOffset));
    }

    private String loadAgendaSummary(int dayOffset) {
        if (!calendarPermissionGranted()) return "Autorisation calendrier requise.";

        Calendar start = Calendar.getInstance();
        start.add(Calendar.DAY_OF_YEAR, dayOffset);
        start.set(Calendar.HOUR_OF_DAY, 0);
        start.set(Calendar.MINUTE, 0);
        start.set(Calendar.SECOND, 0);
        start.set(Calendar.MILLISECOND, 0);

        Calendar end = (Calendar) start.clone();
        end.add(Calendar.DAY_OF_YEAR, 1);

        String[] projection = new String[] {
            CalendarContract.Instances.TITLE,
            CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.ALL_DAY,
            CalendarContract.Instances.EVENT_LOCATION
        };

        StringBuilder out = new StringBuilder(dayOffset == 0 ? "AUJOURD’HUI" : "DEMAIN");
        int count = 0;
        SimpleDateFormat timeFmt = new SimpleDateFormat("HH:mm", Locale.FRANCE);

        try (Cursor cursor = CalendarContract.Instances.query(
            getContentResolver(), projection, start.getTimeInMillis(), end.getTimeInMillis())) {
            if (cursor != null) {
                int titleCol = cursor.getColumnIndex(CalendarContract.Instances.TITLE);
                int beginCol = cursor.getColumnIndex(CalendarContract.Instances.BEGIN);
                int allDayCol = cursor.getColumnIndex(CalendarContract.Instances.ALL_DAY);
                int locCol = cursor.getColumnIndex(CalendarContract.Instances.EVENT_LOCATION);

                while (cursor.moveToNext() && count < 8) {
                    String title = titleCol >= 0 ? cursor.getString(titleCol) : "";
                    long begin = beginCol >= 0 ? cursor.getLong(beginCol) : 0L;
                    boolean allDay = allDayCol >= 0 && cursor.getInt(allDayCol) != 0;
                    String location = locCol >= 0 ? cursor.getString(locCol) : "";

                    if (title == null || title.trim().isEmpty()) title = "(Sans titre)";
                    out.append("\n• ")
                        .append(allDay ? "Journée" : timeFmt.format(begin))
                        .append(" — ").append(title.trim());
                    if (location != null && !location.trim().isEmpty()) {
                        out.append(" · ").append(location.trim());
                    }
                    count++;
                }
            }
        } catch (Exception e) {
            return "Agenda indisponible : " +
                (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
        }

        if (count == 0) out.append("\nRien de prévu.");
        else if (count >= 8) out.append("\n…");
        return out.toString();
    }

    private void startWatchService(String action) {
        Intent i = new Intent(this, BleWatchService.class);
        if (action != null) i.setAction(action);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i);
            else startService(i);
        } catch (Exception e) {
            showAudioOrSecurity("Impossible de démarrer la veille BLE : " + e.getMessage(), false);
        }
    }

    private void toggleWatch() {
        boolean enabled = prefs.getBoolean("enabled", true);
        if (enabled) {
            prefs.edit().putBoolean("enabled", false).apply();
            Intent i = new Intent(this, BleWatchService.class);
            i.setAction(BleWatchService.ACTION_STOP);
            try { startService(i); } catch (Exception ignored) { stopService(i); }
        } else {
            prefs.edit().putBoolean("enabled", true).apply();
            ensureBlePermissionsAndStart();
        }
        handler.postDelayed(this::refresh, 500L);
    }

    private void restartBle() {
        if (!blePermissionsGranted()) {
            ensureBlePermissionsAndStart();
            return;
        }
        startWatchService(BleWatchService.ACTION_RESTART_SCAN);
        refresh();
    }

    private final Runnable refreshRunnable = new Runnable() {
        @Override public void run() {
            refresh();
            handler.postDelayed(this, 1500L);
        }
    };

    private void refresh() {
        String status = prefs.getString("status", "STARTING");
        String targetMac = prefs.getString("targetMac", "");
        String targetName = prefs.getString("targetName", "");
        long lastSeen = prefs.getLong("lastSeenMs", 0L);
        int rssi = prefs.getInt("lastRssi", -127);
        int outages = prefs.getInt("outages", 0);
        int recoveries = prefs.getInt("recoveries", 0);
        boolean enabled = prefs.getBoolean("enabled", true);
        boolean fast = prefs.getBoolean("lowLatency", false);

        int color = Color.rgb(255, 210, 80);
        String label = "RECHERCHE…";
        if ("OK".equals(status)) { label = "DÉTECTÉE"; color = Color.rgb(69, 212, 131); }
        else if ("CONNECTED".equals(status)) { label = "CONNECTÉE VIA ANDROID"; color = Color.rgb(69, 212, 131); }
        else if ("LOST".equals(status)) { label = "SIGNAL BLE ABSENT"; color = Color.rgb(255, 107, 107); }
        else if ("BT_OFF".equals(status)) { label = "BLUETOOTH COUPÉ"; color = Color.rgb(255, 107, 107); }
        else if ("PERMISSION".equals(status)) { label = "AUTORISATION REQUISE"; color = Color.rgb(255, 107, 107); }
        else if ("SCAN_ERROR".equals(status)) { label = "SCAN À RELANCER"; color = Color.rgb(255, 107, 107); }
        else if ("NO_TARGET".equals(status)) label = "CHOISIS LA MONTRE";

        linkState.setText(label);
        linkState.setTextColor(color);
        watchName.setText(targetName == null || targetName.isEmpty()
            ? (targetMac == null || targetMac.isEmpty() ? "Aucune montre choisie" : "Montre sélectionnée")
            : targetName);

        String seen = lastSeen <= 0 ? "jamais" :
            Math.max(0, (System.currentTimeMillis() - lastSeen) / 1000L) + " s";
        String presence = "CONNECTED".equals(status) ? "liaison Android active" : "vue " + seen;
        linkMetrics.setText(
            "RSSI " + (rssi > -120 ? rssi + " dBm" : "—") +
            " • " + presence +
            " • pertes signal " + outages +
            " • reprises " + recoveries +
            (fast ? " • relance rapide" : ""));

        watchToggle.setText(enabled ? "ARRÊTER LA VEILLE" : "ACTIVER LA VEILLE");
        if (agendaToggle != null) {
            agendaToggle.setText(prefs.getBoolean("agendaEnabled", false)
                ? "DÉSACTIVER RAPPELS AGENDA"
                : "ACTIVER RAPPELS AGENDA");
        }

        boolean revealed = System.currentTimeMillis() < revealUntil;
        details.setVisibility(revealed ? View.VISIBLE : View.GONE);
        if (revealed) {
            String bond = bondText(targetMac);
            details.setText(
                (targetMac == null || targetMac.isEmpty()
                    ? "Aucune montre sélectionnée."
                    : "Bluetooth : " + targetMac + "\nNom : " + (targetName == null ? "" : targetName) + "\n" + bond));
        }

        renderCandidates(targetMac);
    }

    private void renderCandidates(String targetMac) {
        candidatesBox.removeAllViews();
        LinkedHashMap<String, DeviceRow> rows = new LinkedHashMap<>();

        String raw = prefs.getString("candidates", "[]");
        try {
            JSONArray arr = new JSONArray(raw);
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o == null) continue;
                mergeDevice(rows,
                    o.optString("mac", ""),
                    o.optString("name", ""),
                    o.optInt("rssi", -127),
                    true, false, false);
            }
        } catch (Exception ignored) {}

        addSystemKnownDevices(rows);

        if (rows.isEmpty()) {
            candidatesBox.addView(text(
                "Aucun appareil BLE visible ou connu pour le moment. Da Fit peut conserver une liaison privée non exposée par Android.",
                12, Color.rgb(154, 181, 207), false));
            return;
        }

        for (DeviceRow row : rows.values()) {
            boolean selected = row.mac.equalsIgnoreCase(targetMac == null ? "" : targetMac);
            StringBuilder source = new StringBuilder();
            if (row.connectedGatt) source.append("connecté GATT");
            if (row.connectedClassic) {
                if (source.length() > 0) source.append(" • ");
                source.append("connecté Android");
                if (row.a2dp || row.headset) {
                    source.append(" (");
                    if (row.a2dp) source.append("A2DP");
                    if (row.a2dp && row.headset) source.append("+");
                    if (row.headset) source.append("HFP");
                    source.append(")");
                }
            }
            if (row.bonded) {
                if (source.length() > 0) source.append(" • ");
                source.append("appairé Android");
            }
            if (row.audio) {
                if (source.length() > 0) source.append(" • ");
                source.append("audio BT");
            }
            if (row.seenByScan) {
                if (source.length() > 0) source.append(" • ");
                source.append("scan BLE");
            }

            String signal = row.seenByScan && row.rssi > -120 ? " • " + row.rssi + " dBm" : "";
            Button b = button(
                (selected ? "✓ " : "⌚ ") +
                (row.name.isEmpty() ? "Appareil Bluetooth" : row.name) +
                "\n" + maskMac(row.mac) + signal +
                (source.length() == 0 ? "" : "\n" + source),
                v -> selectTarget(row.mac, row.name));
            if (selected) b.setBackgroundColor(Color.rgb(15, 102, 117));
            else if (row.connectedGatt || row.connectedClassic) b.setBackgroundColor(Color.rgb(20, 88, 74));
            candidatesBox.addView(b);
        }
    }

    private final BluetoothProfile.ServiceListener classicProfileListener = new BluetoothProfile.ServiceListener() {
        @Override public void onServiceConnected(int profile, BluetoothProfile proxy) {
            if (profile == BluetoothProfile.A2DP) a2dpProxy = proxy;
            else if (profile == BluetoothProfile.HEADSET) headsetProxy = proxy;
            handler.post(MainActivity.this::refresh);
        }

        @Override public void onServiceDisconnected(int profile) {
            if (profile == BluetoothProfile.A2DP) a2dpProxy = null;
            else if (profile == BluetoothProfile.HEADSET) headsetProxy = null;
            handler.post(MainActivity.this::refresh);
        }
    };

    private void requestClassicProfileProxies() {
        if (adapter == null || !blePermissionsGranted()) return;
        try { adapter.getProfileProxy(this, classicProfileListener, BluetoothProfile.A2DP); }
        catch (Exception ignored) {}
        try { adapter.getProfileProxy(this, classicProfileListener, BluetoothProfile.HEADSET); }
        catch (Exception ignored) {}
    }

    private void addSystemKnownDevices(LinkedHashMap<String, DeviceRow> rows) {
        if (adapter == null || !blePermissionsGranted()) return;

        if (bluetoothManager != null) {
            try {
                List<BluetoothDevice> connected = bluetoothManager.getConnectedDevices(BluetoothProfile.GATT);
                if (connected != null) {
                    for (BluetoothDevice d : connected) {
                        mergeBluetoothDevice(rows, d, true, false);
                    }
                }
            } catch (Exception ignored) {}
        }

        addClassicConnectedDevices(rows, a2dpProxy, true, false);
        addClassicConnectedDevices(rows, headsetProxy, false, true);

        try {
            for (BluetoothDevice d : adapter.getBondedDevices()) {
                mergeBluetoothDevice(rows, d, false, true);
            }
        } catch (Exception ignored) {}

        try {
            AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (am != null) {
                addAudioDevices(rows, am.getDevices(AudioManager.GET_DEVICES_INPUTS));
                addAudioDevices(rows, am.getDevices(AudioManager.GET_DEVICES_OUTPUTS));
                if (Build.VERSION.SDK_INT >= 31) {
                    for (AudioDeviceInfo d : am.getAvailableCommunicationDevices()) {
                        addAudioDevice(rows, d);
                    }
                }
            }
        } catch (Exception ignored) {}
    }

    private void addClassicConnectedDevices(LinkedHashMap<String, DeviceRow> rows,
                                            BluetoothProfile proxy,
                                            boolean a2dp, boolean headset) {
        if (proxy == null || !blePermissionsGranted()) return;
        try {
            List<BluetoothDevice> devices = proxy.getConnectedDevices();
            if (devices == null) return;
            for (BluetoothDevice d : devices) {
                if (d == null) continue;
                String mac = d.getAddress();
                String name = d.getName();
                DeviceRow row = mergeDevice(rows, mac, name == null ? "" : name,
                    -127, false, false, false);
                if (row != null) {
                    row.connectedClassic = true;
                    row.a2dp = row.a2dp || a2dp;
                    row.headset = row.headset || headset;
                }
            }
        } catch (SecurityException ignored) {
        } catch (Exception ignored) {}
    }

    private void mergeBluetoothDevice(LinkedHashMap<String, DeviceRow> rows, BluetoothDevice device,
                                      boolean connectedGatt, boolean bonded) {
        if (device == null) return;
        try {
            String mac = device.getAddress();
            String name = device.getName();
            mergeDevice(rows, mac, name == null ? "" : name, -127, false, connectedGatt, bonded);
        } catch (SecurityException ignored) {}
    }

    private void addAudioDevices(LinkedHashMap<String, DeviceRow> rows, AudioDeviceInfo[] devices) {
        if (devices == null) return;
        for (AudioDeviceInfo d : devices) addAudioDevice(rows, d);
    }

    private void addAudioDevice(LinkedHashMap<String, DeviceRow> rows, AudioDeviceInfo d) {
        if (d == null || !isBluetoothType(d.getType()) || Build.VERSION.SDK_INT < 28) return;
        try {
            String mac = d.getAddress();
            if (!BluetoothAdapter.checkBluetoothAddress(mac)) return;
            String name = d.getProductName() == null ? "" : d.getProductName().toString();
            DeviceRow row = mergeDevice(rows, mac, name, -127, false, false, false);
            if (row != null) row.audio = true;
        } catch (Exception ignored) {}
    }

    private DeviceRow mergeDevice(LinkedHashMap<String, DeviceRow> rows, String mac, String name, int rssi,
                                  boolean seenByScan, boolean connectedGatt, boolean bonded) {
        if (mac == null || !BluetoothAdapter.checkBluetoothAddress(mac)) return null;
        String key = mac.toUpperCase(Locale.ROOT);
        DeviceRow row = rows.get(key);
        if (row == null) {
            row = new DeviceRow(key);
            rows.put(key, row);
        }
        if (name != null && !name.trim().isEmpty()) row.name = name.trim();
        if (seenByScan) {
            row.seenByScan = true;
            row.rssi = rssi;
        }
        row.connectedGatt = row.connectedGatt || connectedGatt;
        row.bonded = row.bonded || bonded;
        return row;
    }

    private static class DeviceRow {
        final String mac;
        String name = "";
        int rssi = -127;
        boolean seenByScan;
        boolean connectedGatt;
        boolean connectedClassic;
        boolean a2dp;
        boolean headset;
        boolean bonded;
        boolean audio;

        DeviceRow(String mac) { this.mac = mac; }
    }

    private void selectTarget(String mac, String name) {
        if (!BluetoothAdapter.checkBluetoothAddress(mac)) return;
        prefs.edit()
            .putString("targetMac", mac.toUpperCase(Locale.ROOT))
            .putString("targetName", name == null ? "" : name)
            .putLong("lastSeenMs", 0L)
            .putInt("outages", 0)
            .putInt("recoveries", 0)
            .putString("status", "SEARCHING")
            .apply();
        startWatchService(BleWatchService.ACTION_RESTART_SCAN);
        refresh();
    }

    private String maskMac(String mac) {
        if (mac == null || mac.length() < 5) return "masqué";
        return "••:••:••:••:" + mac.substring(mac.length() - 5);
    }

    private String bondText(String mac) {
        if (mac == null || mac.isEmpty() || adapter == null || !blePermissionsGranted()) return "Appairage : inconnu";
        try {
            BluetoothDevice d = adapter.getRemoteDevice(mac);
            int s = d.getBondState();
            if (s == BluetoothDevice.BOND_BONDED) return "Appairage Android : OUI";
            if (s == BluetoothDevice.BOND_BONDING) return "Appairage Android : EN COURS";
            return "Appairage Android : NON";
        } catch (Exception e) {
            return "Appairage Android : inconnu";
        }
    }

    private void runSecurityTest() {
        String mac = prefs.getString("targetMac", "");
        if (mac == null || mac.isEmpty()) {
            securityResult.setText("Choisis d’abord la montre.");
            return;
        }
        if (!blePermissionsGranted()) {
            securityResult.setText("Autorisation Bluetooth requise.");
            ensureBlePermissionsAndStart();
            return;
        }

        securityResult.setText("Connexion GATT temporaire… aucune lecture/écriture de données.");
        try {
            BluetoothDevice device = adapter.getRemoteDevice(mac);
            if (activeGatt != null) {
                try { activeGatt.close(); } catch (Exception ignored) {}
                activeGatt = null;
            }
            activeGatt = device.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
        } catch (Exception e) {
            securityResult.setText("Test GATT impossible : " + e.getMessage());
        }
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                try { gatt.discoverServices(); }
                catch (SecurityException e) { finishGatt(gatt, "Permission Bluetooth refusée."); }
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    finishGatt(gatt, "Connexion GATT refusée/fermée • code " + status +
                        ". Da Fit peut déjà occuper la liaison ; ce test n’insiste pas.");
                } else {
                    closeGatt(gatt);
                }
            }
        }

        @Override public void onServicesDiscovered(BluetoothGatt gatt, int status) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                finishGatt(gatt, "Services GATT non accessibles • code " + status);
                return;
            }

            int services = 0;
            int chars = 0;
            int readable = 0;
            int writable = 0;
            int notify = 0;
            int encrypted = 0;
            int mitm = 0;

            for (BluetoothGattService s : gatt.getServices()) {
                services++;
                for (BluetoothGattCharacteristic c : s.getCharacteristics()) {
                    chars++;
                    int props = c.getProperties();
                    int perms = c.getPermissions();

                    if ((props & BluetoothGattCharacteristic.PROPERTY_READ) != 0) readable++;
                    if ((props & (BluetoothGattCharacteristic.PROPERTY_WRITE |
                        BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE)) != 0) writable++;
                    if ((props & (BluetoothGattCharacteristic.PROPERTY_NOTIFY |
                        BluetoothGattCharacteristic.PROPERTY_INDICATE)) != 0) notify++;

                    if ((perms & (BluetoothGattCharacteristic.PERMISSION_READ_ENCRYPTED |
                        BluetoothGattCharacteristic.PERMISSION_WRITE_ENCRYPTED)) != 0) encrypted++;
                    if ((perms & (BluetoothGattCharacteristic.PERMISSION_READ_ENCRYPTED_MITM |
                        BluetoothGattCharacteristic.PERMISSION_WRITE_ENCRYPTED_MITM |
                        BluetoothGattCharacteristic.PERMISSION_WRITE_SIGNED_MITM)) != 0) mitm++;
                }
            }

            String mac = prefs.getString("targetMac", "");
            String report =
                bondText(mac) +
                "\nServices : " + services + " • caractéristiques : " + chars +
                "\nLecture : " + readable + " • écriture possible : " + writable + " • notifications : " + notify +
                "\nPermissions GATT marquées chiffrement : " + encrypted +
                "\nPermissions GATT marquées MITM : " + mitm +
                "\nImportant : 0 ici ne prouve PAS que la liaison radio est non chiffrée ; ces compteurs décrivent seulement les permissions déclarées par les caractéristiques." +
                "\nAucune valeur GATT n’a été lue ou écrite.";

            finishGatt(gatt, report);
        }
    };

    private void finishGatt(BluetoothGatt gatt, String text) {
        runOnUiThread(() -> securityResult.setText(text));
        try { gatt.disconnect(); } catch (Exception ignored) {}
        handler.postDelayed(() -> closeGatt(gatt), 300L);
    }

    private void closeGatt(BluetoothGatt gatt) {
        try { gatt.close(); } catch (Exception ignored) {}
        if (gatt == activeGatt) activeGatt = null;
    }

    private void analyzeProfiles() {
        String mac = prefs.getString("targetMac", "");
        if (mac == null || mac.isEmpty()) {
            profileResult.setText("Choisis d’abord la montre.");
            return;
        }
        if (!blePermissionsGranted()) {
            profileResult.setText("Autorisation Bluetooth requise.");
            ensureBlePermissionsAndStart();
            return;
        }

        try {
            BluetoothDevice d = adapter.getRemoteDevice(mac);
            StringBuilder out = new StringBuilder();
            out.append(bondText(mac)).append("\n");

            ParcelUuid[] uuids = d.getUuids();
            boolean hfp = false, hsp = false, a2dpSink = false, a2dpSource = false;
            if (uuids != null && uuids.length > 0) {
                out.append("Profils/UUID connus : ").append(uuids.length).append("\n");
                for (ParcelUuid p : uuids) {
                    String u = p.getUuid().toString().toLowerCase(Locale.ROOT);
                    String label = uuidLabel(u);
                    if (u.startsWith("0000111e-")) hfp = true;
                    if (u.startsWith("00001108-")) hsp = true;
                    if (u.startsWith("0000110b-")) a2dpSink = true;
                    if (u.startsWith("0000110a-")) a2dpSource = true;
                    if (!label.isEmpty()) out.append("• ").append(label).append("\n");
                }
            } else {
                out.append("Profils classiques : non disponibles dans le cache Android.\n");
            }

            AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
            AudioDeviceInfo btIn = findBluetoothInput(am);
            AudioDeviceInfo btOut = findBluetoothCommunicationOutput(am);

            out.append("Micro Bluetooth visible par Android : ")
                .append(btIn == null ? "NON" : "OUI • " + deviceLabel(btIn)).append("\n");
            out.append("Sortie communication Bluetooth : ")
                .append(btOut == null ? "NON" : "OUI • " + deviceLabel(btOut)).append("\n");

            if (hfp || hsp) {
                out.append("Téléphonie/micro potentiel : profil ")
                    .append(hfp ? "HFP" : "HSP")
                    .append(" annoncé, mais Android ne l’expose pas forcément tant qu’un appel/flux voix n’est pas actif.\n");
            } else {
                out.append("Téléphonie/micro potentiel : aucun profil HFP/HSP actuellement annoncé dans le cache.\n");
            }

            if (a2dpSink || a2dpSource) {
                out.append("Audio média : ")
                    .append(a2dpSink ? "réception A2DP " : "")
                    .append(a2dpSource ? "émission A2DP" : "")
                    .append(".\n");
            } else {
                out.append("Audio média : aucun profil A2DP identifié dans le cache.\n");
            }

            out.append("Conclusion : le BLE de données et l’audio Bluetooth sont deux chemins distincts.");
            profileResult.setText(out.toString());
        } catch (Exception e) {
            profileResult.setText("Analyse des profils impossible : " +
                (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
        }
    }

    private String uuidLabel(String u) {
        if (u.startsWith("0000111e-")) return "HFP Hands-Free (voix/appels)";
        if (u.startsWith("0000111f-")) return "HFP Audio Gateway";
        if (u.startsWith("00001108-")) return "Headset HSP";
        if (u.startsWith("0000110b-")) return "A2DP Audio Sink";
        if (u.startsWith("0000110a-")) return "A2DP Audio Source";
        if (u.startsWith("0000110c-")) return "AVRCP Target";
        if (u.startsWith("0000110e-")) return "AVRCP";
        if (u.startsWith("00001800-")) return "GAP BLE";
        if (u.startsWith("00001801-")) return "GATT BLE";
        if (u.startsWith("0000180a-")) return "Device Information";
        if (u.startsWith("0000180f-")) return "Battery Service";
        return "";
    }

    private void testMicrophone() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
            return;
        }

        audioResult.setText("Test micro 2 s… aucun son n’est sauvegardé.");
        new Thread(() -> {
            AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
            AudioDeviceInfo input = findBluetoothInput(am);
            AudioDeviceInfo commOut = findBluetoothCommunicationOutput(am);
            boolean commSelected = false;
            AudioRecord rec = null;

            try {
                am.setMode(AudioManager.MODE_IN_COMMUNICATION);
                if (Build.VERSION.SDK_INT >= 31 && commOut != null) {
                    commSelected = am.setCommunicationDevice(commOut);
                }

                int sampleRate = 16000;
                int min = AudioRecord.getMinBufferSize(
                    sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
                int buffer = Math.max(min, sampleRate);

                AudioRecord.Builder builder = new AudioRecord.Builder()
                    .setAudioSource(MediaRecorder.AudioSource.VOICE_COMMUNICATION)
                    .setAudioFormat(new AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(sampleRate)
                        .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                        .build())
                    .setBufferSizeInBytes(buffer);

                if (Build.VERSION.SDK_INT >= 30) builder.setPrivacySensitive(true);
                rec = builder.build();
                if (input != null) rec.setPreferredDevice(input);

                rec.startRecording();
                short[] data = new short[1024];
                long until = System.currentTimeMillis() + 2000L;
                double sumSq = 0.0;
                long samples = 0;
                int peak = 0;

                while (System.currentTimeMillis() < until) {
                    int n = rec.read(data, 0, data.length);
                    if (n > 0) {
                        for (int i = 0; i < n; i++) {
                            int v = Math.abs((int) data[i]);
                            peak = Math.max(peak, v);
                            sumSq += (double) v * v;
                        }
                        samples += n;
                    }
                }

                AudioDeviceInfo routed = rec.getRoutedDevice();
                double rms = samples > 0 ? Math.sqrt(sumSq / samples) : 0.0;
                int percent = (int) Math.min(100, Math.round((rms / 32767.0) * 250.0));

                boolean bluetoothRoute = routed != null && isBluetoothType(routed.getType());
                String result =
                    "Entrée réellement utilisée : " + deviceLabel(routed) +
                    "\nRoute Bluetooth : " + (bluetoothRoute ? "OUI" : "NON") +
                    "\nNiveau détecté : " + percent + "% • pic " + peak +
                    "\nSortie communication Bluetooth : " + (commOut == null ? "non trouvée" :
                        deviceLabel(commOut) + (commSelected ? " • sélectionnée" : " • détectée")) +
                    "\nAucun audio sauvegardé ni transmis.";

                runOnUiThread(() -> audioResult.setText(result));
            } catch (Exception e) {
                String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                runOnUiThread(() -> audioResult.setText(
                    "Test micro impossible : " + msg +
                    "\nLe téléphone peut voir la montre en BLE sans exposer son micro aux applications."));
            } finally {
                if (rec != null) {
                    try { rec.stop(); } catch (Exception ignored) {}
                    try { rec.release(); } catch (Exception ignored) {}
                }
                if (Build.VERSION.SDK_INT >= 31) {
                    try { am.clearCommunicationDevice(); } catch (Exception ignored) {}
                }
                try { am.setMode(AudioManager.MODE_NORMAL); } catch (Exception ignored) {}
            }
        }).start();
    }

    private void testTone() {
        AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
        AudioDeviceInfo out = findBluetoothCommunicationOutput(am);
        if (out == null) {
            audioResult.setText("Aucune sortie Bluetooth de communication disponible pour le test son.");
            return;
        }

        try {
            am.setMode(AudioManager.MODE_IN_COMMUNICATION);
            boolean selected = Build.VERSION.SDK_INT < 31 || am.setCommunicationDevice(out);
            if (!selected) {
                audioResult.setText("La sortie Bluetooth est visible mais Android refuse de la sélectionner.");
                am.setMode(AudioManager.MODE_NORMAL);
                return;
            }

            ToneGenerator tg = new ToneGenerator(AudioManager.STREAM_VOICE_CALL, 30);
            tg.startTone(ToneGenerator.TONE_PROP_BEEP, 500);
            audioResult.setText("Bip envoyé vers : " + deviceLabel(out) + "\nVolume de test limité.");
            handler.postDelayed(() -> {
                try { tg.release(); } catch (Exception ignored) {}
                if (Build.VERSION.SDK_INT >= 31) {
                    try { am.clearCommunicationDevice(); } catch (Exception ignored) {}
                }
                try { am.setMode(AudioManager.MODE_NORMAL); } catch (Exception ignored) {}
            }, 800L);
        } catch (Exception e) {
            audioResult.setText("Test son impossible : " + e.getMessage());
        }
    }

    private AudioDeviceInfo findBluetoothInput(AudioManager am) {
        String targetName = prefs.getString("targetName", "").toLowerCase(Locale.ROOT);
        AudioDeviceInfo fallback = null;
        for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_INPUTS)) {
            if (!isBluetoothType(d.getType())) continue;
            if (fallback == null) fallback = d;
            String label = deviceLabel(d).toLowerCase(Locale.ROOT);
            if (!targetName.isEmpty() && label.contains(targetName)) return d;
        }
        return fallback;
    }

    private AudioDeviceInfo findBluetoothCommunicationOutput(AudioManager am) {
        String targetName = prefs.getString("targetName", "").toLowerCase(Locale.ROOT);

        if (Build.VERSION.SDK_INT >= 31) {
            AudioDeviceInfo fallback = null;
            for (AudioDeviceInfo d : am.getAvailableCommunicationDevices()) {
                if (!isBluetoothType(d.getType())) continue;
                if (fallback == null) fallback = d;
                String label = deviceLabel(d).toLowerCase(Locale.ROOT);
                if (!targetName.isEmpty() && label.contains(targetName)) return d;
            }
            if (fallback != null) return fallback;
        }

        AudioDeviceInfo fallback = null;
        for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            if (!isBluetoothType(d.getType())) continue;
            if (fallback == null) fallback = d;
            String label = deviceLabel(d).toLowerCase(Locale.ROOT);
            if (!targetName.isEmpty() && label.contains(targetName)) return d;
        }
        return fallback;
    }

    private boolean isBluetoothType(int type) {
        if (type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
            type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP) return true;
        if (Build.VERSION.SDK_INT >= 31 &&
            (type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
             type == AudioDeviceInfo.TYPE_BLE_SPEAKER ||
             type == AudioDeviceInfo.TYPE_BLE_BROADCAST)) return true;
        return false;
    }

    private String deviceLabel(AudioDeviceInfo d) {
        if (d == null) return "aucune";
        String name = d.getProductName() == null ? "Bluetooth" : d.getProductName().toString();
        String addr = "";
        if (Build.VERSION.SDK_INT >= 28) {
            try { addr = d.getAddress(); } catch (Exception ignored) {}
        }
        return name + (addr == null || addr.isEmpty() ? "" : " • " + maskMac(addr));
    }

    private void showAudioOrSecurity(String msg, boolean audio) {
        if (audio && audioResult != null) audioResult.setText(msg);
        else if (securityResult != null) securityResult.setText(msg);
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (adapter != null) {
            try { if (a2dpProxy != null) adapter.closeProfileProxy(BluetoothProfile.A2DP, a2dpProxy); } catch (Exception ignored) {}
            try { if (headsetProxy != null) adapter.closeProfileProxy(BluetoothProfile.HEADSET, headsetProxy); } catch (Exception ignored) {}
        }
        a2dpProxy = null;
        headsetProxy = null;
        if (activeGatt != null) {
            try { activeGatt.disconnect(); } catch (Exception ignored) {}
            try { activeGatt.close(); } catch (Exception ignored) {}
            activeGatt = null;
        }
        super.onDestroy();
    }
}
