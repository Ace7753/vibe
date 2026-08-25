package com.example.vibe

import android.Manifest
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ContentValues
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import android.view.View
import android.webkit.URLUtil
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var prefs: SharedPreferences
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(300, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    companion object {
        private const val REQUEST_CODE_PERMISSIONS = 101
        private const val TAG = "VibeApp"
        private const val CHANNEL_ID = "vibe_downloads"
        private const val DEFAULT_URL = "http://10.0.0.228:8080/"
        private const val PREF_KEY_URL = "server_url"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getPreferences(Context.MODE_PRIVATE)
        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)

        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        webView.setBackgroundColor(android.graphics.Color.TRANSPARENT)

        createNotificationChannel()
        checkPermissions()
        setupWebView()
        
        val savedUrl = prefs.getString(PREF_KEY_URL, DEFAULT_URL) ?: DEFAULT_URL
        Log.d(TAG, "Loading Vibe UI: $savedUrl")
        webView.loadUrl(savedUrl)

        // Secret URL Switcher: Long click handler
        // Note: In WebView, we need to handle clicks on the WebView itself or a specific element.
        // For simplicity, we can use a dedicated secret gesture if the user wants.
        // Let's use a long click on the WebView as a fallback.
        webView.setOnLongClickListener {
            showUrlDialog()
            true
        }
    }

    private fun showUrlDialog() {
        val builder = AlertDialog.Builder(this)
        builder.setTitle("Switch Server")
        builder.setMessage("Enter the Cloud URL (e.g., http://vibe-alb-1651997055.us-east-1.elb.amazonaws.com/)")

        val input = EditText(this)
        input.setText(prefs.getString(PREF_KEY_URL, DEFAULT_URL))
        builder.setView(input)

        builder.setPositiveButton("Connect") { _, _ ->
            var newUrl = input.text.toString().trim()
            if (!newUrl.startsWith("http")) newUrl = "http://$newUrl"
            if (!newUrl.endsWith("/")) newUrl = "$newUrl/"
            
            prefs.edit().putString(PREF_KEY_URL, newUrl).apply()
            webView.loadUrl(newUrl)
            Toast.makeText(this, "Connecting to $newUrl", Toast.LENGTH_SHORT).show()
        }
        builder.setNegativeButton("Cancel") { dialog, _ -> dialog.cancel() }
        builder.setNeutralButton("Reset to Local") { _, _ ->
            prefs.edit().putString(PREF_KEY_URL, DEFAULT_URL).apply()
            webView.loadUrl(DEFAULT_URL)
            Toast.makeText(this, "Reset to Local Default", Toast.LENGTH_SHORT).show()
        }

        builder.show()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val name = "Downloads"
            val descriptionText = "Download progress and completion"
            val importance = NotificationManager.IMPORTANCE_LOW
            val channel = NotificationChannel(CHANNEL_ID, name, importance).apply {
                description = descriptionText
            }
            val notificationManager: NotificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun checkPermissions() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            permissions.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }

        val needed = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), REQUEST_CODE_PERMISSIONS)
        }
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            setSupportZoom(true)
            builtInZoomControls = true
            displayZoomControls = false
            loadWithOverviewMode = true
            useWideViewPort = true
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                progressBar.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                if (request?.isForMainFrame == true) {
                    Log.e(TAG, "Connection Error: ${error?.description}")
                    // Show dialog if connection fails, so user can fix URL
                    if (error?.errorCode == -6 || error?.errorCode == -2) { // Connection refused or Name not resolved
                         Toast.makeText(this@MainActivity, "Could not reach server. Long-press screen to change URL.", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progressBar.progress = newProgress
                if (newProgress == 100) progressBar.visibility = View.GONE
            }
        }

        webView.setDownloadListener { url, _, contentDisposition, mimetype, _ ->
            val fileName = URLUtil.guessFileName(url, contentDisposition, mimetype)
            startManualDownload(url, fileName)
        }
    }

    private fun startManualDownload(url: String, fileName: String) {
        Toast.makeText(this, "Starting download...", Toast.LENGTH_SHORT).show()
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notificationBuilder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle(fileName)
            .setContentText("Connecting...")
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setProgress(100, 0, true)

        val notificationId = (System.currentTimeMillis() % 10000).toInt()
        notificationManager.notify(notificationId, notificationBuilder.build())

        CoroutineScope(Dispatchers.IO).launch {
            try {
                Log.d(TAG, "Requesting: $url")
                val request = Request.Builder().url(url).build()
                val response = client.newCall(request).execute()
                
                if (!response.isSuccessful) throw Exception("Server returned ${response.code}")
                
                val body = response.body ?: throw Exception("Empty response body")
                val totalBytes = body.contentLength()
                val inputStream: InputStream = body.byteStream()
                
                val outputStream: OutputStream = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val contentValues = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                        put(MediaStore.MediaColumns.MIME_TYPE, response.header("Content-Type") ?: "application/octet-stream")
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                    }
                    val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                        ?: throw Exception("Failed to create MediaStore entry")
                    contentResolver.openOutputStream(uri) ?: throw Exception("Failed to open output stream")
                } else {
                    val file = java.io.File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), fileName)
                    java.io.FileOutputStream(file)
                }

                val buffer = ByteArray(65536)
                var bytesRead: Int
                var totalRead: Long = 0
                var lastUpdate: Long = 0
                
                outputStream.use { out ->
                    while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                        out.write(buffer, 0, bytesRead)
                        totalRead += bytesRead
                        
                        val now = System.currentTimeMillis()
                        if (now - lastUpdate > 1000 && totalBytes > 0) {
                            val progress = (totalRead * 100 / totalBytes).toInt()
                            notificationBuilder.setProgress(100, progress, false)
                                .setContentText("$progress% Downloaded")
                            notificationManager.notify(notificationId, notificationBuilder.build())
                            lastUpdate = now
                        }
                    }
                }

                withContext(Dispatchers.Main) {
                    notificationBuilder.setContentText("Download Complete")
                        .setSmallIcon(android.R.drawable.stat_sys_download_done)
                        .setOngoing(false)
                        .setProgress(0, 0, false)
                    notificationManager.notify(notificationId, notificationBuilder.build())
                    Toast.makeText(this@MainActivity, "Saved to Downloads", Toast.LENGTH_SHORT).show()
                }

            } catch (e: Exception) {
                Log.e(TAG, "Download Failed: ${e.message}", e)
                withContext(Dispatchers.Main) {
                    notificationBuilder.setContentText("Download Failed: ${e.message}")
                        .setOngoing(false)
                        .setProgress(0, 0, false)
                    notificationManager.notify(notificationId, notificationBuilder.build())
                    Toast.makeText(this@MainActivity, "Error: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
