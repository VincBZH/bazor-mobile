package com.bazor.skyperelay;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

public class RelayReceiver extends BroadcastReceiver {
    private static final String CHANNEL = "messages";
    private static final int ID = 28001;

    @Override public void onReceive(Context context, Intent intent) {
        if (intent == null || !"com.bazor.montre.RELAY_TO_C28".equals(intent.getAction())) return;

        String title = intent.getStringExtra("title");
        String text = intent.getStringExtra("text");
        if (title == null || title.trim().isEmpty()) title = "BAZOR";
        if (text == null) text = "";

        NotificationManager nm =
            (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL, "Messages", NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("Relais local BAZOR vers la C28 via le canal Skype de Da Fit.");
            channel.enableVibration(true);
            nm.createNotificationChannel(channel);
        }

        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(context, CHANNEL)
            : new Notification.Builder(context).setPriority(Notification.PRIORITY_HIGH);

        Notification n = b
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(text.replace("\n", " • "))
            .setStyle(new Notification.BigTextStyle().bigText(text))
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setAutoCancel(true)
            .build();

        nm.notify(ID, n);
    }
}
