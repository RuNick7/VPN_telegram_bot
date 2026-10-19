package pro.kairavpn.check;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.telephony.TelephonyManager;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;

/**
 * Keeps the file the check reads the phone's connection from (Go's package
 * phone): what the connection is, whether it is metered, whether a VPN is on,
 * and its DNS servers. A process on Android can find none of it out for
 * itself, so the file is rewritten whenever the system says the connection
 * changed.
 */
final class NetworkWatch extends ConnectivityManager.NetworkCallback {
    private final Context context;
    private final File file;
    private final ConnectivityManager manager;

    NetworkWatch(Context context, File file) {
        this.context = context.getApplicationContext();
        this.file = file;
        this.manager = context.getSystemService(ConnectivityManager.class);
    }

    File file() {
        return file;
    }

    void start() {
        write();
        manager.registerDefaultNetworkCallback(this);
    }

    void stop() {
        try {
            manager.unregisterNetworkCallback(this);
        } catch (IllegalArgumentException alreadyGone) {
            // Never registered, or already let go.
        }
    }

    @Override
    public void onAvailable(Network network) {
        write();
    }

    @Override
    public void onLost(Network network) {
        write();
    }

    @Override
    public void onCapabilitiesChanged(Network network, NetworkCapabilities capabilities) {
        write();
    }

    @Override
    public void onLinkPropertiesChanged(Network network, LinkProperties link) {
        write();
    }

    private synchronized void write() {
        Network active = manager.getActiveNetwork();
        NetworkCapabilities caps = active == null ? null : manager.getNetworkCapabilities(active);
        LinkProperties link = active == null ? null : manager.getLinkProperties(active);

        StringBuilder out = new StringBuilder();
        out.append("network=").append(describe(caps)).append('\n');
        out.append("metered=").append(manager.isActiveNetworkMetered() ? 1 : 0).append('\n');
        boolean vpn = caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
        out.append("vpn=").append(vpn ? 1 : 0).append('\n');
        out.append("dns=");
        if (link != null) {
            String sep = "";
            for (InetAddress server : link.getDnsServers()) {
                out.append(sep).append(server.getHostAddress());
                sep = ",";
            }
        }
        out.append('\n');

        // Whole or not at all: the check may read it at any moment.
        File tmp = new File(file.getPath() + ".tmp");
        try (FileOutputStream stream = new FileOutputStream(tmp)) {
            stream.write(out.toString().getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            Log.w(MainActivity.TAG, "network file: " + e);
            return;
        }
        if (!tmp.renameTo(file)) {
            Log.w(MainActivity.TAG, "network file: rename failed");
        }
    }

    /** The connection as a report names it: "Wi-Fi", "мобильная сеть, MegaFon". */
    private String describe(NetworkCapabilities caps) {
        if (caps == null) {
            return "нет подключения";
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
            return "Wi-Fi";
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
            TelephonyManager phone = context.getSystemService(TelephonyManager.class);
            String operator = phone == null ? "" : phone.getNetworkOperatorName();
            return operator == null || operator.isEmpty() ? "мобильная сеть" : "мобильная сеть, " + operator.replace('\n', ' ');
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
            return "Ethernet";
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) {
            return "VPN";
        }
        return "другая";
    }
}
