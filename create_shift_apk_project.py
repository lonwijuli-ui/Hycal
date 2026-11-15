#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
4조 3교대 최신 근무달력 앱 & 위젯 프로젝트 통합 생성기
================================================================================
[최신 업데이트 내용]
1. Kotlin 컴파일러 데몬 에러(Daemon compilation failed) 원천 차단
2. 날짜 더블탭(Double Tap) 메모 팝업 및 다크/라이트 모드 지원
3. 공휴일 특근 자동 표시 및 안드로이드 홈 위젯 완벽 연동
================================================================================
"""

import os
import sys
from pathlib import Path


def write_text_file(base_dir: Path, relative_path: str, content: str) -> None:
    """지정한 경로에 UTF-8 텍스트 파일을 안전하게 생성합니다."""
    target = base_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"[생성 완료] {relative_path}")


def build_project_files() -> dict:
    """안드로이드 앱, 홈 위젯, 최신 웹뷰 UI, Gradle 및 GitHub APK 자동 빌드 파일을 구성합니다."""
    files = {}

    # -------------------------------------------------------------------------
    # 1. GitHub Actions 자동 APK 빌드 설정
    # -------------------------------------------------------------------------
    files[".github/workflows/build-apk.yml"] = """
name: Build Modern Shift Calendar APK

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v3
        with:
          gradle-version: '8.5'

      - name: Build Debug APK
        run: gradle assembleDebug --no-daemon

      - name: Upload APK Artifact
        uses: actions/upload-artifact@v4
        with:
          name: 4조3교대_최신달력_위젯_APK
          path: app/build/outputs/apk/debug/app-debug.apk
"""

    # -------------------------------------------------------------------------
    # 2. Gradle 설정 파일들 (버전 호환성 완벽 고정)
    # -------------------------------------------------------------------------
    files["settings.gradle.kts"] = """
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "ModernShiftCalendar"
include(":app")
"""

    files["build.gradle.kts"] = """
