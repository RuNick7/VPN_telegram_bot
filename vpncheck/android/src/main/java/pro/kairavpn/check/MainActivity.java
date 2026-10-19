package pro.kairavpn.check;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.Log;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Map;
import java.util.TimeZone;

/**
 * The app's one window. It starts the check (libvpncheck.so, vpncheck-app
 * built for Android) as a process of its own, shows the page that process
 * serves on 127.0.0.1, and does for the page what only an app can: read the
 * clipboard, save a file where the customer picks, and share it.
 */
public final class MainActivity extends Activity {
    static final String TAG = "vpncheck";
    private static final int SAVE_REPORT = 1;
    private static final String GROUND = "#0e1014";

    private WebView web;
    private NetworkWatch network;
    private ClipboardManager clipboard;
    private Process engine;
    // Where the page is served, "http://127.0.0.1:port"; null until it is.
    private String origin;
    private boolean closing;
    // The report waiting for the system's save dialog to answer.
    private String pendingSave;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        if (saved != null) {
            pendingSave = saved.getString("pendingSave");
        }
        // A check takes minutes, and a phone that locks halfway pauses it.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        clipboard = getSystemService(ClipboardManager.class);

        web = new WebView(this);
        web.setBackgroundColor(0xff0e1014);
        setContentView(web);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        // sessionStorage keeps the page's key for a reload.
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        web.addJavascriptInterface(new Bridge(), "KairaAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("kaira".equals(uri.getScheme()) && "restart".equals(uri.getHost())) {
                    startEngine();
                    return true;
                }
                if (isPage(uri)) {
                    return false;
                }
                // «Продлить» and any other link: the browser, never here.
                openOutside(uri);
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (isPage(Uri.parse(url))) {
                    Log.i(TAG, "page loaded");
                }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage message) {
                int level = message.messageLevel() == ConsoleMessage.MessageLevel.ERROR ? Log.ERROR : Log.INFO;
                Log.println(level, TAG, "page: " + message.message() + " (" + message.sourceId() + ":" + message.lineNumber() + ")");
                return true;
            }
        });

        network = new NetworkWatch(this, new File(getFilesDir(), "network"));
        network.start();
        startEngine();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putString("pendingSave", pendingSave);
    }

    @Override
    protected void onDestroy() {
        closing = true;
        stopEngine();
        network.stop();
        web.destroy();
        super.onDestroy();
    }

    // Back leaves the app as Home does: closing it would stop a check.
    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        moveTaskToBack(true);
    }

    private boolean isPage(Uri uri) {
        String url = uri.toString();
        return origin != null && (url.equals(origin) || url.startsWith(origin + "/"));
    }

    private void openOutside(Uri uri) {
        String scheme = uri.getScheme();
        if (!"https".equals(scheme) && !"http".equals(scheme)) {
            return;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException e) {
            toast("Нет браузера, чтобы открыть " + uri);
        }
    }

    // -- the check's process --------------------------------------------------

    private void startEngine() {
        stopEngine();
        origin = null;
        showMessage("Запускаю проверку…", null);

        File program = new File(getApplicationInfo().nativeLibraryDir, "libvpncheck.so");
        ProcessBuilder builder = new ProcessBuilder(program.getPath())
                .directory(getFilesDir())
                .redirectErrorStream(true);
        Map<String, String> env = builder.environment();
        // Where Go looks for the folders it writes to (os.UserCacheDir,
        // os.UserConfigDir, os.TempDir): the app's own.
        env.put("HOME", getFilesDir().getPath());
        env.put("XDG_CONFIG_HOME", getFilesDir().getPath());
        env.put("XDG_CACHE_HOME", getCacheDir().getPath());
        env.put("TMPDIR", getCacheDir().getPath());
        // Go finds no zone on Android by itself; the report's times are local.
        env.put("TZ", TimeZone.getDefault().getID());
        env.put("VPNCHECK_PHONE", network.file().getPath());
        env.put("VPNCHECK_SYSTEM", "Android " + Build.VERSION.RELEASE + ", " + Build.MANUFACTURER + " " + Build.MODEL);
        final Process process;
        try {
            process = builder.start();
        } catch (IOException e) {
            Log.e(TAG, "start: " + e);
            showMessage("Проверка не запустилась.", e.toString());
            return;
        }
        engine = process;
        Thread reader = new Thread(() -> follow(process), "vpncheck");
        reader.setDaemon(true);
        reader.start();
    }

    private void stopEngine() {
        Process process = engine;
        engine = null;
        if (process == null) {
            return;
        }
        // The end of its stdin stops it as surely as the signal does.
        try {
            process.getOutputStream().close();
        } catch (IOException ignored) {
            // Closing is all that is wanted.
        }
        process.destroy();
    }

    /** Reads what the process prints: the page's address first, then its complaints. */
    private void follow(Process process) {
        boolean debuggable = (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        ArrayDeque<String> tail = new ArrayDeque<>();
        try (BufferedReader lines = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            for (String line; (line = lines.readLine()) != null; ) {
                if (line.startsWith("URL ")) {
                    String url = line.substring(4).trim();
                    // The key after # stays out of the log of a release build.
                    Log.i(TAG, "URL " + (debuggable ? url : url.replaceFirst("#.*", "")));
                    runOnUiThread(() -> {
                        if (engine == process) {
                            Uri uri = Uri.parse(url);
                            origin = uri.getScheme() + "://" + uri.getAuthority();
                            web.loadUrl(url);
                        }
                    });
                    continue;
                }
                Log.i(TAG, line);
                tail.addLast(line);
                if (tail.size() > 20) {
                    tail.removeFirst();
                }
            }
        } catch (IOException ignored) {
            // The process went; waitFor says how.
        }
        int code;
        try {
            code = process.waitFor();
        } catch (InterruptedException e) {
            return;
        }
        Log.i(TAG, "exited: " + code);
        String log = TextUtils.join("\n", tail);
        runOnUiThread(() -> {
            if (!closing && engine == process) {
                engine = null;
                origin = null;
                showMessage("Проверка остановилась (код " + code + ").", log);
            }
        });
    }

    /** A page of the app's own: starting up, or the check gone. */
    private void showMessage(String text, String details) {
        StringBuilder html = new StringBuilder()
                .append("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>")
                .append("<body style='background:").append(GROUND)
                .append(";color:#e9ebef;font:16px sans-serif;padding:24px'><p>")
                .append(TextUtils.htmlEncode(text)).append("</p>");
        if (details != null) {
            html.append("<p><a href='kaira://restart' style='color:#ff6a4a'>Запустить снова</a></p>")
                    .append("<pre style='white-space:pre-wrap;color:#8d94a0;font-size:12px'>")
                    .append(TextUtils.htmlEncode(details)).append("</pre>");
        }
        web.loadDataWithBaseURL(null, html.toString(), "text/html", "utf-8", null);
    }

    // -- what the page asks of the phone --------------------------------------

    /** Called by the page's script as KairaAndroid, on a thread of the WebView's. */
    final class Bridge {
        /** The clipboard's text; the check takes only a subscription link out of it. */
        @JavascriptInterface
        public String clipboard() {
            ClipData clip = clipboard == null ? null : clipboard.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) {
                return "";
            }
            CharSequence text = clip.getItemAt(0).coerceToText(MainActivity.this);
            if (text == null) {
                return "";
            }
            // A link is short; whatever else is there is not ours to read.
            return text.length() > 4096 ? text.subSequence(0, 4096).toString() : text.toString();
        }

        @JavascriptInterface
        public void save(String name) {
            runOnUiThread(() -> saveReport(name));
        }

        @JavascriptInterface
        public void share(String name) {
            runOnUiThread(() -> shareReport(name));
        }
    }

    private void saveReport(String name) {
        if (ReportProvider.report(this, name) == null) {
            toast("Отчёта нет: запустите проверку снова.");
            return;
        }
        pendingSave = name;
        Intent pick = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("application/zip")
                .putExtra(Intent.EXTRA_TITLE, name);
        try {
            startActivityForResult(pick, SAVE_REPORT);
        } catch (ActivityNotFoundException e) {
            pendingSave = null;
            toast("Сохранить файл здесь нельзя. Нажмите «Поделиться файлом».");
        }
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        if (request != SAVE_REPORT) {
            super.onActivityResult(request, result, data);
            return;
        }
        String name = pendingSave;
        pendingSave = null;
        File file = ReportProvider.report(this, name);
        if (result != RESULT_OK || data == null || data.getData() == null || file == null) {
            return;
        }
        Uri target = data.getData();
        new Thread(() -> {
            String done = "Отчёт сохранён: " + name;
            try (InputStream in = new FileInputStream(file);
                 OutputStream out = getContentResolver().openOutputStream(target)) {
                if (out == null) {
                    throw new IOException("no stream");
                }
                byte[] buf = new byte[64 * 1024];
                for (int n; (n = in.read(buf)) > 0; ) {
                    out.write(buf, 0, n);
                }
            } catch (IOException e) {
                done = "Не удалось сохранить отчёт: " + e.getMessage();
            }
            String text = done;
            runOnUiThread(() -> toast(text));
        }, "save").start();
    }

    private void shareReport(String name) {
        if (ReportProvider.report(this, name) == null) {
            toast("Отчёта нет: запустите проверку снова.");
            return;
        }
        Uri uri = ReportProvider.uri(this, name);
        Intent send = new Intent(Intent.ACTION_SEND)
                .setType("application/zip")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        send.setClipData(ClipData.newRawUri(name, uri));
        try {
            startActivity(Intent.createChooser(send, "Отправить отчёт"));
        } catch (ActivityNotFoundException e) {
            toast("Нет приложения, чтобы отправить файл.");
        }
    }

    private void toast(String text) {
        Toast.makeText(this, text, Toast.LENGTH_LONG).show();
    }
}
