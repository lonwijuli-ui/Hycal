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