plugins {
    id("com.android.application") version "8.3.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
}
"""

    files["gradle.properties"] = """
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
"""

    files["app/proguard-rules.pro"] = """
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
"""

    files["app/build.gradle.kts"] = """
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.shiftcalendar.modern"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.shiftcalendar.modern"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
}
"""

    # -------------------------------------------------------------------------
    # 3. AndroidManifest.xml
    # -------------------------------------------------------------------------
    files["app/src/main/AndroidManifest.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher"
        android:supportsRtl="true"
        android:theme="@style/Theme.ShiftCalendar">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <receiver
            android:name=".ShiftWidgetSmallProvider"
            android:exported="true"
            android:label="@string/widget_small_name">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
                <action android:name="com.shiftcalendar.modern.ACTION_CYCLE_TEAM" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/widget_small_info" />
        </receiver>

    </application>
</manifest>
"""

    # -------------------------------------------------------------------------
    # 4. Kotlin: ShiftCalculator.kt
    # -------------------------------------------------------------------------
    files["app/src/main/java/com/shiftcalendar/modern/ShiftCalculator.kt"] = """
package com.shiftcalendar.modern

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import org.json.JSONObject
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

object ShiftCalculator {

    private const val PREFS_NAME = "shift_calendar_prefs"
    private val DATE_FMT: DateTimeFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    const val DEFAULT_TEAM = 4
    const val DEFAULT_DIRECTION = "FORWARD"
    const val DEFAULT_ANCHOR_DATE = "2026-11-15"
    const val DEFAULT_ANCHOR_TEAM1_INDEX = 16
    const val DEFAULT_TIME_A = "07:00~15:00"
    const val DEFAULT_TIME_B = "15:00~23:00"
    const val DEFAULT_TIME_C = "23:00~07:00"

    data class ShiftStep(
        val code: String,
        val label: String,
        val shortLabel: String,
        val dayInBlock: Int,
        val blockTotal: Int,
        val isWork: Boolean,
        val cycleIndex: Int,
        val timeRange: String
    )

    data class HolidayInfo(
        val isHoliday: Boolean,
        val holidayName: String
    )

    data class DayAnalysis(
        val date: LocalDate,
        val dateStr: String,
        val dayName: String,
        val shift: ShiftStep,
        val holiday: HolidayInfo,
        val isSpecialWork: Boolean,
        val memo: String
    )

    private val PUBLIC_HOLIDAYS: Map<String, String> = mapOf(
        "2025-01-01" to "신정", "2025-01-27" to "설날 연휴", "2025-01-28" to "설날", "2025-01-29" to "설날 연휴", "2025-01-30" to "설날 연휴",
        "2025-03-01" to "삼일절", "2025-03-03" to "대체공휴일", "2025-05-01" to "노동절", "2025-05-05" to "어린이날",
        "2025-06-06" to "현충일", "2025-08-15" to "광복절", "2025-10-03" to "개천절", "2025-10-05" to "추석 연휴",
        "2025-10-06" to "추석", "2025-10-07" to "추석 연휴", "2025-10-08" to "추석 연휴", "2025-10-09" to "한글날", "2025-12-25" to "성탄절",
        "2026-01-01" to "신정", "2026-02-16" to "설날 연휴", "2026-02-17" to "설날", "2026-02-18" to "설날 연휴", "2026-02-19" to "설날 연휴",
        "2026-03-01" to "삼일절", "2026-03-02" to "대체공휴일", "2026-05-01" to "노동절", "2026-05-05" to "어린이날",
        "2026-05-25" to "대체공휴일", "2026-06-06" to "현충일", "2026-08-15" to "광복절", "2026-08-17" to "대체공휴일",
        "2026-09-24" to "추석 연휴", "2026-09-25" to "추석", "2026-09-26" to "추석 연휴", "2026-09-27" to "추석 연휴",
        "2026-10-03" to "개천절", "2026-10-05" to "대체공휴일", "2026-10-09" to "한글날", "2026-12-25" to "성탄절",
        "2027-01-01" to "신정", "2027-02-06" to "설날 연휴", "2027-02-07" to "설날", "2027-02-08" to "설날 연휴", "2027-02-09" to "설날 연휴",
        "2027-03-01" to "삼일절", "2027-05-01" to "노동절", "2027-05-05" to "어린이날", "2027-06-06" to "현충일",
        "2027-08-15" to "광복절", "2027-09-14" to "추석 연휴", "2027-09-15" to "추석", "2027-09-16" to "추석 연휴", "2027-09-17" to "추석 연휴",
        "2027-10-03" to "개천절", "2027-10-09" to "한글날", "2027-12-25" to "성탄절"
    )

    fun loadConfig(context: Context): JSONObject {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("app_state_json", "") ?: ""
        return if (jsonStr.isNotEmpty()) {
            try { JSONObject(jsonStr) } catch (e: Exception) { getDefaultJson() }
        } else {
            getDefaultJson()
        }
    }

    fun saveConfig(context: Context, jsonStr: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString("app_state_json", jsonStr).apply()
        notifyWidgets(context)
    }

    private fun getDefaultJson(): JSONObject {
        val root = JSONObject()
        root.put("selectedTeam", DEFAULT_TEAM)
        root.put("direction", DEFAULT_DIRECTION)
        root.put("anchorDateStr", DEFAULT_ANCHOR_DATE)
        root.put("anchorTeam1Index", DEFAULT_ANCHOR_TEAM1_INDEX)
        root.put("timeA", DEFAULT_TIME_A)
        root.put("timeB", DEFAULT_TIME_B)
        root.put("timeC", DEFAULT_TIME_C)
        root.put("userOverrides", JSONObject())
        return root
    }

    fun notifyWidgets(context: Context) {
        val manager = AppWidgetManager.getInstance(context)
        val ids = manager.getAppWidgetIds(ComponentName(context, ShiftWidgetSmallProvider::class.java))
        if (ids.isNotEmpty()) {
            val intent = Intent(context, ShiftWidgetSmallProvider::class.java).apply {
                action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
            }
            context.sendBroadcast(intent)
        }
    }

    fun getShiftForTeam(json: JSONObject, teamNum: Int, targetDate: LocalDate): ShiftStep {
        val dir = json.optString("direction", DEFAULT_DIRECTION)
        val anchorDateStr = json.optString("anchorDateStr", DEFAULT_ANCHOR_DATE)
        val anchorTeam1Idx = json.optInt("anchorTeam1Index", DEFAULT_ANCHOR_TEAM1_INDEX)
        val tA = json.optString("timeA", DEFAULT_TIME_A)
        val tB = json.optString("timeB", DEFAULT_TIME_B)
        val tC = json.optString("timeC", DEFAULT_TIME_C)

        val anchorDate = try { LocalDate.parse(anchorDateStr, DATE_FMT) } catch (e: Exception) { LocalDate.parse(DEFAULT_ANCHOR_DATE, DATE_FMT) }
        val deltaDays = ChronoUnit.DAYS.between(anchorDate, targetDate).toInt()
        val teamOffset = ((teamNum - 1) * 6) % 24
        val rawIdx = (anchorTeam1Idx + teamOffset + deltaDays) % 24
        val cycleIdx = (rawIdx + 24) % 24

        val order = if (dir == "REVERSE") listOf("C", "B", "A") else listOf("A", "B", "C")
        val blockIdx = cycleIdx / 8
        val posInBlock = cycleIdx % 8
        val shiftCode = order[blockIdx]

        return if (posInBlock < 6) {
            ShiftStep(
                code = shiftCode,
                label = when(shiftCode) { "A" -> "A 주간"; "B" -> "B 오후"; else -> "C 야간" },
                shortLabel = shiftCode,
                dayInBlock = posInBlock + 1,
                blockTotal = 6,
                isWork = true,
                cycleIndex = cycleIdx,
                timeRange = when(shiftCode) { "A" -> tA; "B" -> tB; else -> tC }
            )
        } else {
            ShiftStep(
                code = "OFF",
                label = "휴무",
                shortLabel = "휴",
                dayInBlock = posInBlock - 5,
                blockTotal = 2,
                isWork = false,
                cycleIndex = cycleIdx,
                timeRange = "전일 휴식"
            )
        }
    }

    fun getHolidayInfo(json: JSONObject, dateStr: String): HolidayInfo {
        try {
            val overrides = json.optJSONObject("userOverrides")
            if (overrides != null && overrides.has(dateStr)) {
                val item = overrides.getJSONObject(dateStr)
                if (item.optBoolean("disableHoliday", false)) return HolidayInfo(false, "")
            }
        } catch (_: Exception) {}

        val builtIn = PUBLIC_HOLIDAYS[dateStr]
        return if (builtIn != null) HolidayInfo(true, builtIn) else HolidayInfo(false, "")
    }

    fun analyzeDate(json: JSONObject, teamNum: Int, date: LocalDate): DayAnalysis {
        val dateStr = date.format(DATE_FMT)
        val shift = getShiftForTeam(json, teamNum, date)
        val holiday = getHolidayInfo(json, dateStr)
        val isSpecialWork = holiday.isHoliday && shift.isWork

        var memo = ""
        try {
            val overrides = json.optJSONObject("userOverrides")
            if (overrides != null && overrides.has(dateStr)) {
                memo = overrides.getJSONObject(dateStr).optString("memo", "")
            }
        } catch (_: Exception) {}

        val dowName = when (date.dayOfWeek) {
            DayOfWeek.SUNDAY -> "일"
            DayOfWeek.MONDAY -> "월"
            DayOfWeek.TUESDAY -> "화"
            DayOfWeek.WEDNESDAY -> "수"
            DayOfWeek.THURSDAY -> "목"
            DayOfWeek.FRIDAY -> "금"
            DayOfWeek.SATURDAY -> "토"
        }

        return DayAnalysis(date, dateStr, dowName, shift, holiday, isSpecialWork, memo)
    }
}
"""

    # -------------------------------------------------------------------------
    # 5. Kotlin: ShiftWidgetSmallProvider.kt
    # -------------------------------------------------------------------------
    files["app/src/main/java/com/shiftcalendar/modern/ShiftWidgetSmallProvider.kt"] = """
package com.shiftcalendar.modern

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import java.time.LocalDate

class ShiftWidgetSmallProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        val json = ShiftCalculator.loadConfig(context)
        val team = json.optInt("selectedTeam", 4)
        val today = LocalDate.now()
        val todayInfo = ShiftCalculator.analyzeDate(json, team, today)

        for (id in ids) {
            val views = RemoteViews(context.packageName, R.layout.widget_small)
            views.setTextViewText(R.id.tvSmallTitle, "${team}조 근무 정보")
            views.setTextViewText(R.id.tvSmallShift, "${todayInfo.shift.label} (${todayInfo.shift.dayInBlock}일차)")
            views.setTextViewText(R.id.tvSmallTime, todayInfo.shift.timeRange)

            val openIntent = PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            views.setOnClickPendingIntent(R.id.widgetSmallRoot, openIntent)

            manager.updateAppWidget(id, views)
        }
    }
}
"""

    # -------------------------------------------------------------------------
    # 6. Kotlin: MainActivity.kt
    # -------------------------------------------------------------------------
    files["app/src/main/java/com/shiftcalendar/modern/MainActivity.kt"] = """
package com.shiftcalendar.modern

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = true
            webChromeClient = WebChromeClient()
            webViewClient = WebViewClient()
            addJavascriptInterface(AndroidBridge(), "AndroidBridge")
        }
        setContentView(webView)
        webView.loadUrl("file:///android_asset/index.html")
    }

    inner class AndroidBridge {
        @JavascriptInterface
        fun getInitialStateJson(): String = ShiftCalculator.loadConfig(this@MainActivity).toString()

        @JavascriptInterface
        fun saveStateJson(jsonStr: String) = ShiftCalculator.saveConfig(this@MainActivity, jsonStr)
    }
}
"""

    # -------------------------------------------------------------------------
    # 7. Android 자원 및 레이아웃 XML
    # -------------------------------------------------------------------------
    files["app/src/main/res/values/strings.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">4조3교대 달력</string>
    <string name="widget_small_name">4조3교대 위젯</string>
</resources>
"""

    files["app/src/main/res/values/styles.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.ShiftCalendar" parent="Theme.AppCompat.Light.NoActionBar">
        <item name="android:statusBarColor">#0F172A</item>
        <item name="android:navigationBarColor">#FFFFFF</item>
    </style>
</resources>
"""

    files["app/src/main/res/xml/widget_small_info.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:initialLayout="@layout/widget_small"
    android:minWidth="140dp"
    android:minHeight="110dp"
    android:targetCellWidth="2"
    android:targetCellHeight="2"
    android:resizeMode="horizontal|vertical"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
"""

    files["app/src/main/res/layout/widget_small.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/widgetSmallRoot"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="#FFFFFF"
    android:orientation="vertical"
    android:padding="12dp">
    <TextView
        android:id="@+id/tvSmallTitle"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="4조 근무 정보"
        android:textColor="#4F46E5"
        android:textSize="12sp"
        android:textStyle="bold" />
    <TextView
        android:id="@+id/tvSmallShift"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="8dp"
        android:text="B 오후 (3일차)"
        android:textColor="#0F172A"
        android:textSize="16sp"
        android:textStyle="bold" />
    <TextView
        android:id="@+id/tvSmallTime"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="4dp"
        android:text="15:00~23:00"
        android:textColor="#64748B"
        android:textSize="11sp" />
</LinearLayout>
"""

    files["app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
</adaptive-icon>
"""

    files["app/src/main/res/drawable/ic_launcher_background.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#4F46E5" android:pathData="M0,0h108v108h-108z" />
</vector>
"""

    files["app/src/main/res/drawable/ic_launcher_foreground.xml"] = """
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#FFFFFF" android:pathData="M30,28h48c3.3,0 6,2.7 6,6v42c0,3.3 -2.7,6 -6,6H30c-3.3,0 -6,-2.7 -6,-6V34C24,30.7 26.7,28 30,28zM30,42v34h48V42H30z" />
</vector>
"""

    # -------------------------------------------------------------------------
    # 8. 최신 웹뷰 UI: app/src/main/assets/index.html
    # -------------------------------------------------------------------------
    files["app/src/main/assets/index.html"] = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>4조 3교대 근무달력</title>
  <style>
    :root {
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #0f172a;
      --sub: #64748b;
      --border: #e2e8f0;
      --blue: #2563eb;
      --amber: #d97706;
      --indigo: #4f46e5;
      --emerald: #059669;
      --rose: #e11d48;
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Noto Sans KR", sans-serif;
      background: var(--bg); color: var(--text); padding-bottom: 32px;
    }
    header {
      position: sticky; top: 0; z-index: 20;
      background: rgba(255,255,255,0.88);
      backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border); padding: 12px 16px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .brand { display: flex; align-items: center; gap: 10px; }
    .logo {
      width: 38px; height: 38px; border-radius: 14px;
      background: linear-gradient(135deg, #4f46e5, #2563eb);
      color: #fff; font-weight: 900; font-size: 13px;
      display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(79,70,229,0.3);
    }
    h1 { font-size: 16px; font-weight: 800; letter-spacing: -0.3px; }
    .sub-txt { font-size: 11px; color: var(--sub); font-weight: 500; margin-top: 1px; }
    .btn-sm {
      border: 1px solid #c7d2fe; background: #eef2ff; color: var(--indigo);
      font-size: 12px; font-weight: 800; padding: 7px 12px; border-radius: 12px; cursor: pointer;
    }
    main { max-width: 640px; margin: 0 auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
    .card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: 22px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .banner { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .big-shift { font-size: 22px; font-weight: 900; margin: 3px 0; letter-spacing: -0.5px; }
    .badge-sp {
      display: inline-block; background: var(--rose); color: #fff;
      font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 6px; box-shadow: 0 1px 3px rgba(225,29,72,0.3);
    }
    .stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
    .stat-item {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 9px 4px; text-align: center;
    }
    .stat-item.sp { background: #fff1f2; border-color: #fecdd3; }
    .stat-lbl { font-size: 11px; font-weight: 800; }
    .stat-val { font-size: 16px; font-weight: 900; margin-top: 2px; }
    .cal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
    .nav-grp { display: flex; align-items: center; gap: 6px; }
    .nav-btn {
      border: 1px solid var(--border); background: var(--bg); color: var(--text);
      width: 34px; height: 34px; border-radius: 12px; font-weight: 900; cursor: pointer;
    }
    .today-btn {
      border: 1px solid var(--border); background: var(--bg); color: var(--text);
      padding: 7px 11px; border-radius: 12px; font-size: 12px; font-weight: 800; cursor: pointer;
    }
    .dow-row, .days-grid { display: grid; grid-template-columns: repeat(7, 1fr); }
    .dow-row { text-align: center; font-size: 11px; font-weight: 800; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
    .day-cell {
      min-height: 88px; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border);
      padding: 5px 3px; display: flex; flex-direction: column; justify-content: space-between;
      background: var(--card); text-align: left; cursor: pointer; user-select: none;
    }
    .day-cell.selected { outline: 2px solid var(--indigo); outline-offset: -2px; background: #eef2ff !important; }
    .day-cell.dim { opacity: 0.35; }
    .day-top { display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 800; }
    .today-dot {
      background: var(--indigo); color: #fff; width: 20px; height: 20px; border-radius: 10px;
      display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(79,70,229,0.3);
    }
    .hol-name { font-size: 9px; color: var(--rose); font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .memo-tag { font-size: 9px; color: var(--indigo); background: #eef2ff; padding: 1px 4px; border-radius: 4px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 1px; border: 1px solid #c7d2fe; }
    
    .shift-circle-box { display: flex; justify-content: center; align-items: center; margin: auto 0; padding: 2px 0; }
    .shift-circle {
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 900; color: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .circle-A { background: var(--blue); }
    .circle-B { background: var(--amber); }
    .circle-C { background: var(--indigo); }
    .circle-OFF { background: #ecfdf5; color: var(--emerald); border: 1px solid #a7f3d0; width: auto; height: auto; border-radius: 10px; padding: 2px 8px; font-size: 11px; }

    input[type="text"], input[type="date"], select {
      flex: 1; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--border);
      font-size: 12px; font-weight: 700; background: var(--bg); color: var(--text);
    }
    .btn-primary { border: none; background: var(--indigo); color: #fff; padding: 10px 14px; border-radius: 12px; font-size: 12px; font-weight: 800; box-shadow: 0 2px 6px rgba(79,70,229,0.3); cursor: pointer; }
    .hidden { display: none !important; }
    .modal-bg {
      position: fixed; inset: 0; background: rgba(15,23,42,0.6); z-index: 50;
      display: flex; align-items: center; justify-content: center; padding: 16px; backdrop-filter: blur(4px);
    }
    .modal-card {
      background: var(--card); color: var(--text); border-radius: 24px; padding: 20px; width: 100%; max-width: 420px;
      display: flex; flex-direction: column; gap: 12px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
      border: 1px solid var(--border);
    }
    .toast {
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      background: #0f172a; color: #fff; padding: 10px 18px; border-radius: 14px;
      font-size: 12px; font-weight: 800; z-index: 60; opacity: 0; transition: opacity 0.2s; pointer-events: none;
    }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <header id="mainHeader">
    <div class="brand">
      <div class="logo">4조</div>
      <div>
        <h1>4조 3교대 근무달력</h1>
        <div class="sub-txt">6근 2휴 · 공휴일 특근표시</div>
      </div>
    </div>
    <button id="openSettingsBtn" class="btn-sm" type="button">⚙️ 설정</button>
  </header>

  <main>
    <section id="calView" style="display:flex; flex-direction:column; gap:12px;">
      <!-- 상단 배너 -->
      <div id="todayCard" class="card banner"></div>

      <!-- 달력 본문 -->
      <div class="card" style="padding:12px 8px;">
        <div class="cal-head" style="padding:0 6px;">
          <div class="nav-grp">
            <button id="prevBtn" class="nav-btn" type="button">&lt;</button>
            <strong id="monthLbl" style="font-size:16px; min-width:110px; text-align:center;">2026년 11월</strong>
            <button id="nextBtn" class="nav-btn" type="button">&gt;</button>
          </div>
          <button id="todayBtn" class="today-btn" type="button">오늘</button>
        </div>
        <div class="dow-row">
          <div style="color:var(--rose);">일</div><div>월</div><div>화</div><div>수</div><div>목</div><div>금</div><div style="color:var(--blue);">토</div>
        </div>
        <div id="daysGrid" class="days-grid"></div>
      </div>

      <!-- 월간 근무 통계 창 -->
      <div class="stats-grid">
        <div class="stat-item"><div class="stat-lbl" style="color:var(--blue);">A 주간</div><div id="stA" class="stat-val">0일</div></div>
        <div class="stat-item"><div class="stat-lbl" style="color:var(--amber);">B 오후</div><div id="stB" class="stat-val">0일</div></div>
        <div class="stat-item"><div class="stat-lbl" style="color:var(--indigo);">C 야간</div><div id="stC" class="stat-val">0일</div></div>
        <div class="stat-item"><div class="stat-lbl" style="color:var(--emerald);">휴무</div><div id="stOff" class="stat-val">0일</div></div>
        <div class="stat-item sp"><div class="stat-lbl" style="color:var(--rose);">특근</div><div id="stSp" class="stat-val" style="color:var(--rose);">0일</div></div>
      </div>

      <!-- 1, 2, 3, 4조 조 변경 버튼 -->
      <div class="card" style="padding: 12px;">
        <div class="sub-txt" style="margin-bottom: 6px;">나의 조 선택</div>
        <div id="teamSeg" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; background: #e2e8f0; padding: 4px; border-radius: 14px;">
          <button class="seg-btn" data-team="1" type="button" style="border:none; background:transparent; padding:8px 4px; border-radius:10px; font-size:12px; font-weight:800; color:#475569; cursor:pointer;">1조</button>
          <button class="seg-btn" data-team="2" type="button" style="border:none; background:transparent; padding:8px 4px; border-radius:10px; font-size:12px; font-weight:800; color:#475569; cursor:pointer;">2조</button>
          <button class="seg-btn" data-team="3" type="button" style="border:none; background:transparent; padding:8px 4px; border-radius:10px; font-size:12px; font-weight:800; color:#475569; cursor:pointer;">3조</button>
          <button class="seg-btn active" data-team="4" type="button" style="border:none; background:#fff; padding:8px 4px; border-radius:10px; font-size:12px; font-weight:800; color:var(--indigo); box-shadow:0 1px 3px rgba(0,0,0,0.08); cursor:pointer;">4조</button>
        </div>
      </div>
    </section>
  </main>

  <!-- 날짜 더블탭 메모 팝업 모달 -->
  <div id="memoModal" class="modal-bg hidden">
    <div class="modal-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <strong id="modalMemoTitle" style="font-size:15px;">날짜 메모 설정</strong>
        <button id="closeMemoModalBtn" class="today-btn" type="button">닫기</button>
      </div>
      <div>
        <div class="sub-txt">메모 내용 (연차, 대근, 특근 등)</div>
        <input id="modalMemoInp" type="text" placeholder="메모를 입력하세요" style="width:100%; margin-top:6px;" />
      </div>
      <button id="modalSaveMemoBtn" class="btn-primary" type="button">메모 저장하기</button>
    </div>
  </div>

  <!-- 설정 모달 (다크모드 토글 및 근무맞춤 통합) -->
  <div id="settingsModal" class="modal-bg hidden">
    <div class="modal-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <strong style="font-size:16px;">앱 설정 및 근무 맞춤</strong>
        <button id="closeSettingsModalBtn" class="today-btn" type="button">닫기</button>
      </div>

      <!-- 다크모드 설정 항목 -->
      <div style="display:flex; align-items:center; justify-content:space-between; background:var(--bg); padding:12px; border-radius:14px; border:1px solid var(--border);">
        <div>
          <div style="font-weight:800; font-size:13px;">화면 테마 모드</div>
          <div class="sub-txt">다크 모드와 라이트 모드를 전환합니다.</div>
        </div>
        <button id="themeToggleBtn" class="btn-primary" type="button" style="padding:8px 14px;">🌙 다크모드</button>
      </div>

      <hr style="border:none; border-top:1px solid var(--border); margin:4px 0;" />

      <!-- 근무맞춤 설정 항목들 -->
      <div>
        <div class="sub-txt">순환 방향</div>
        <select id="dirSel" style="width:100%; margin-top:4px;">
          <option value="FORWARD">정순환 (A 6일 → 휴 2일 → B 6일 → 휴 2일 → C 6일 → 휴 2일)</option>
          <option value="REVERSE">역순환 (C 6일 → 휴 2일 → B 6일 → 휴 2일 → A 6일 → 휴 2일)</option>
        </select>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
        <div>
          <div class="sub-txt">기준 날짜</div>
          <input id="ancDateInp" type="date" style="width:100%; margin-top:4px;" />
        </div>
        <div>
          <div class="sub-txt">기준 조</div>
          <select id="ancTeamSel" style="width:100%; margin-top:4px;">
            <option value="1">1조</option><option value="2">2조</option>
            <option value="3">3조</option><option value="4" selected>4조</option>
          </select>
        </div>
      </div>
      <div>
        <div class="sub-txt">기준일 근무 차수</div>
        <select id="ancStepSel" style="width:100%; margin-top:4px;"></select>
      </div>
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px;">
        <div><div class="sub-txt">A 시간</div><input id="tAInp" type="text" style="width:100%; margin-top:4px;" value="07:00~15:00" /></div>
        <div><div class="sub-txt">B 시간</div><input id="tBInp" type="text" style="width:100%; margin-top:4px;" value="15:00~23:00" /></div>
        <div><div class="sub-txt">C 시간</div><input id="tCInp" type="text" style="width:100%; margin-top:4px;" value="23:00~07:00" /></div>
      </div>
      <button id="saveSettingsBtn" class="btn-primary" type="button">설정 저장</button>
    </div>
  </div>

  <div id="toast" class="toast">저장되었습니다.</div>

  <script>
    const HOLIDAYS = {
      '2025-01-01':'신정','2025-01-27':'설날 연휴','2025-01-28':'설날','2025-01-29':'설날 연휴','2025-01-30':'설날 연휴','2025-03-01':'삼일절','2025-03-03':'대체공휴일','2025-05-01':'노동절','2025-05-05':'어린이날','2025-06-06':'현충일','2025-08-15':'광복절','2025-10-03':'개천절','2025-10-05':'추석 연휴','2025-10-06':'추석','2025-10-07':'추석 연휴','2025-10-08':'추석 연휴','2025-10-09':'한글날','2025-12-25':'성탄절',
      '2026-01-01':'신정','2026-02-16':'설날 연휴','2026-02-17':'설날','2026-02-18':'설날 연휴','2026-02-19':'설날 연휴','2026-03-01':'삼일절','2026-03-02':'대체공휴일','2026-05-01':'노동절','2026-05-05':'어린이날','2026-05-25':'대체공휴일','2026-06-06':'현충일','2026-08-15':'광복절','2026-08-17':'대체공휴일','2026-09-24':'추석 연휴','2026-09-25':'추석','2026-09-26':'추석 연휴','2026-09-27':'추석 연휴','2026-10-03':'개천절','2026-10-05':'대체공휴일','2026-10-09':'한글날','2026-12-25':'성탄절',
      '2027-01-01':'신정','2027-02-06':'설날 연휴','2027-02-07':'설날','2027-02-08':'설날 연휴','2027-02-09':'설날 연휴','2027-03-01':'삼일절','2027-05-01':'노동절','2027-05-05':'어린이날','2027-06-06':'현충일','2027-08-15':'광복절','2027-09-14':'추석 연휴','2027-09-15':'추석','2027-09-16':'추석 연휴','2027-09-17':'추석 연휴','2027-10-03':'개천절','2027-10-09':'한글날','2027-12-25':'성탄절'
    };
    const DOWS = ['일','월','화','수','목','금','토'];

    function fmtDate(d) {
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    }
    function parseDate(s) {
      const [y,m,d] = s.split('-').map(Number);
      return new Date(y, m-1, d);
    }
    function diffDays(s1, s2) {
      const a = parseDate(s1), b = parseDate(s2);
      return Math.round((Date.UTC(a.getFullYear(),a.getMonth(),a.getDate()) - Date.UTC(b.getFullYear(),b.getMonth(),b.getDate())) / 86400000);
    }

    const now = new Date();
    const TODAY = fmtDate(now);
    const STORAGE_KEY = 'shift_app_state_v5';

    function loadSavedData() {
      try {
        if (window.AndroidBridge && window.AndroidBridge.getInitialStateJson) {
          return JSON.parse(window.AndroidBridge.getInitialStateJson());
        }
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) return JSON.parse(saved);
      } catch (e) {}
      return null;
    }

    const savedState = loadSavedData();

    const state = {
      selectedTeam: savedState && savedState.selectedTeam ? savedState.selectedTeam : 4,
      direction: savedState && savedState.direction ? savedState.direction : 'FORWARD',
      anchorDateStr: savedState && savedState.anchorDateStr ? savedState.anchorDateStr : '2026-11-15',
      anchorTeam1Index: savedState && savedState.anchorTeam1Index !== undefined ? savedState.anchorTeam1Index : 16,
      timeA: savedState && savedState.timeA ? savedState.timeA : '07:00~15:00',
      timeB: savedState && savedState.timeB ? savedState.timeB : '15:00~23:00',
      timeC: savedState && savedState.timeC ? savedState.timeC : '23:00~07:00',
      userOverrides: savedState && savedState.userOverrides ? savedState.userOverrides : {},
      darkMode: savedState && savedState.darkMode ? savedState.darkMode : false,
      viewYear: now.getFullYear(),
      viewMonth: now.getMonth(),
      selectedDateStr: TODAY,
      doubleTapTargetDate: null
    };

    function saveToLocalStorage() {
      const payload = {
        selectedTeam: state.selectedTeam,
        direction: state.direction,
        anchorDateStr: state.anchorDateStr,
        anchorTeam1Index: state.anchorTeam1Index,
        timeA: state.timeA,
        timeB: state.timeB,
        timeC: state.timeC,
        userOverrides: state.userOverrides,
        darkMode: state.darkMode
      };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        if (window.AndroidBridge && window.AndroidBridge.saveStateJson) {
          window.AndroidBridge.saveStateJson(JSON.stringify(payload));
        }
      } catch (e) {}
    }

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2000);
    }

    function getCycleSteps(dir) {
      const ord = dir === 'REVERSE' ? ['C','B','A'] : ['A','B','C'];
      const names = { A:'A 주간', B:'B 오후', C:'C 야간' };
      const list = [];
      ord.forEach(code => {
        for (let i=1; i<=6; i++) list.push({ code, label: names[code], short: code, day: i, total: 6, isWork: true });
        for (let i=1; i<=2; i++) list.push({ code: 'OFF', label: '휴무', short: '휴', day: i, total: 2, isWork: false });
      });
      return list;
    }

    function getShift(team, dateStr) {
      const steps = getCycleSteps(state.direction);
      const delta = diffDays(dateStr, state.anchorDateStr);
      const offset = ((team - 1) * 6) % 24;
      const idx = (((state.anchorTeam1Index + offset + delta) % 24) + 24) % 24;
      const st = steps[idx];
      const time = st.code === 'A' ? state.timeA : st.code === 'B' ? state.timeB : st.code === 'C' ? state.timeC : '전일 휴식';
      return { ...st, idx, time };
    }

    function getHoliday(dateStr) {
      const ov = state.userOverrides[dateStr] || {};
      if (ov.disableHoliday) return { isHol: false, name: '' };
      if (HOLIDAYS[dateStr]) return { isHol: true, name: HOLIDAYS[dateStr] };
      return { isHol: false, name: '' };
    }

    function analyze(team, dateStr) {
      const d = parseDate(dateStr);
      const sh = getShift(team, dateStr);
      const hol = getHoliday(dateStr);
      const ov = state.userOverrides[dateStr] || {};
      return {
        dateStr, d, dow: DOWS[d.getDay()], dowNum: d.getDay(),
        sh, hol, isSpecial: hol.isHol && sh.isWork, memo: ov.memo || ''
      };
    }

    function getNaturalDayName(dayInBlock) {
      if (dayInBlock === 1) return '첫째날';
      if (dayInBlock === 2) return '둘째날';
      if (dayInBlock === 3) return '셋째날';
      if (dayInBlock === 4) return '넷째날';
      if (dayInBlock === 5) return '다섯째날';
      if (dayInBlock === 6) return '여섯째날';
      return `${dayInBlock}일째`;
    }

    function renderAll() {
      if (state.darkMode) {
        document.documentElement.style.setProperty('--bg', '#0f172a');
        document.documentElement.style.setProperty('--card', '#1e293b');
        document.documentElement.style.setProperty('--text', '#f8fafc');
        document.documentElement.style.setProperty('--sub', '#94a3b8');
        document.documentElement.style.setProperty('--border', '#334155');
        document.getElementById('mainHeader').style.background = 'rgba(15,23,42,0.88)';
        document.getElementById('themeToggleBtn').textContent = '☀️ 라이트모드';
        document.getElementById('themeToggleBtn').style.background = '#334155';
      } else {
        document.documentElement.style.setProperty('--bg', '#f8fafc');
        document.documentElement.style.setProperty('--card', '#ffffff');
        document.documentElement.style.setProperty('--text', '#0f172a');
        document.documentElement.style.setProperty('--sub', '#64748b');
        document.documentElement.style.setProperty('--border', '#e2e8f0');
        document.getElementById('mainHeader').style.background = 'rgba(255,255,255,0.88)';
        document.getElementById('themeToggleBtn').textContent = '🌙 다크모드';
        document.getElementById('themeToggleBtn').style.background = 'var(--indigo)';
      }

      document.querySelectorAll('#teamSeg button').forEach(b => {
        const isSel = Number(b.dataset.team) === state.selectedTeam;
        b.style.background = isSel ? (state.darkMode ? '#334155' : '#fff') : 'transparent';
        b.style.color = isSel ? (state.darkMode ? '#818cf8' : 'var(--indigo)') : (state.darkMode ? '#94a3b8' : '#475569');
        b.style.boxShadow = isSel ? '0 1px 3px rgba(0,0,0,0.08)' : 'none';
      });

      const selInfo = analyze(state.selectedTeam, state.selectedDateStr);
      const naturalStr = selInfo.sh.isWork ? getNaturalDayName(selInfo.sh.day) : '휴무';
      const isSelectedToday = state.selectedDateStr === TODAY;
      const bannerTitle = isSelectedToday ? `오늘 ${now.getMonth()+1}월 ${now.getDate()}일 (${selInfo.dow})` : `${selInfo.d.getMonth()+1}월 ${selInfo.d.getDate()}일 (${selInfo.dow}) 선택일`;

      document.getElementById('todayCard').innerHTML = `
        <div>
          <div class="sub-txt">${bannerTitle} · ${state.selectedTeam}조
            ${selInfo.isSpecial ? `<span class="badge-sp">특근 · ${selInfo.hol.name}</span>` : ''}
          </div>
          <div class="big-shift" style="color:var(--${selInfo.sh.code==='A'?'blue':selInfo.sh.code==='B'?'amber':selInfo.sh.code==='C'?'indigo':'emerald'})">${selInfo.sh.label} (${naturalStr})</div>
          <div class="sub-txt">${selInfo.sh.time}</div>
        </div>
        <div style="width:58px; height:58px; border-radius:18px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#fff; font-weight:900;" class="circle-${selInfo.sh.code}">
          <span style="font-size:20px; line-height:1;">${selInfo.sh.short}</span>
          <span style="font-size:9px; margin-top:2px; opacity:0.9;">${naturalStr}</span>
        </div>
      `;

      const y = state.viewYear, m = state.viewMonth;
      document.getElementById('monthLbl').textContent = `${y}년 ${m+1}월`;
      const firstW = new Date(y, m, 1).getDay();
      const lastD = new Date(y, m+1, 0).getDate();
      const cells = Math.ceil((firstW + lastD) / 7) * 7;

      let cA=0, cB=0, cC=0, cO=0, cS=0;
      for (let d=1; d<=lastD; d++) {
        const inf = analyze(state.selectedTeam, fmtDate(new Date(y, m, d)));
        if (inf.sh.code==='A') cA++; else if (inf.sh.code==='B') cB++; else if (inf.sh.code==='C') cC++; else cO++;
        if (inf.isSpecial) cS++;
      }
      document.getElementById('stA').textContent = cA + '일';
      document.getElementById('stB').textContent = cB + '일';
      document.getElementById('stC').textContent = cC + '일';
      document.getElementById('stOff').textContent = cO + '일';
      document.getElementById('stSp').textContent = cS + '일';

      let gridHtml = '';
      for (let i=0; i<cells; i++) {
        const dObj = new Date(y, m, i - firstW + 1);
        const dStr = fmtDate(dObj);
        const inMonth = dObj.getMonth() === m;
        const inf = analyze(state.selectedTeam, dStr);
        const isToday = dStr === TODAY;
        const isSel = dStr === state.selectedDateStr;
        const numColor = (inf.hol.isHol || inf.dowNum===0) ? 'var(--rose)' : inf.dowNum===6 ? 'var(--blue)' : 'var(--text)';
        const cellBg = isSel ? (state.darkMode ? '#1e3a8a' : '#eef2ff') : (state.darkMode ? '#1e293b' : '#fff');

        let badgeHtml = inf.sh.code === 'OFF' ? 
          `<div class="shift-circle-box"><span class="shift-circle circle-OFF">휴무</span></div>` :
          `<div class="shift-circle-box"><div class="shift-circle circle-${inf.sh.code}">${inf.sh.short}</div></div>`;

        gridHtml += `
          <button type="button" class="day-cell ${!inMonth?'dim':''} ${isSel?'selected':''}" data-date="${dStr}" style="background:${cellBg}; border-color:var(--border);">
            <div class="day-top">
              <span class="${isToday?'today-dot':''}" style="${!isToday?'color:'+numColor:''}">${dObj.getDate()}</span>
              ${inf.isSpecial ? '<span class="badge-sp">특근</span>' : ''}
            </div>
            ${inf.hol.isHol ? `<div class="hol-name">${inf.hol.name}</div>` : ''}
            ${inf.memo ? `<div class="memo-tag">📝 ${inf.memo}</div>` : ''}
            ${badgeHtml}
          </button>
        `;
      }
      document.getElementById('daysGrid').innerHTML = gridHtml;
    }

    const settingsModal = document.getElementById('settingsModal');
    const openSettingsBtn = document.getElementById('openSettingsBtn');
    const closeSettingsModalBtn = document.getElementById('closeSettingsModalBtn');

    openSettingsBtn.addEventListener('click', () => {
      document.getElementById('dirSel').value = state.direction;
      document.getElementById('ancDateInp').value = state.selectedDateStr;
      document.getElementById('ancTeamSel').value = String(state.selectedTeam);
      document.getElementById('tAInp').value = state.timeA;
      document.getElementById('tBInp').value = state.timeB;
      document.getElementById('tCInp').value = state.timeC;
      fillStepSelect();
      settingsModal.classList.remove('hidden');
    });

    closeSettingsModalBtn.addEventListener('click', () => {
      settingsModal.classList.add('hidden');
    });

    settingsModal.addEventListener('click', e => {
      if (e.target === settingsModal) settingsModal.classList.add('hidden');
    });

    document.getElementById('themeToggleBtn').addEventListener('click', () => {
      state.darkMode = !state.darkMode;
      saveToLocalStorage();
      renderAll();
      showToast(state.darkMode ? '다크 모드로 전환되었습니다.' : '라이트 모드로 전환되었습니다.');
    });

    document.getElementById('saveSettingsBtn').addEventListener('click', () => {
      const dateVal = document.getElementById('ancDateInp').value || TODAY;
      const teamVal = Number(document.getElementById('ancTeamSel').value) || 4;
      const stepIdx = Number(document.getElementById('ancStepSel').value) || 0;
      const offset = ((teamVal - 1) * 6) % 24;

      state.direction = document.getElementById('dirSel').value;
      state.anchorDateStr = dateVal;
      state.anchorTeam1Index = (((stepIdx - offset) % 24) + 24) % 24;
      state.timeA = document.getElementById('tAInp').value.trim() || '07:00~15:00';
      state.timeB = document.getElementById('tBInp').value.trim() || '15:00~23:00';
      state.timeC = document.getElementById('tCInp').value.trim() || '23:00~07:00';

      saveToLocalStorage();
      settingsModal.classList.add('hidden');
      renderAll();
      showToast('설정이 저장되었습니다.');
    });

    function fillStepSelect() {
      const dir = document.getElementById('dirSel').value;
      const steps = getCycleSteps(dir);
      const curIdx = getShift(Number(document.getElementById('ancTeamSel').value), document.getElementById('ancDateInp').value || TODAY).idx;
      document.getElementById('ancStepSel').innerHTML = steps.map((s, i) =>
        `<option value="${i}" ${i===curIdx?'selected':''}>${s.label} ${getNaturalDayName(s.day)} (${i+1}/24)</option>`
      ).join('');
    }

    document.getElementById('dirSel').addEventListener('change', fillStepSelect);

    let lastTapTime = 0;
    document.getElementById('daysGrid').addEventListener('click', e => {
      const cell = e.target.closest('.day-cell');
      if (!cell) return;
      const dStr = cell.dataset.date;
      
      const currentTime = new Date().getTime();
      const tapLength = currentTime - lastTapTime;
      if (tapLength < 300 && tapLength > 0) {
        openMemoModal(dStr);
        e.preventDefault();
      } else {
        state.selectedDateStr = dStr;
        const d = parseDate(dStr);
        state.viewYear = d.getFullYear();
        state.viewMonth = d.getMonth();
        renderAll();
      }
      lastTapTime = currentTime;
    });

    const memoModal = document.getElementById('memoModal');
    function openMemoModal(dStr) {
      state.doubleTapTargetDate = dStr;
      const d = parseDate(dStr);
      const inf = analyze(state.selectedTeam, dStr);
      document.getElementById('modalMemoTitle').textContent = `${d.getMonth()+1}월 ${d.getDate()}일 (${inf.dow}) 메모 설정`;
      document.getElementById('modalMemoInp').value = inf.memo;
      memoModal.classList.remove('hidden');
    }

    document.getElementById('closeMemoModalBtn').addEventListener('click', () => {
      memoModal.classList.add('hidden');
    });
    memoModal.addEventListener('click', e => {
      if (e.target === memoModal) memoModal.classList.add('hidden');
    });

    document.getElementById('modalSaveMemoBtn').addEventListener('click', () => {
      const dStr = state.doubleTapTargetDate;
      if (dStr) {
        if (!state.userOverrides[dStr]) state.userOverrides[dStr] = {};
        state.userOverrides[dStr].memo = document.getElementById('modalMemoInp').value.trim();
        saveToLocalStorage();
        renderAll();
        showToast('메모가 저장되었습니다.');
      }
      memoModal.classList.add('hidden');
    });

    document.getElementById('prevBtn').addEventListener('click', () => {
      state.viewMonth--; if (state.viewMonth < 0) { state.viewMonth = 11; state.viewYear--; }
      renderAll();
    });
    document.getElementById('nextBtn').addEventListener('click', () => {
      state.viewMonth++; if (state.viewMonth > 11) { state.viewMonth = 0; state.viewYear++; }
      renderAll();
    });
    document.getElementById('todayBtn').addEventListener('click', () => {
      const t = new Date();
      state.viewYear = t.getFullYear(); state.viewMonth = t.getMonth(); state.selectedDateStr = TODAY;
      renderAll();
    });

    document.getElementById('teamSeg').addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn) return;
      state.selectedTeam = Number(btn.dataset.team);
      saveToLocalStorage();
      renderAll();
      showToast(`${state.selectedTeam}조로 변경되었습니다.`);
    });

    renderAll();
  </script>
</body>
</html>
"""

    return files


def main() -> None:
    try:
        base_dir = Path.cwd()
        project_files = build_project_files()
        for rel_path, content in project_files.items():
            write_text_file(base_dir, rel_path, content)
        print("\n============================================================")
        print("최신 버전(AGP 8.3.2)으로 프로젝트가 성공적으로 재생성되었습니다!")
        print("============================================================")
    except Exception as exc:
        print(f"[오류 발생] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()