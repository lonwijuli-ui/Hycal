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
