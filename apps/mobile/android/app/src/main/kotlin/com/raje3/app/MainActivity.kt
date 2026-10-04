package com.raje3.app

import com.google.android.play.core.assetpacks.AssetPackManagerFactory
import com.google.android.play.core.assetpacks.AssetPackState
import com.google.android.play.core.assetpacks.model.AssetPackStatus
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

/**
 * Bridges android/ai_model_pack — a Play Asset Delivery install-time pack — to Dart. See that
 * module's own build.gradle.kts, and lib/core/ai/adapters/gemma_ai_model.dart, for why the model
 * moved out of a plain Flutter asset (Google Play's 200MB base-module cap) and into a real
 * on-device file path this class resolves at runtime instead.
 *
 * TWO CHANNELS, ONE JOB EACH — a MethodChannel for the one-shot "give me the real path" call
 * ([ensureAiModelPack]), an EventChannel for the progress stream the Dart side already renders
 * (the exact shape `GemmaAiModel.downloadProgress` expects, unchanged by this move).
 */
class MainActivity : FlutterActivity() {
    private val packName = "ai_model_pack"
    private val methodChannelName = "raje3/ai_model_pack"
    private val progressChannelName = "raje3/ai_model_pack/progress"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val assetPackManager = AssetPackManagerFactory.getInstance(applicationContext)
        var progressSink: EventChannel.EventSink? = null

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, progressChannelName)
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, sink: EventChannel.EventSink) {
                    progressSink = sink
                }
                override fun onCancel(arguments: Any?) {
                    progressSink = null
                }
            })

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, methodChannelName)
            .setMethodCallHandler { call, result ->
                if (call.method != "ensureInstalled") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }

                // ALREADY THERE, THE COMMON CASE — install-time delivery means Play already
                // staged this pack alongside the base app before the user ever opened it; this
                // returns immediately without ever registering a listener or calling fetch().
                val existingPath = assetPackManager.getPackLocation(packName)?.assetsPath()
                if (existingPath != null) {
                    result.success("$existingPath/gemma-4-E4B-it-gpu.litertlm")
                    return@setMethodCallHandler
                }

                // NOT YET STAGED — a fresh install caught mid-sync, or a local/debug run outside
                // Play's own install pipeline (install-time packs are not pre-staged by
                // `flutter run`). fetch() is safe to call even when Play would have delivered it
                // anyway; it is a no-op once COMPLETED.
                lateinit var listener: (AssetPackState) -> Unit
                listener = { state ->
                    if (state.name() == packName) {
                        when (state.status()) {
                            AssetPackStatus.DOWNLOADING, AssetPackStatus.TRANSFERRING -> {
                                val total = state.totalBytesToDownload()
                                val pct = if (total > 0)
                                    ((100.0 * state.bytesDownloaded()) / total).toInt()
                                else 0
                                progressSink?.success(pct)
                            }
                            AssetPackStatus.COMPLETED -> {
                                assetPackManager.unregisterListener(listener)
                                val path = assetPackManager.getPackLocation(packName)?.assetsPath()
                                if (path != null) {
                                    result.success("$path/gemma-4-E4B-it-gpu.litertlm")
                                } else {
                                    result.error(
                                        "ai_model_pack_missing",
                                        "pack reported COMPLETED but has no location",
                                        null
                                    )
                                }
                            }
                            AssetPackStatus.FAILED, AssetPackStatus.CANCELED -> {
                                assetPackManager.unregisterListener(listener)
                                result.error(
                                    "ai_model_pack_failed",
                                    "asset pack delivery failed: status=${state.status()} " +
                                        "errorCode=${state.errorCode()}",
                                    null
                                )
                            }
                            else -> { /* PENDING, NOT_INSTALLED, WAITING_FOR_WIFI — no signal yet */ }
                        }
                    }
                }
                assetPackManager.registerListener(listener)
                assetPackManager.fetch(listOf(packName))
            }
    }
}
