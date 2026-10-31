package com.hestia.desk;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.webkit.CookieManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    static final String DESK = "https://hestia.trading/";
    static final String HOST = Uri.parse(DESK).getHost();
    // shortcut: fixed home address of the Umbrel, used when hestia.trading does not answer
    static final String HOME = "http://192.168.68.78:18080/";
    static final String HOME_HOST = Uri.parse(HOME).getHost();

    // Cloudflare Access signs in on the team's cloudflareaccess.com page, which has to stay inside the app.
    static boolean inApp(String host) {
        return host != null && (host.equals(HOST) || host.equals(HOME_HOST) || host.endsWith("." + HOST) || host.endsWith(".cloudflareaccess.com"));
    }

    static final String OFFLINE = "<!DOCTYPE html><html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
            + "<style>body{margin:0;min-height:100vh;display:flex;flex-direction:column;justify-content:center;padding:2rem;"
            + "background:#0a1021;color:#f2e2c9;font:16px/1.5 sans-serif}h1{font:500 1.6rem serif;margin:0 0 .5rem}"
            + "p{color:#a9b4c7;margin:0 0 1.5rem}button{min-height:48px;border:0;border-radius:6px;background:#ff4d2e;"
            + "color:#0a1021;font:600 1rem sans-serif}</style></head><body><h1>Hestia is out of reach</h1>"
            + "<p>Neither hestia.trading nor the Umbrel on the home Wi-Fi answered. Check that the phone is online and the Umbrel is running, then try again.</p>"
            + "<button onclick=\"location.href='" + DESK + "'\">Try again</button></body></html>";

    private WebView web;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0a1021"));
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setSupportMultipleWindows(false);
        // The site reads this to offer an app update when the server holds a newer APK.
        settings.setUserAgentString(settings.getUserAgentString() + " HestiaApp/" + versionCode());
        web.setDownloadListener((url, userAgent, disposition, mime, length) -> download(url, mime));
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (inApp(uri.getHost())) {
                    return false;
                }
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) {
                    return;
                }
                if (HOST.equals(request.getUrl().getHost())) {
                    view.loadUrl(HOME);
                } else {
                    view.loadDataWithBaseURL(DESK, OFFLINE, "text/html", "utf-8", DESK);
                }
            }
        });
        setContentView(web);
        if (state == null || web.restoreState(state) == null) {
            web.loadUrl(DESK);
        }
    }

    @SuppressWarnings("deprecation")
    private int versionCode() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
        } catch (PackageManager.NameNotFoundException e) {
            return 0;
        }
    }

    // Downloads with the Cloudflare Access cookie; tapping the finished notification opens the installer.
    private void download(String url, String mime) {
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
        String cookie = CookieManager.getInstance().getCookie(url);
        if (cookie != null) {
            request.addRequestHeader("Cookie", cookie);
        }
        request.setMimeType(mime);
        request.setTitle("Hestia update");
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, "hestia-" + System.currentTimeMillis() + ".apk");
        ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
