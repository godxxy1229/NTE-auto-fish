import tkinter as tk
from tkinter import messagebox
from collections import deque
from dataclasses import dataclass
import ctypes
import threading
import time
import json
import os
import sys

import customtkinter as ctk  # custom2kinter
import cv2
import numpy as np
import pyautogui
import pydirectinput
from PIL import Image, ImageTk

try:
    import mss
except ImportError:
    mss = None


CONFIG_FILE = "config.json"
REFERENCE_IMAGE_DIR = "reference_images"
BITE_REFERENCE_FILE = os.path.join(REFERENCE_IMAGE_DIR, "bite_reference.png")
SUCCESS_REFERENCE_FILE = os.path.join(REFERENCE_IMAGE_DIR, "success_reference.png")
BITE_LEGACY_TEMPLATE_FILES = ("bite_template.png",)
SUCCESS_LEGACY_TEMPLATE_FILES = ("success_template.png", "success_templates.png")
REFERENCE_IMAGE_OPTIONS = {
    "bite": (("capture", BITE_REFERENCE_FILE),) + tuple(("legacy", path) for path in BITE_LEGACY_TEMPLATE_FILES),
    "success": (("capture", SUCCESS_REFERENCE_FILE),) + tuple(("legacy", path) for path in SUCCESS_LEGACY_TEMPLATE_FILES),
}
ROI_REFERENCE_KIND = {
    "bite_roi": "bite",
    "success_roi": "success",
}
CAPTURE_EXAMPLE_DIR = os.path.join("assets", "capture_examples")
CAPTURE_EXAMPLE_IMAGES = {
    "bar_roi": "fishing_bar_capture_example.png",
    "bite_roi": "bite_capture_example.png",
    "success_roi": "success_capture_example.png",
}
STATUS_UPDATE_INTERVAL = 0.12
DEBUG_UPDATE_INTERVAL = 0.1
TOOLTIP_HOVER_DELAY_MS = 80
TOOLTIP_SCREEN_MARGIN = 12
STALE_DETECTION_FRAMES = 2
PREDICTION_HORIZON = 0.08
MAX_PREDICTION_DT = 0.35
MIN_PREDICTION_CONFIDENCE = 0.35


def enable_dpi_awareness():
    if os.name != "nt":
        return

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


default_config = {
    "bar_roi": None,
    "bite_roi": None,
    "success_roi": None,
    "green_lower": [70, 60, 70],
    "green_upper": [95, 255, 255],
    "yellow_lower": [20, 60, 100],
    "yellow_upper": [38, 255, 255],
    "bite_match_threshold": 0.65,
    "success_match_threshold": 0.65,
    "bite_cooldown": 1.0,
    "success_cooldown": 1.5,
    "deadzone": 5,
    "loop_delay": 0.02,
    "invert_control": False,
    "no_detection_retry_enabled": False,
    "no_detection_retry_seconds": 12.0,
    "language": "en",
}


def is_valid_roi(roi):
    if not roi or len(roi) != 4:
        return False
    try:
        return int(roi[2]) > 0 and int(roi[3]) > 0
    except (TypeError, ValueError):
        return False


LANGUAGE_NAMES = {
    "en": "English",
    "zh": "简体中文",
    "ko": "한국어",
    "ja": "日本語",
}
LANGUAGE_CODES_BY_NAME = {name: code for code, name in LANGUAGE_NAMES.items()}


TRANSLATIONS = {
    "en": {
        "app.title": "Auto Fishing Macro",
        "language.label": "Language",
        "section.status.title": "Run Status",
        "section.status.subtitle": "Check macro, input, and recovery state at a glance.",
        "section.roi.title": "Detection Area Setup",
        "section.roi.subtitle": "Review current detection areas and capture image status, then reselect only what you need.",
        "section.detect.title": "Detection Settings",
        "section.detect.subtitle": "Changes are not written to the file until saved.",
        "section.options.title": "Options",
        "section.debug.title": "Fishing Bar Debug",
        "section.debug.subtitle": "View the detection overlay and performance information inside the main window.",
        "chip.macro": "Macro",
        "chip.input": "Input",
        "chip.success_detection": "Success",
        "chip.retry": "No-detect retry",
        "state.idle": "Idle",
        "state.running": "Running",
        "state.no_input": "No input",
        "state.key_input": "{key} held",
        "state.on": "ON",
        "state.off": "OFF",
        "state.configured": "Set",
        "state.unconfigured": "Not set",
        "state.retry_count": "{count} times",
        "roi.bar": "Fishing Bar",
        "roi.bite": "Bite Detection",
        "roi.success": "Success Detection",
        "roi.coords": "Detection area: [{x}, {y}, {w}, {h}]",
        "roi.unset": "Detection area: not set",
        "reference.unused": "Capture image: not needed",
        "reference.capture_present": "Capture image: {file} found",
        "reference.legacy_present": "Legacy template: {file} found",
        "reference.missing": "Capture/template image missing: {files}",
        "button.reselect": "Reselect",
        "button.preview_areas": "Check Positions",
        "button.reset_defaults": "Reset to defaults",
        "button.save": "Save Settings",
        "button.start": "Start",
        "button.stop": "Stop",
        "button.exit": "Exit",
        "button.cancel_esc": "Cancel (ESC)",
        "setting.deadzone.title": "Deadzone",
        "setting.deadzone.desc": "If the green and yellow centers differ by this many px or less, no A/D key is pressed.",
        "setting.loop_delay.title": "Loop Delay",
        "setting.loop_delay.desc": "Wait time between loops. Lower values react faster.",
        "setting.bite_threshold.title": "Bite Accuracy",
        "setting.bite_threshold.desc": "Similarity threshold for the captured bite image.",
        "setting.success_threshold.title": "Success Accuracy",
        "setting.success_threshold.desc": "Similarity threshold for the captured success image.",
        "option.invert": "Invert A/D direction",
        "option.no_detection_retry": "Press F after no detection",
        "setting.retry_seconds.title": "No-detect Timeout",
        "setting.retry_seconds.desc": "Seconds to wait before pressing F when nothing is detected. Default: 12 seconds.",
        "option.debug": "Show debug",
        "debug.placeholder": "Enable debug and start the macro to show data.",
        "debug.image_waiting": "Waiting for debug image",
        "debug.waiting": "Waiting | {summary}",
        "perf.waiting": "Performance: waiting",
        "perf.prefix": "Performance: {summary}",
        "overlay.title": "{title} Detection Area",
        "overlay.instruction": "Drag the {title} detection area / ESC to cancel",
        "preview.instruction": "Detection area preview / click or press ESC to close",
        "error.region_too_small": "The selected detection area is too small.",
        "dialog.region_error.title": "Detection Area Error",
        "dialog.input_error.title": "Input Error",
        "dialog.input_error.body": "Please check numeric values.",
        "dialog.missing_area.title": "Detection Area Missing",
        "dialog.missing_area.body": "Please set the {area} detection area first.",
        "dialog.missing_bite.title": "Bite Capture Image Missing",
        "dialog.missing_bite.body": "Please capture the Bite Detection area first, or place bite_template.png next to the app.",
        "dialog.missing_success.title": "Success Capture Image Missing",
        "dialog.missing_success.body": "Please capture the Success Detection area first, or place success_template.png next to the app.",
        "toast.bar_saved": "Fishing bar detection area saved.",
        "toast.bite_saved": "Bite detection area and capture image saved.",
        "toast.success_saved": "Success detection area and capture image saved.",
        "toast.settings_saved": "Settings saved.",
        "toast.defaults_reset": "Detection settings were reset. Press Save Settings to apply.",
        "toast.language_saved": "Language changed.",
        "toast.preview_missing": "Some detection areas are not set.",
        "toast.preview_no_areas": "No detection areas are set.",
        "status.ready": "Status: idle",
        "status.running_success_off": "Status: running / success detection OFF",
        "status.stopped": "Status: stopped",
        "status.no_detection_retry": "Status: no detection for {seconds:.0f}s / pressed F",
        "status.mss_failed": "Status: MSS capture failed / {error}",
        "status.bite_detected": "Status: bite detected! F / score {score:.3f}",
        "status.success_detected": "Status: success detected! ESC -> F / score {score:.3f}",
        "status.detect_failed": "Status: fishing bar detection failed / bite {bite:.3f} / success {success:.3f}",
        "status.center_hold": "Status: centered / success detection {success_state}",
        "status.key_input": "Status: holding {key} / success detection {success_state}",
        "tooltip.roi.bar": "Use the example image below as a guide and capture only the long fishing bar detection area. You must capture the actual game screen!",
        "tooltip.roi.bite": "Use the example image below as a guide and capture the detection area where the bite prompt appears. If the current screen is similar to your captured image, the macro presses F. You must capture the actual game screen!",
        "tooltip.roi.success": "Use the example image below as a guide and capture the detection area where the success prompt appears. If the current screen is similar to your captured image, the macro presses ESC then F. You must capture the actual game screen!",
        "tooltip.preview_areas": "Shows the current detection areas as colored boxes over the screen. This does not change any settings.",
        "tooltip.deadzone": "This is the no-input buffer. If the green and yellow centers differ by this many px or less, A/D is released. Increase it to reduce jitter; decrease it for quicker correction.",
        "tooltip.loop_delay": "Lower values can improve response but use more CPU. If the game stutters, raise this value.",
        "tooltip.bite_threshold": "Higher values reduce false positives but may miss bite images.",
        "tooltip.success_threshold": "Higher values reduce false positives but may miss success images.",
        "tooltip.invert": "Use this if A and D move the marker in the opposite direction on your setup.",
        "tooltip.no_detection_retry": "When enabled, the macro presses F once if no bite, success, or fishing bar is detected for the selected timeout.",
        "tooltip.debug": "Shows the detected candidates, selected centers, confidence, FPS, and capture backend.",
        "tooltip.save": "Writes current UI settings to config.json.",
        "tooltip.start": "Starts or stops the macro. Bite and success capture images must exist before starting.",
        "tooltip.exit": "Stops the macro, releases held keys, and closes the app.",
        "tooltip.reset_defaults": "Restores only the visible detection sliders to their default values. Save to apply.",
    },
    "ko": {
        "app.title": "낚시 자동 매크로",
        "language.label": "언어",
        "section.status.title": "실행 상태",
        "section.status.subtitle": "현재 매크로 상태와 입력 상태를 한눈에 확인합니다.",
        "section.roi.title": "감지 영역 설정 상태",
        "section.roi.subtitle": "현재 감지 영역과 캡처 이미지 상태를 확인하고 필요한 항목만 다시 지정합니다.",
        "section.detect.title": "감지 설정",
        "section.detect.subtitle": "저장 전까지 파일에는 반영되지 않습니다.",
        "section.options.title": "옵션",
        "section.debug.title": "낚시바 디버그",
        "section.debug.subtitle": "감지 오버레이와 성능 정보를 메인 화면 안에서 확인합니다.",
        "chip.macro": "매크로",
        "chip.input": "입력",
        "chip.success_detection": "성공감지",
        "chip.retry": "무감지 복구",
        "state.idle": "대기중",
        "state.running": "실행중",
        "state.no_input": "입력 없음",
        "state.key_input": "{key} 입력중",
        "state.on": "ON",
        "state.off": "OFF",
        "state.configured": "설정됨",
        "state.unconfigured": "미설정",
        "state.retry_count": "{count}회",
        "roi.bar": "낚시바",
        "roi.bite": "입질 인식",
        "roi.success": "성공 인식",
        "roi.coords": "감지 영역: [{x}, {y}, {w}, {h}]",
        "roi.unset": "감지 영역: 미설정",
        "reference.unused": "캡처 이미지: 필요 없음",
        "reference.capture_present": "캡처 이미지: {file} 있음",
        "reference.legacy_present": "기존 템플릿: {file} 있음",
        "reference.missing": "캡처/템플릿 이미지 없음: {files}",
        "button.reselect": "다시 지정",
        "button.preview_areas": "위치 확인",
        "button.reset_defaults": "기본값으로 초기화",
        "button.save": "설정 저장",
        "button.start": "시작",
        "button.stop": "정지",
        "button.exit": "종료",
        "button.cancel_esc": "취소 (ESC)",
        "setting.deadzone.title": "데드존",
        "setting.deadzone.desc": "초록/노란 중심 차이가 이 px 이하이면 A/D를 누르지 않는 완충 구간입니다.",
        "setting.loop_delay.title": "반복 딜레이",
        "setting.loop_delay.desc": "루프 사이의 대기 시간입니다. 낮을수록 반응이 빠릅니다.",
        "setting.bite_threshold.title": "입질 정확도",
        "setting.bite_threshold.desc": "사용자가 캡처한 입질 이미지와의 유사도 기준입니다.",
        "setting.success_threshold.title": "성공 정확도",
        "setting.success_threshold.desc": "사용자가 캡처한 성공 이미지와의 유사도 기준입니다.",
        "option.invert": "A/D 방향 반전",
        "option.no_detection_retry": "무감지 시 F 입력",
        "setting.retry_seconds.title": "무감지 대기 시간",
        "setting.retry_seconds.desc": "아무것도 감지되지 않을 때 F를 누르기 전까지 기다릴 시간입니다. 기본값은 12초입니다.",
        "option.debug": "디버그 보기",
        "debug.placeholder": "디버그 보기를 켜고 매크로를 시작하면 정보가 표시됩니다.",
        "debug.image_waiting": "디버그 이미지 대기중",
        "debug.waiting": "대기중 | {summary}",
        "perf.waiting": "성능: 대기중",
        "perf.prefix": "성능: {summary}",
        "overlay.title": "{title} 감지 영역 지정",
        "overlay.instruction": "{title} 감지 영역을 드래그하세요 / ESC 취소",
        "preview.instruction": "감지 영역 위치 확인 / 클릭 또는 ESC로 닫기",
        "error.region_too_small": "감지 영역이 너무 작습니다.",
        "dialog.region_error.title": "감지 영역 오류",
        "dialog.input_error.title": "입력 오류",
        "dialog.input_error.body": "숫자 값을 확인해주세요.",
        "dialog.missing_area.title": "감지 영역 미설정",
        "dialog.missing_area.body": "먼저 [{area}] 감지 영역을 설정해주세요.",
        "dialog.missing_bite.title": "입질 캡처 이미지 없음",
        "dialog.missing_bite.body": "먼저 [입질 인식] 감지 영역을 캡처하거나 bite_template.png를 앱 경로에 두세요.",
        "dialog.missing_success.title": "성공 캡처 이미지 없음",
        "dialog.missing_success.body": "먼저 [성공 인식] 감지 영역을 캡처하거나 success_template.png를 앱 경로에 두세요.",
        "toast.bar_saved": "낚시바 감지 영역이 저장되었습니다.",
        "toast.bite_saved": "입질 감지 영역과 캡처 이미지가 저장되었습니다.",
        "toast.success_saved": "성공 감지 영역과 캡처 이미지가 저장되었습니다.",
        "toast.settings_saved": "설정이 저장되었습니다.",
        "toast.defaults_reset": "감지 설정을 기본값으로 되돌렸습니다. 설정 저장을 누르면 반영됩니다.",
        "toast.language_saved": "언어가 변경되었습니다.",
        "toast.preview_missing": "일부 감지 영역이 아직 설정되지 않았습니다.",
        "toast.preview_no_areas": "설정된 감지 영역이 없습니다.",
        "status.ready": "상태: 대기중",
        "status.running_success_off": "상태: 실행중 / 성공감지 OFF",
        "status.stopped": "상태: 정지됨",
        "status.no_detection_retry": "상태: {seconds:.0f}초 무감지 / F 재입력",
        "status.mss_failed": "상태: MSS 캡처 실패 / {error}",
        "status.bite_detected": "상태: 입질 감지! F / 정확도 {score:.3f}",
        "status.success_detected": "상태: 성공 감지! ESC -> F / 정확도 {score:.3f}",
        "status.detect_failed": "상태: 낚시바 인식 실패 / 입질 {bite:.3f} / 성공 {success:.3f}",
        "status.center_hold": "상태: 중앙 유지 / 성공감지 {success_state}",
        "status.key_input": "상태: {key} 입력중 / 성공감지 {success_state}",
        "tooltip.roi.bar": "아래 예시 이미지를 참고해 낚시바의 긴 막대 감지 영역만 캡처하세요. 실제 게임 화면을 캡쳐해야합니다!",
        "tooltip.roi.bite": "아래 예시 이미지를 참고해 입질 안내가 뜨는 감지 영역을 캡처하세요. 현재 화면이 내 캡처 이미지와 비슷하면, 매크로가 F를 누릅니다. 실제 게임 화면을 캡쳐해야합니다!",
        "tooltip.roi.success": "아래 예시 이미지를 참고해 성공 안내가 뜨는 감지 영역을 캡처하세요. 현재 화면이 내 캡처 이미지와 비슷하면, 매크로가 ESC 후 F를 누릅니다. 실제 게임 화면을 캡쳐해야합니다!",
        "tooltip.preview_areas": "현재 감지 영역을 화면 위 색상 박스로 보여줍니다. 설정은 변경하지 않습니다.",
        "tooltip.deadzone": "입력하지 않는 완충 구간입니다. 초록 막대 중심과 노란 막대 중심 차이가 이 px 이하이면 A/D를 떼고 대기합니다. 중앙 근처에서 흔들리면 값을 올리고, 반응이 늦으면 낮추세요.",
        "tooltip.loop_delay": "낮을수록 반응이 빠르지만 CPU 사용량이 늘 수 있습니다. 게임이 끊기면 값을 올리세요.",
        "tooltip.bite_threshold": "높이면 오탐이 줄지만 입질 이미지를 놓칠 수 있습니다.",
        "tooltip.success_threshold": "높이면 오탐이 줄지만 성공 이미지를 놓칠 수 있습니다.",
        "tooltip.invert": "A/D 입력 방향이 반대로 움직일 때 켭니다.",
        "tooltip.no_detection_retry": "입질, 성공, 낚시바가 설정한 시간 동안 모두 감지되지 않으면 F를 한 번 눌러 복구를 시도합니다.",
        "tooltip.debug": "후보 박스, 중심점, confidence, FPS, 캡처 backend를 확인합니다.",
        "tooltip.save": "현재 UI 설정을 config.json에 저장합니다.",
        "tooltip.start": "매크로를 시작하거나 정지합니다. 시작 전 입질/성공 캡처 이미지가 필요합니다.",
        "tooltip.exit": "매크로를 정지하고 눌린 키를 해제한 뒤 앱을 종료합니다.",
        "tooltip.reset_defaults": "화면에 보이는 감지 슬라이더만 기본값으로 되돌립니다. 저장을 눌러 반영하세요.",
    },
}


def _derive_translation(base, overrides):
    result = TRANSLATIONS["en"].copy()
    result.update(overrides)
    return result


TRANSLATIONS["zh"] = _derive_translation("en", {
    "app.title": "自动钓鱼宏",
    "language.label": "语言",
    "section.status.title": "运行状态",
    "section.status.subtitle": "快速查看宏、按键和恢复状态。",
    "section.roi.title": "检测区域设置",
    "section.roi.subtitle": "查看当前检测区域和捕获图像状态，只重新选择需要的项目。",
    "section.detect.title": "检测设置",
    "section.detect.subtitle": "保存前不会写入文件。",
    "section.options.title": "选项",
    "section.debug.title": "钓鱼条调试",
    "section.debug.subtitle": "在主窗口查看检测叠加和性能信息。",
    "chip.macro": "宏",
    "chip.input": "输入",
    "chip.success_detection": "成功检测",
    "chip.retry": "无检测恢复",
    "state.idle": "待机",
    "state.running": "运行中",
    "state.no_input": "无输入",
    "state.key_input": "按住 {key}",
    "state.configured": "已设置",
    "state.unconfigured": "未设置",
    "state.retry_count": "{count} 次",
    "roi.bar": "钓鱼条",
    "roi.bite": "咬钩检测",
    "roi.success": "成功检测",
    "roi.coords": "检测区域: [{x}, {y}, {w}, {h}]",
    "roi.unset": "检测区域: 未设置",
    "reference.unused": "捕获图像: 不需要",
    "reference.capture_present": "捕获图像: {file} 已存在",
    "reference.legacy_present": "旧模板: {file} 已存在",
    "reference.missing": "缺少捕获/模板图像: {files}",
    "button.reselect": "重新选择",
    "button.preview_areas": "检查位置",
    "button.reset_defaults": "恢复默认值",
    "button.save": "保存设置",
    "button.start": "开始",
    "button.stop": "停止",
    "button.exit": "退出",
    "button.cancel_esc": "取消 (ESC)",
    "setting.deadzone.title": "死区",
    "setting.deadzone.desc": "绿色和黄色中心差在此 px 以内时，不按 A/D。",
    "setting.loop_delay.title": "循环延迟",
    "setting.loop_delay.desc": "每次循环之间的等待时间。越低反应越快。",
    "setting.bite_threshold.title": "咬钩准确度",
    "setting.bite_threshold.desc": "与用户捕获的咬钩图像的相似度阈值。",
    "setting.success_threshold.title": "成功准确度",
    "setting.success_threshold.desc": "与用户捕获的成功图像的相似度阈值。",
    "option.invert": "反转 A/D 方向",
    "option.no_detection_retry": "无检测时按 F",
    "setting.retry_seconds.title": "无检测等待时间",
    "setting.retry_seconds.desc": "未检测到任何内容时，按 F 前等待的秒数。默认值为 12 秒。",
    "option.debug": "显示调试",
    "debug.placeholder": "开启调试并启动宏后会显示信息。",
    "debug.image_waiting": "等待调试图像",
    "debug.waiting": "等待 | {summary}",
    "perf.waiting": "性能: 等待中",
    "perf.prefix": "性能: {summary}",
    "overlay.title": "{title} 检测区域",
    "overlay.instruction": "拖拽选择 {title} 检测区域 / ESC 取消",
    "preview.instruction": "检测区域预览 / 点击或按 ESC 关闭",
    "error.region_too_small": "选择的检测区域太小。",
    "dialog.region_error.title": "检测区域错误",
    "dialog.input_error.title": "输入错误",
    "dialog.input_error.body": "请检查数字值。",
    "dialog.missing_area.title": "检测区域未设置",
    "dialog.missing_area.body": "请先设置 [{area}] 检测区域。",
    "dialog.missing_bite.title": "缺少咬钩捕获图像",
    "dialog.missing_bite.body": "请先捕获咬钩检测区域，或将 bite_template.png 放在程序旁边。",
    "dialog.missing_success.title": "缺少成功捕获图像",
    "dialog.missing_success.body": "请先捕获成功检测区域，或将 success_template.png 放在程序旁边。",
    "toast.bar_saved": "钓鱼条检测区域已保存。",
    "toast.bite_saved": "咬钩检测区域和捕获图像已保存。",
    "toast.success_saved": "成功检测区域和捕获图像已保存。",
    "toast.settings_saved": "设置已保存。",
    "toast.defaults_reset": "检测设置已恢复默认。点击保存设置后生效。",
    "toast.language_saved": "语言已更改。",
    "toast.preview_missing": "部分检测区域尚未设置。",
    "toast.preview_no_areas": "没有已设置的检测区域。",
    "status.ready": "状态: 待机",
    "status.running_success_off": "状态: 运行中 / 成功检测 OFF",
    "status.stopped": "状态: 已停止",
    "status.no_detection_retry": "状态: {seconds:.0f} 秒无检测 / 已按 F",
    "status.mss_failed": "状态: MSS 捕获失败 / {error}",
    "status.bite_detected": "状态: 检测到咬钩! F / 分数 {score:.3f}",
    "status.success_detected": "状态: 检测到成功! ESC -> F / 分数 {score:.3f}",
    "status.detect_failed": "状态: 钓鱼条检测失败 / 咬钩 {bite:.3f} / 成功 {success:.3f}",
    "status.center_hold": "状态: 保持居中 / 成功检测 {success_state}",
    "status.key_input": "状态: 按住 {key} / 成功检测 {success_state}",
    "tooltip.roi.bar": "参考下方示例图，只捕获钓鱼条的长条检测区域。必须捕获实际游戏画面！",
    "tooltip.roi.bite": "参考下方示例图，捕获咬钩提示出现的检测区域。当前画面与您的捕获图像相似时，宏会按 F。必须捕获实际游戏画面！",
    "tooltip.roi.success": "参考下方示例图，捕获成功提示出现的检测区域。当前画面与您的捕获图像相似时，宏会先按 ESC 再按 F。必须捕获实际游戏画面！",
    "tooltip.preview_areas": "在屏幕上用彩色框显示当前检测区域。不会更改任何设置。",
    "tooltip.deadzone": "这是不输入的缓冲区。绿色条中心和黄色标记中心差在此 px 以内时会松开 A/D。抖动时增大，反应慢时减小。",
    "tooltip.loop_delay": "数值越低反应越快，但 CPU 占用可能更高。游戏卡顿时请增大。",
    "tooltip.bite_threshold": "数值越高误判越少，但可能漏掉咬钩图像。",
    "tooltip.success_threshold": "数值越高误判越少，但可能漏掉成功图像。",
    "tooltip.invert": "如果 A/D 移动方向与预期相反，请开启。",
    "tooltip.no_detection_retry": "启用后，如果在设定时间内没有检测到咬钩、成功或钓鱼条，会按一次 F 尝试恢复。",
    "tooltip.debug": "显示候选框、中心点、confidence、FPS 和捕获 backend。",
    "tooltip.save": "将当前 UI 设置写入 config.json。",
    "tooltip.start": "启动或停止宏。启动前必须先有咬钩和成功的捕获图像。",
    "tooltip.exit": "停止宏、释放按键并关闭程序。",
    "tooltip.reset_defaults": "仅将当前显示的检测滑块恢复为默认值。点击保存后生效。",
})


TRANSLATIONS["ja"] = _derive_translation("en", {
    "app.title": "自動釣りマクロ",
    "language.label": "言語",
    "section.status.title": "実行状態",
    "section.status.subtitle": "マクロ、入力、復帰状態を一目で確認します。",
    "section.roi.title": "検出範囲設定",
    "section.roi.subtitle": "現在の検出範囲とキャプチャ画像の状態を確認し、必要な項目だけ再指定します。",
    "section.detect.title": "検出設定",
    "section.detect.subtitle": "保存するまでファイルには反映されません。",
    "section.options.title": "オプション",
    "section.debug.title": "釣りバー デバッグ",
    "section.debug.subtitle": "検出オーバーレイと性能情報をメイン画面で確認します。",
    "chip.macro": "マクロ",
    "chip.input": "入力",
    "chip.success_detection": "成功検出",
    "chip.retry": "無検出復帰",
    "state.idle": "待機中",
    "state.running": "実行中",
    "state.no_input": "入力なし",
    "state.key_input": "{key} 入力中",
    "state.configured": "設定済み",
    "state.unconfigured": "未設定",
    "state.retry_count": "{count}回",
    "roi.bar": "釣りバー",
    "roi.bite": "アタリ検出",
    "roi.success": "成功検出",
    "roi.coords": "検出範囲: [{x}, {y}, {w}, {h}]",
    "roi.unset": "検出範囲: 未設定",
    "reference.unused": "キャプチャ画像: 不要",
    "reference.capture_present": "キャプチャ画像: {file} あり",
    "reference.legacy_present": "旧テンプレート: {file} あり",
    "reference.missing": "キャプチャ/テンプレート画像なし: {files}",
    "button.reselect": "再指定",
    "button.preview_areas": "位置確認",
    "button.reset_defaults": "既定値に戻す",
    "button.save": "設定を保存",
    "button.start": "開始",
    "button.stop": "停止",
    "button.exit": "終了",
    "button.cancel_esc": "キャンセル (ESC)",
    "setting.deadzone.title": "デッドゾーン",
    "setting.deadzone.desc": "緑と黄色の中心差がこの px 以下なら A/D を押さない緩衝範囲です。",
    "setting.loop_delay.title": "ループ遅延",
    "setting.loop_delay.desc": "ループ間の待機時間です。低いほど反応が速くなります。",
    "setting.bite_threshold.title": "アタリ精度",
    "setting.bite_threshold.desc": "ユーザーがキャプチャしたアタリ画像との類似度しきい値です。",
    "setting.success_threshold.title": "成功精度",
    "setting.success_threshold.desc": "ユーザーがキャプチャした成功画像との類似度しきい値です。",
    "option.invert": "A/D 方向を反転",
    "option.no_detection_retry": "無検出時に F 入力",
    "setting.retry_seconds.title": "無検出待機時間",
    "setting.retry_seconds.desc": "何も検出されない場合に F を押すまで待つ秒数です。既定値は12秒です。",
    "option.debug": "デバッグ表示",
    "debug.placeholder": "デバッグを有効にしてマクロを開始すると情報が表示されます。",
    "debug.image_waiting": "デバッグ画像待機中",
    "debug.waiting": "待機中 | {summary}",
    "perf.waiting": "性能: 待機中",
    "perf.prefix": "性能: {summary}",
    "overlay.title": "{title} 検出範囲",
    "overlay.instruction": "{title} 検出範囲をドラッグ / ESC でキャンセル",
    "preview.instruction": "検出範囲プレビュー / クリックまたは ESC で閉じる",
    "error.region_too_small": "選択した検出範囲が小さすぎます。",
    "dialog.region_error.title": "検出範囲エラー",
    "dialog.input_error.title": "入力エラー",
    "dialog.input_error.body": "数値を確認してください。",
    "dialog.missing_area.title": "検出範囲が未設定",
    "dialog.missing_area.body": "先に [{area}] 検出範囲を設定してください。",
    "dialog.missing_bite.title": "アタリのキャプチャ画像なし",
    "dialog.missing_bite.body": "先にアタリ検出範囲をキャプチャするか、bite_template.png をアプリの隣に置いてください。",
    "dialog.missing_success.title": "成功のキャプチャ画像なし",
    "dialog.missing_success.body": "先に成功検出範囲をキャプチャするか、success_template.png をアプリの隣に置いてください。",
    "toast.bar_saved": "釣りバー検出範囲を保存しました。",
    "toast.bite_saved": "アタリ検出範囲とキャプチャ画像を保存しました。",
    "toast.success_saved": "成功検出範囲とキャプチャ画像を保存しました。",
    "toast.settings_saved": "設定を保存しました。",
    "toast.defaults_reset": "検出設定を既定値に戻しました。保存すると反映されます。",
    "toast.language_saved": "言語を変更しました。",
    "toast.preview_missing": "一部の検出範囲が未設定です。",
    "toast.preview_no_areas": "設定済みの検出範囲がありません。",
    "status.ready": "状態: 待機中",
    "status.running_success_off": "状態: 実行中 / 成功検出 OFF",
    "status.stopped": "状態: 停止",
    "status.no_detection_retry": "状態: {seconds:.0f}秒無検出 / F 再入力",
    "status.mss_failed": "状態: MSS キャプチャ失敗 / {error}",
    "status.bite_detected": "状態: アタリ検出! F / 精度 {score:.3f}",
    "status.success_detected": "状態: 成功検出! ESC -> F / 精度 {score:.3f}",
    "status.detect_failed": "状態: 釣りバー検出失敗 / アタリ {bite:.3f} / 成功 {success:.3f}",
    "status.center_hold": "状態: 中央維持 / 成功検出 {success_state}",
    "status.key_input": "状態: {key} 入力中 / 成功検出 {success_state}",
    "tooltip.roi.bar": "下の例を参考に、釣りバーの長い検出範囲だけをキャプチャしてください。実際のゲーム画面をキャプチャする必要があります！",
    "tooltip.roi.bite": "下の例を参考に、アタリ表示が出る検出範囲をキャプチャしてください。現在画面が自分のキャプチャ画像に近いと、マクロが F を押します。実際のゲーム画面をキャプチャする必要があります！",
    "tooltip.roi.success": "下の例を参考に、成功表示が出る検出範囲をキャプチャしてください。現在画面が自分のキャプチャ画像に近いと、マクロが ESC の後に F を押します。実際のゲーム画面をキャプチャする必要があります！",
    "tooltip.preview_areas": "現在の検出範囲を画面上に色付き枠で表示します。設定は変更しません。",
    "tooltip.deadzone": "入力しない緩衝範囲です。緑バー中心と黄色マーカー中心の差がこの px 以下なら A/D を離します。揺れる場合は上げ、反応が遅い場合は下げます。",
    "tooltip.loop_delay": "低いほど反応は速くなりますが CPU 使用量が増えます。ゲームが重い場合は上げてください。",
    "tooltip.bite_threshold": "高いほど誤検出は減りますが、アタリ画像を見逃す場合があります。",
    "tooltip.success_threshold": "高いほど誤検出は減りますが、成功画像を見逃す場合があります。",
    "tooltip.invert": "A/D の移動方向が逆に感じる場合に有効にします。",
    "tooltip.no_detection_retry": "有効時、設定した時間だけアタリ・成功・釣りバーが検出されないと F を1回押して復帰を試します。",
    "tooltip.debug": "候補枠、中心点、confidence、FPS、キャプチャ backend を表示します。",
    "tooltip.save": "現在の UI 設定を config.json に保存します。",
    "tooltip.start": "マクロを開始または停止します。開始前にアタリと成功のキャプチャ画像が必要です。",
    "tooltip.exit": "マクロを停止し、押下中のキーを解除してアプリを閉じます。",
    "tooltip.reset_defaults": "表示中の検出スライダーだけを既定値に戻します。保存すると反映されます。",
})


def normalize_language(language):
    return language if language in LANGUAGE_NAMES else default_config["language"]


def translate(language, text_key, **kwargs):
    table = TRANSLATIONS.get(normalize_language(language), TRANSLATIONS["en"])
    text = table.get(text_key, TRANSLATIONS["en"].get(text_key, text_key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


@dataclass
class BarDetection:
    green_center: int | None = None
    yellow_center: int | None = None
    green_rect: tuple[int, int, int, int] | None = None
    yellow_rect: tuple[int, int, int, int] | None = None
    confidence: float = 0.0
    debug_frame: np.ndarray | None = None
    stale_frames: int = 0
    timestamp: float = 0.0
    green_velocity: float = 0.0
    yellow_velocity: float = 0.0
    predicted_green_center: int | None = None
    predicted_yellow_center: int | None = None


class ScreenCapture:
    def __init__(self):
        self._mss = None
        self.last_backend = "mss"
        self.last_error = ""

    def _ensure_mss(self):
        if mss is None:
            self.last_backend = "mss-missing"
            self.last_error = "mss is not installed"
            raise RuntimeError(self.last_error)
        if self._mss is None:
            factory = getattr(mss, "MSS", mss.mss)
            self._mss = factory()
        return self._mss

    def _reset_mss(self):
        if self._mss is not None:
            try:
                self._mss.close()
            except Exception:
                pass
        self._mss = None

    def size(self):
        sct = self._ensure_mss()
        monitor = sct.monitors[0]
        return monitor["width"], monitor["height"]

    def grab(self, region=None):
        last_error = None
        for attempt in range(2):
            try:
                sct = self._ensure_mss()
                if region:
                    x, y, w, h = [int(v) for v in region]
                    monitor = {"left": x, "top": y, "width": w, "height": h}
                else:
                    monitor = sct.monitors[0]
                frame = np.array(sct.grab(monitor))
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                self.last_backend = "mss"
                self.last_error = ""
                return rgb, (monitor["left"], monitor["top"])
            except Exception as e:
                last_error = e
                self.last_backend = "mss-error"
                self.last_error = str(e)
                self._reset_mss()
                if attempt == 0:
                    continue

        raise RuntimeError(f"MSS capture failed: {last_error}")


class PerformanceStats:
    def __init__(self, maxlen=120):
        self.samples = deque(maxlen=maxlen)

    def add(self, capture_ms, detect_ms, loop_ms, backend):
        self.samples.append(
            {
                "capture_ms": float(capture_ms),
                "detect_ms": float(detect_ms),
                "loop_ms": float(loop_ms),
                "backend": backend,
            }
        )

    def snapshot(self):
        if not self.samples:
            return {
                "capture_ms": 0.0,
                "detect_ms": 0.0,
                "loop_ms": 0.0,
                "loop_fps": 0.0,
                "backend": "unknown",
            }

        count = len(self.samples)
        capture_ms = sum(s["capture_ms"] for s in self.samples) / count
        detect_ms = sum(s["detect_ms"] for s in self.samples) / count
        loop_ms = sum(s["loop_ms"] for s in self.samples) / count
        backend = self.samples[-1]["backend"]
        return {
            "capture_ms": capture_ms,
            "detect_ms": detect_ms,
            "loop_ms": loop_ms,
            "loop_fps": 1000.0 / loop_ms if loop_ms > 0 else 0.0,
            "backend": backend,
        }

    def summary_text(self):
        snapshot = self.snapshot()
        return (
            f"{snapshot['backend']} "
            f"{snapshot['loop_fps']:.1f}fps "
            f"cap={snapshot['capture_ms']:.1f}ms "
            f"det={snapshot['detect_ms']:.1f}ms"
        )


def _make_hsv_mask(hsv, lower, upper):
    lower = np.array(lower, dtype=np.uint8)
    upper = np.array(upper, dtype=np.uint8)
    return cv2.inRange(hsv, lower, upper)


def _prepare_bar_masks(hsv, config):
    green_mask = _make_hsv_mask(hsv, config["green_lower"], config["green_upper"])
    yellow_mask = _make_hsv_mask(hsv, config["yellow_lower"], config["yellow_upper"])

    green_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, green_kernel)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, green_kernel)

    yellow_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    yellow_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5))
    yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, yellow_open)
    yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, yellow_close)
    return green_mask, yellow_mask


def _rect_center_x(rect):
    x, _, w, _ = rect
    return int(x + w // 2)


def _component_candidates(mask, kind, previous_rect=None):
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates = []
    roi_w = max(mask.shape[1], 1)
    previous_center = _rect_center_x(previous_rect) if previous_rect else None

    for index in range(1, count):
        x, y, w, h, area = [int(v) for v in stats[index]]
        if w <= 0 or h <= 0:
            continue

        fill = area / max(w * h, 1)
        if kind == "green":
            if area < 50 or w < 20 or h < 4 or h > 24:
                continue
            aspect = w / max(h, 1)
            if aspect < 3:
                continue
            area_score = min(area / 900, 1.0)
            aspect_score = min(aspect / 8, 1.0)
        else:
            if area < 20 or w < 2 or w > 16 or h < 8 or h > 40:
                continue
            aspect = h / max(w, 1)
            if aspect < 1.3:
                continue
            area_score = min(area / 120, 1.0)
            aspect_score = min(aspect / 3, 1.0)

        fill_score = min(fill / 0.65, 1.0)
        score = area_score * 0.45 + aspect_score * 0.35 + fill_score * 0.20

        if previous_center is not None:
            center = x + w / 2
            distance = abs(center - previous_center)
            continuity = max(0.0, 1.0 - distance / roi_w)
            score *= 0.75 + continuity * 0.25

        candidates.append(
            {
                "rect": (x, y, w, h),
                "area": area,
                "score": score,
                "center": int(x + w // 2),
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def _draw_bar_debug(roi_rgb, green_candidates, yellow_candidates, detection, note=""):
    debug = roi_rgb.copy()

    for candidate in green_candidates[:8]:
        x, y, w, h = candidate["rect"]
        cv2.rectangle(debug, (x, y), (x + w, y + h), (60, 150, 60), 1)

    for candidate in yellow_candidates[:8]:
        x, y, w, h = candidate["rect"]
        cv2.rectangle(debug, (x, y), (x + w, y + h), (160, 140, 30), 1)

    if detection.green_rect:
        x, y, w, h = detection.green_rect
        cv2.rectangle(debug, (x, y), (x + w, y + h), (40, 255, 80), 2)
        cv2.line(debug, (detection.green_center, 0), (detection.green_center, debug.shape[0]), (40, 255, 80), 1)

    if detection.yellow_rect:
        x, y, w, h = detection.yellow_rect
        cv2.rectangle(debug, (x, y), (x + w, y + h), (255, 220, 40), 2)
        cv2.line(debug, (detection.yellow_center, 0), (detection.yellow_center, debug.shape[0]), (255, 220, 40), 1)

    if detection.predicted_green_center is not None:
        cv2.line(debug, (detection.predicted_green_center, 0), (detection.predicted_green_center, debug.shape[0]), (0, 180, 255), 1)
    if detection.predicted_yellow_center is not None:
        cv2.line(debug, (detection.predicted_yellow_center, 0), (detection.predicted_yellow_center, debug.shape[0]), (255, 120, 0), 1)

    text = (
        f"conf={detection.confidence:.2f} stale={detection.stale_frames} "
        f"gv={detection.green_velocity:.0f} yv={detection.yellow_velocity:.0f}"
    )
    if note:
        text = f"{text} {note}"
    cv2.putText(debug, text, (8, max(16, debug.shape[0] - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return debug


def _clamp_center(value, roi_width):
    return int(max(0, min(roi_width - 1, round(value))))


def detect_bar_components(roi_rgb, config, previous_detection=None, make_debug=True, timestamp=None):
    if roi_rgb is None or roi_rgb.size == 0:
        return BarDetection(timestamp=timestamp or time.perf_counter())

    timestamp = timestamp or time.perf_counter()
    hsv = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2HSV)
    green_mask, yellow_mask = _prepare_bar_masks(hsv, config)

    previous_green = previous_detection.green_rect if previous_detection else None
    previous_yellow = previous_detection.yellow_rect if previous_detection else None
    green_candidates = _component_candidates(green_mask, "green", previous_green)
    yellow_candidates = _component_candidates(yellow_mask, "yellow", previous_yellow)

    green = green_candidates[0] if green_candidates else None
    yellow = yellow_candidates[0] if yellow_candidates else None

    stale_frames = 0
    note = ""
    if previous_detection and previous_detection.stale_frames < STALE_DETECTION_FRAMES:
        if green is None and previous_detection.green_rect is not None:
            green = {
                "rect": previous_detection.green_rect,
                "score": previous_detection.confidence * 0.45,
                "center": previous_detection.green_center,
            }
            stale_frames = previous_detection.stale_frames + 1
            note = "fallback"
        if yellow is None and previous_detection.yellow_rect is not None:
            yellow = {
                "rect": previous_detection.yellow_rect,
                "score": previous_detection.confidence * 0.45,
                "center": previous_detection.yellow_center,
            }
            stale_frames = max(stale_frames, previous_detection.stale_frames + 1)
            note = "fallback"

    detection = BarDetection(stale_frames=stale_frames, timestamp=timestamp)
    if green:
        detection.green_rect = green["rect"]
        detection.green_center = int(green["center"])
    if yellow:
        detection.yellow_rect = yellow["rect"]
        detection.yellow_center = int(yellow["center"])

    if green and yellow:
        detection.confidence = max(0.0, min(float(green["score"]), float(yellow["score"]), 1.0))

    roi_width = roi_rgb.shape[1]
    detection.predicted_green_center = detection.green_center
    detection.predicted_yellow_center = detection.yellow_center

    if previous_detection and previous_detection.timestamp:
        dt = timestamp - previous_detection.timestamp
        if 0 < dt <= MAX_PREDICTION_DT:
            if detection.stale_frames > 0:
                detection.green_velocity = previous_detection.green_velocity
                detection.yellow_velocity = previous_detection.yellow_velocity
            else:
                if detection.green_center is not None and previous_detection.green_center is not None:
                    detection.green_velocity = (detection.green_center - previous_detection.green_center) / dt
                if detection.yellow_center is not None and previous_detection.yellow_center is not None:
                    detection.yellow_velocity = (detection.yellow_center - previous_detection.yellow_center) / dt

            if detection.confidence >= MIN_PREDICTION_CONFIDENCE or detection.stale_frames > 0:
                if detection.green_center is not None:
                    detection.predicted_green_center = _clamp_center(
                        detection.green_center + detection.green_velocity * PREDICTION_HORIZON,
                        roi_width,
                    )
                if detection.yellow_center is not None:
                    detection.predicted_yellow_center = _clamp_center(
                        detection.yellow_center + detection.yellow_velocity * PREDICTION_HORIZON,
                        roi_width,
                    )

    if make_debug:
        detection.debug_frame = _draw_bar_debug(roi_rgb, green_candidates, yellow_candidates, detection, note)
    return detection


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
        return default_config.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    for key, value in default_config.items():
        if key not in config:
            config[key] = value

    return config


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def iter_path_candidates(file_path):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bases = [os.getcwd(), base_dir]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        bases.append(bundle_dir)

    if os.path.isabs(file_path):
        raw_candidates = [file_path]
    else:
        raw_candidates = [os.path.join(base, file_path) for base in bases]

    seen = set()
    for candidate in raw_candidates:
        absolute = os.path.abspath(candidate)
        key = os.path.normcase(absolute)
        if key in seen:
            continue
        seen.add(key)
        yield absolute


def resolve_existing_file(file_path):
    for candidate in iter_path_candidates(file_path):
        if os.path.exists(candidate):
            return candidate
    return None


def resolve_reference_image(kind):
    for source, file_path in REFERENCE_IMAGE_OPTIONS.get(kind, ()):
        resolved = resolve_existing_file(file_path)
        if resolved:
            return {
                "kind": kind,
                "source": source,
                "path": resolved,
                "file": os.path.basename(resolved),
            }
    return None


def expected_reference_files(kind):
    return ", ".join(os.path.basename(path) for _, path in REFERENCE_IMAGE_OPTIONS.get(kind, ()))


def find_example_image(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, CAPTURE_EXAMPLE_DIR, filename),
        os.path.join(os.getcwd(), "example", filename),
        os.path.join(base_dir, "example", filename),
        os.path.join(base_dir, "..", "example", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


def find_capture_example_image(roi_key):
    filename = CAPTURE_EXAMPLE_IMAGES.get(roi_key)
    if not filename:
        return None
    return find_example_image(filename)


class Tooltip:
    active_tooltip = None

    def __init__(self, widget, text_getter, image_path=None, delay=TOOLTIP_HOVER_DELAY_MS, max_image_width=420):
        self.widget = widget
        self.text_getter = text_getter
        self.image_path = image_path
        self.delay = delay
        self.max_image_width = max_image_width
        self.after_id = None
        self.window = None
        self.image_ref = None
        self.pinned = False

        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.on_leave, add="+")
        widget.bind("<FocusOut>", self.hide, add="+")

    def schedule(self, event=None):
        if self.pinned:
            return
        self.cancel_schedule()
        self.after_id = self.widget.after(self.delay, self.show)

    def cancel_schedule(self):
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def get_screen_bounds(self):
        try:
            left = int(self.widget.winfo_vrootx())
            top = int(self.widget.winfo_vrooty())
            width = int(self.widget.winfo_vrootwidth())
            height = int(self.widget.winfo_vrootheight())
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except tk.TclError:
            pass

        try:
            width = int(self.widget.winfo_screenwidth())
            height = int(self.widget.winfo_screenheight())
        except tk.TclError:
            width, height = 800, 600
        return 0, 0, width, height

    def place_within_screen(self):
        if self.window is None:
            return

        try:
            self.window.update_idletasks()
            tip_w = self.window.winfo_reqwidth()
            tip_h = self.window.winfo_reqheight()
            screen_left, screen_top, screen_right, screen_bottom = self.get_screen_bounds()
            margin = TOOLTIP_SCREEN_MARGIN

            widget_x = self.widget.winfo_rootx()
            widget_y = self.widget.winfo_rooty()
            widget_h = self.widget.winfo_height()

            x = widget_x + 18
            y = widget_y + widget_h + 8

            if x + tip_w + margin > screen_right:
                x = screen_right - tip_w - margin
            if x < screen_left + margin:
                x = screen_left + margin

            if y + tip_h + margin > screen_bottom:
                y = widget_y - tip_h - 8
            if y < screen_top + margin:
                y = screen_top + margin

            self.window.wm_geometry(f"+{int(x)}+{int(y)}")
        except tk.TclError:
            pass

    def show(self, pinned=False):
        self.after_id = None
        if Tooltip.active_tooltip is not None and Tooltip.active_tooltip is not self:
            Tooltip.active_tooltip.hide()
        self.hide()

        text = self.text_getter()
        if not text:
            return

        self.pinned = pinned

        screen_left, _, screen_right, _ = self.get_screen_bounds()
        available_width = max(160, screen_right - screen_left - (TOOLTIP_SCREEN_MARGIN * 2))
        content_width = max(120, min(self.max_image_width, available_width))

        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.attributes("-topmost", True)

        frame = tk.Frame(self.window, bg="#1F2328", bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        label = tk.Label(
            frame,
            text=text,
            justify="left",
            wraplength=content_width,
            bg="#1F2328",
            fg="#FFFFFF",
            padx=10,
            pady=8,
            font=("맑은 고딕", 10),
        )
        label.pack(fill="x")

        if self.image_path and os.path.exists(self.image_path):
            try:
                image = Image.open(self.image_path).convert("RGB")
                if image.width > content_width:
                    new_h = max(1, int(image.height * content_width / image.width))
                    image = image.resize((int(content_width), new_h), Image.Resampling.LANCZOS)
                self.image_ref = ImageTk.PhotoImage(image)
                image_label = tk.Label(frame, image=self.image_ref, bg="#1F2328", padx=10, pady=8)
                image_label.pack(fill="x")
            except Exception:
                self.image_ref = None

        self.place_within_screen()
        Tooltip.active_tooltip = self

    def toggle(self):
        self.cancel_schedule()
        if self.window is not None and self.pinned:
            self.hide()
            return
        self.show(pinned=True)

    def on_leave(self, event=None):
        if not self.pinned:
            self.hide()

    def hide(self, event=None):
        self.cancel_schedule()
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.image_ref = None
        self.pinned = False
        if Tooltip.active_tooltip is self:
            Tooltip.active_tooltip = None


class RegionSelector:
    def __init__(self, title_key, language="en", parent=None):
        self.parent = parent
        self.language = normalize_language(language)
        self.title_text = translate(self.language, title_key)
        self.start_x = 0
        self.start_y = 0
        self.rect = None
        self.result = None
        self.cancelled = False
        self.error_message = None
        self.closed = False
        self.focus_attempts = 0

        screenshot = pyautogui.screenshot()
        self.screenshot = screenshot.convert("RGB")
        self.screen_w, self.screen_h = self.screenshot.size

        self.root = tk.Toplevel(parent)
        self.root.title(translate(self.language, "overlay.title", title=self.title_text))
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(takefocus=True)
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)

        self.canvas = tk.Canvas(
            self.root,
            cursor="cross",
            width=self.screen_w,
            height=self.screen_h,
            highlightthickness=0,
            takefocus=True,
        )
        self.canvas.pack(fill="both", expand=True)

        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", self.cancel)
        self.root.bind("<KeyPress-Escape>", self.cancel)
        self.root.bind("<KeyRelease-Escape>", self.cancel)
        self.root.bind("<KeyPress>", self.on_key_press)
        self.canvas.bind("<Escape>", self.cancel)
        self.canvas.bind("<KeyPress-Escape>", self.cancel)
        self.canvas.bind("<KeyRelease-Escape>", self.cancel)
        self.canvas.bind("<KeyPress>", self.on_key_press)
        self.root.bind_all("<Escape>", self.cancel)
        self.root.bind_all("<KeyPress-Escape>", self.cancel)
        self.root.bind_all("<KeyRelease-Escape>", self.cancel)

        label = tk.Label(
            self.root,
            text=translate(self.language, "overlay.instruction", title=self.title_text),
            fg="white",
            bg="black",
            font=("맑은 고딕", 18, "bold"),
        )
        label.place(x=30, y=30)
        label.bind("<Escape>", self.cancel)
        label.bind("<KeyPress-Escape>", self.cancel)

        cancel_button = tk.Button(
            self.root,
            text=translate(self.language, "button.cancel_esc"),
            command=self.cancel,
            fg="white",
            bg="#D32F2F",
            activeforeground="white",
            activebackground="#A92727",
            font=("맑은 고딕", 12, "bold"),
            relief="flat",
            padx=14,
            pady=6,
        )
        cancel_button.place(x=30, y=72)
        cancel_button.bind("<Escape>", self.cancel)
        cancel_button.bind("<KeyPress-Escape>", self.cancel)

        try:
            self.root.grab_set()
            self.force_focus()
        except tk.TclError:
            pass
        self.root.after(50, self.force_focus)
        self.root.after(50, self.poll_escape_key)

    def force_focus(self):
        if self.closed:
            return

        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_set()
            self.root.focus_force()
            self.canvas.focus_set()
            self.canvas.focus_force()
        except tk.TclError:
            return

        self.focus_attempts += 1
        if self.focus_attempts < 12:
            self.root.after(100, self.force_focus)

    def poll_escape_key(self):
        if self.closed:
            return

        if os.name == "nt":
            try:
                if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
                    self.cancel()
                    return
            except Exception:
                pass

        try:
            self.root.after(50, self.poll_escape_key)
        except tk.TclError:
            pass

    def on_key_press(self, event):
        if event.keysym in ("Escape", "Esc") or event.keycode == 27:
            self.cancel(event)
            return "break"
        return None

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.root.unbind_all("<Escape>")
            self.root.unbind_all("<KeyPress-Escape>")
            self.root.unbind_all("<KeyRelease-Escape>")
            self.root.grab_release()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def cancel(self, event=None):
        self.cancelled = True
        self.result = None
        self.close()
        return "break"

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

        if self.rect:
            self.canvas.delete(self.rect)

        self.rect = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            self.start_x,
            self.start_y,
            outline="red",
            width=3,
        )

    def on_drag(self, event):
        if self.rect is None:
            return
        self.canvas.coords(
            self.rect,
            self.start_x,
            self.start_y,
            event.x,
            event.y,
        )

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        w = x2 - x1
        h = y2 - y1

        if w < 20 or h < 10:
            self.error_message = translate(self.language, "error.region_too_small")
            self.close()
            return

        self.result = ([x1, y1, w, h], self.screenshot)
        self.close()


class DetectionAreaPreview:
    def __init__(self, areas, language="en", parent=None):
        self.parent = parent
        self.language = normalize_language(language)
        self.areas = areas
        self.closed = False
        self.focus_attempts = 0

        screenshot = pyautogui.screenshot()
        self.screenshot = screenshot.convert("RGB")
        self.screen_w, self.screen_h = self.screenshot.size

        self.root = tk.Toplevel(parent)
        self.root.title(translate(self.language, "button.preview_areas"))
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(takefocus=True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.canvas = tk.Canvas(
            self.root,
            cursor="hand2",
            width=self.screen_w,
            height=self.screen_h,
            highlightthickness=0,
            takefocus=True,
        )
        self.canvas.pack(fill="both", expand=True)

        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        self.draw_areas()

        label = tk.Label(
            self.root,
            text=translate(self.language, "preview.instruction"),
            fg="white",
            bg="black",
            font=("맑은 고딕", 18, "bold"),
        )
        label.place(x=30, y=30)

        close_button = tk.Button(
            self.root,
            text=translate(self.language, "button.cancel_esc"),
            command=self.close,
            fg="white",
            bg="#D32F2F",
            activeforeground="white",
            activebackground="#A92727",
            font=("맑은 고딕", 12, "bold"),
            relief="flat",
            padx=14,
            pady=6,
        )
        close_button.place(x=30, y=72)

        self.canvas.bind("<ButtonPress-1>", self.close)
        self.root.bind("<Escape>", self.close)
        self.root.bind("<KeyPress-Escape>", self.close)
        self.root.bind("<KeyRelease-Escape>", self.close)
        self.canvas.bind("<Escape>", self.close)
        self.canvas.bind("<KeyPress-Escape>", self.close)
        self.root.bind_all("<Escape>", self.close)
        self.root.bind_all("<KeyPress-Escape>", self.close)

        try:
            self.root.grab_set()
            self.force_focus()
        except tk.TclError:
            pass
        self.root.after(50, self.force_focus)
        self.root.after(50, self.poll_escape_key)

    def draw_areas(self):
        for area in self.areas:
            x, y, w, h = area["roi"]
            color = area["color"]
            label = area["label"]
            x2 = x + w
            y2 = y + h
            self.canvas.create_rectangle(x, y, x2, y2, outline=color, width=4)
            text_x = max(4, x)
            text_y = max(4, y - 28)
            text = self.canvas.create_text(
                text_x + 8,
                text_y + 5,
                text=label,
                fill="white",
                anchor="nw",
                font=("맑은 고딕", 14, "bold"),
            )
            bbox = self.canvas.bbox(text)
            if bbox:
                background = self.canvas.create_rectangle(
                    bbox[0] - 6,
                    bbox[1] - 4,
                    bbox[2] + 6,
                    bbox[3] + 4,
                    fill="black",
                    outline=color,
                    width=2,
                )
                self.canvas.tag_raise(text, background)

    def force_focus(self):
        if self.closed:
            return
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.canvas.focus_force()
        except tk.TclError:
            return
        self.focus_attempts += 1
        if self.focus_attempts < 12:
            self.root.after(100, self.force_focus)

    def poll_escape_key(self):
        if self.closed:
            return
        if os.name == "nt":
            try:
                if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
                    self.close()
                    return
            except Exception:
                pass
        try:
            self.root.after(50, self.poll_escape_key)
        except tk.TclError:
            pass

    def close(self, event=None):
        if self.closed:
            return "break"
        self.closed = True
        try:
            self.root.unbind_all("<Escape>")
            self.root.unbind_all("<KeyPress-Escape>")
            self.root.grab_release()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        return "break"


class FishingMacroGUI:
    def __init__(self):
        self.config = load_config()
        self.language = normalize_language(self.config.get("language", default_config["language"]))
        self.config["language"] = self.language
        self.running = False
        self.thread = None
        self.pressed_key = None
        self.last_bite_time = 0
        self.last_success_time = 0
        self.no_detection_since = time.time()
        self.no_detection_retry_count = 0
        self.fishing_active = False
        self.last_bar_detection = None
        self.reference_image_cache = {}
        self.last_status_update = 0
        self.last_debug_update = 0
        self.last_perf_update = 0
        self.debug_panel = None
        self.debug_image_label = None
        self.debug_metrics_label = None
        self.debug_photo = None
        self.perf_label = None
        self.run_state_label = None
        self.input_state_label = None
        self.fishing_state_label = None
        self.retry_count_label = None
        self.toast_label = None
        self.toast_after_id = None
        self.roi_summary_labels = {}
        self.slider_value_labels = {}
        self.i18n_widgets = []
        self.tooltips = []
        self.status_key = "status.ready"
        self.status_kwargs = {}
        self.status_color = "#8A8A8A"
        self.capture_backend = ScreenCapture()
        self.perf_stats = PerformanceStats()

        enable_dpi_awareness()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(self.t("app.title"))
        self.root.geometry("680x860")
        self.root.minsize(520, 620)
        self.root.resizable(True, True)
        self.build_ui()

    def t(self, text_key, **kwargs):
        return translate(self.language, text_key, **kwargs)

    def register_i18n(self, widget, key, attr="text", **kwargs):
        self.i18n_widgets.append((widget, key, attr, kwargs))
        try:
            widget.configure(**{attr: self.t(key, **kwargs)})
        except tk.TclError:
            pass
        return widget

    def make_help_button(self, parent, tooltip_key, image_path=None):
        button = ctk.CTkButton(
            parent,
            text="?",
            width=26,
            height=24,
            fg_color="#6B7280",
            hover_color="#4B5563",
        )
        tooltip = Tooltip(button, lambda key=tooltip_key: self.t(key), image_path=image_path)
        button.configure(command=tooltip.toggle)
        self.tooltips.append(tooltip)
        return button

    def set_status_key(self, status_key, fg, force=False, **kwargs):
        self.status_key = status_key
        self.status_kwargs = kwargs
        self.status_color = fg
        self.set_status(self.t(status_key, **kwargs), fg, force=force)

    def refresh_language(self):
        if Tooltip.active_tooltip is not None:
            Tooltip.active_tooltip.hide()
        self.root.title(self.t("app.title"))
        for widget, key, attr, kwargs in self.i18n_widgets:
            try:
                widget.configure(**{attr: self.t(key, **kwargs)})
            except tk.TclError:
                pass

        if hasattr(self, "language_menu"):
            self.language_menu.set(LANGUAGE_NAMES[self.language])

        self.refresh_roi_summary()
        self.refresh_slider_labels()
        self.refresh_runtime_summary()
        self.set_status(self.t(self.status_key, **self.status_kwargs), self.status_color, force=True)
        self.schedule_performance_update(force=True)
        if self.debug_var.get() and self.debug_metrics_label is not None:
            self.debug_metrics_label.configure(text=self.t("debug.waiting", summary=self.perf_stats.summary_text()))
        if self.debug_image_label is not None and self.debug_photo is None:
            self.debug_image_label.config(text=self.t("debug.image_waiting"))
        self.btn_start.configure(text=self.t("button.stop" if self.running else "button.start"))

    def on_language_change(self, display_name):
        self.language = LANGUAGE_CODES_BY_NAME.get(display_name, default_config["language"])
        self.config["language"] = self.language
        save_config(self.config)
        self.refresh_language()
        self.show_toast(self.t("toast.language_saved"))

    def _make_section(self, parent, title, subtitle=None):
        section = ctk.CTkFrame(parent, corner_radius=16)
        section.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(section, text="", font=("맑은 고딕", 16, "bold"), anchor="w")
        self.register_i18n(title_label, title)
        title_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 2))

        if subtitle:
            subtitle_label = ctk.CTkLabel(section, text="", font=("맑은 고딕", 11), text_color="#8A8A8A", anchor="w")
            self.register_i18n(subtitle_label, subtitle)
            subtitle_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
            body_row = 2
        else:
            body_row = 1

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.grid(row=body_row, column=0, sticky="ew", padx=16, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)
        return section, body

    def _make_runtime_chip(self, parent, column, title_key, value):
        chip = ctk.CTkFrame(parent, corner_radius=12)
        chip.grid(row=0, column=column, sticky="ew", padx=4, pady=4)
        chip.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(chip, text="", font=("맑은 고딕", 11), text_color="#7A7A7A", anchor="w")
        self.register_i18n(title_label, title_key)
        title_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(10, 0),
        )
        value_label = ctk.CTkLabel(chip, text=value, font=("맑은 고딕", 14, "bold"), anchor="w")
        value_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 10))
        return value_label

    def _make_roi_card(self, parent, row, title_key, roi_key, reference_file, command, tooltip_key):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", padx=2, pady=5)
        card.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(card, text="", font=("맑은 고딕", 14, "bold"), anchor="w")
        self.register_i18n(title_label, title_key)
        title_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=14,
            pady=(12, 0),
        )
        state_label = ctk.CTkLabel(card, text="", font=("맑은 고딕", 11, "bold"), anchor="e")
        state_label.grid(row=0, column=1, sticky="e", padx=(4, 6), pady=(12, 0))
        example_image = find_capture_example_image(roi_key)
        self.make_help_button(card, tooltip_key, example_image).grid(row=0, column=2, sticky="e", padx=(0, 14), pady=(12, 0))

        roi_label = ctk.CTkLabel(card, text="", font=("맑은 고딕", 11), text_color="#6F6F6F", anchor="w")
        roi_label.grid(row=1, column=0, columnspan=3, sticky="ew", padx=14, pady=(4, 0))

        reference_label = ctk.CTkLabel(card, text="", font=("맑은 고딕", 11), text_color="#6F6F6F", anchor="w")
        reference_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 12))

        reselect_button = ctk.CTkButton(card, text="", width=92, height=30, command=command)
        self.register_i18n(reselect_button, "button.reselect")
        reselect_button.grid(
            row=2,
            column=2,
            sticky="e",
            padx=14,
            pady=(2, 12),
        )

        self.roi_summary_labels[roi_key] = {
            "roi": roi_label,
            "state": state_label,
            "reference": reference_label,
            "reference_file": reference_file,
            "reference_kind": ROI_REFERENCE_KIND.get(roi_key),
        }
        return card

    def _make_slider_row(self, parent, row, key, title_key, description_key, variable, from_, to, steps, formatter, tooltip_key):
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.grid(row=row, column=0, sticky="ew", padx=2, pady=(4, 12))
        row_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(row_frame, text="", font=("맑은 고딕", 13, "bold"), anchor="w")
        self.register_i18n(title_label, title_key)
        title_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=4,
            pady=(0, 0),
        )
        value_label = ctk.CTkLabel(row_frame, text="", font=("맑은 고딕", 12, "bold"), text_color="#2F80D0", anchor="e")
        value_label.grid(row=0, column=1, sticky="e", padx=4, pady=(0, 0))
        self.make_help_button(row_frame, tooltip_key).grid(row=0, column=2, sticky="e", padx=(0, 4), pady=(0, 0))

        desc_label = ctk.CTkLabel(row_frame, text="", font=("맑은 고딕", 10), text_color="#7A7A7A", anchor="w")
        self.register_i18n(desc_label, description_key)
        desc_label.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=4,
            pady=(0, 4),
        )

        slider = ctk.CTkSlider(
            row_frame,
            from_=from_,
            to=to,
            number_of_steps=steps,
            variable=variable,
            command=lambda value, slider_key=key: self.update_slider_label(slider_key, value),
        )
        slider.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 0))

        self.slider_value_labels[key] = {
            "label": value_label,
            "variable": variable,
            "formatter": formatter,
        }
        self.update_slider_label(key)
        return slider

    def _coerce_slider_value(self, key, value):
        if key == "deadzone":
            return int(round(float(value)))
        if key == "loop_delay":
            return int(round(float(value) / 5) * 5)
        if key == "no_detection_retry_seconds":
            return int(round(float(value)))
        return round(float(value), 2)

    def update_slider_label(self, key, value=None):
        item = self.slider_value_labels.get(key)
        if not item:
            return

        variable = item["variable"]
        if value is None:
            value = variable.get()

        value = self._coerce_slider_value(key, value)
        variable.set(value)
        item["label"].configure(text=item["formatter"](value))

    def refresh_slider_labels(self):
        for key in self.slider_value_labels:
            self.update_slider_label(key)

    def refresh_roi_summary(self):
        for roi_key, labels in self.roi_summary_labels.items():
            roi = self.config.get(roi_key)
            valid = is_valid_roi(roi)

            if valid:
                roi_text = self.t("roi.coords", x=int(roi[0]), y=int(roi[1]), w=int(roi[2]), h=int(roi[3]))
                labels["state"].configure(text=self.t("state.configured"), text_color="#2EAD5B")
            else:
                roi_text = self.t("roi.unset")
                labels["state"].configure(text=self.t("state.unconfigured"), text_color="#D32F2F")

            reference_kind = labels["reference_kind"]
            if reference_kind is None:
                reference_text = self.t("reference.unused")
            else:
                resolved = resolve_reference_image(reference_kind)
                if resolved and resolved["source"] == "capture":
                    reference_text = self.t("reference.capture_present", file=resolved["file"])
                elif resolved and resolved["source"] == "legacy":
                    reference_text = self.t("reference.legacy_present", file=resolved["file"])
                else:
                    reference_text = self.t("reference.missing", files=expected_reference_files(reference_kind))

            labels["roi"].configure(text=roi_text)
            labels["reference"].configure(text=reference_text)

    def refresh_runtime_summary(self):
        if self.run_state_label is None:
            return

        run_text = self.t("state.running") if self.running else self.t("state.idle")
        key_text = self.t("state.key_input", key=self.pressed_key.upper()) if self.pressed_key else self.t("state.no_input")
        fishing_text = self.t("state.on") if self.fishing_active else self.t("state.off")
        retry_enabled = (
            self.no_detection_retry_var.get()
            if hasattr(self, "no_detection_retry_var")
            else self.config.get("no_detection_retry_enabled", False)
        )
        retry_text = self.t("state.retry_count", count=self.no_detection_retry_count) if retry_enabled else self.t("state.off")

        self.run_state_label.configure(text=run_text, text_color="#2EAD5B" if self.running else "#7A7A7A")
        self.input_state_label.configure(text=key_text, text_color="#2F80D0" if self.pressed_key else "#7A7A7A")
        self.fishing_state_label.configure(text=fishing_text, text_color="#2EAD5B" if self.fishing_active else "#7A7A7A")
        self.retry_count_label.configure(
            text=retry_text,
            text_color="#E08A1E" if retry_enabled and self.no_detection_retry_count > 0 else "#7A7A7A",
        )

    def get_detection_preview_areas(self):
        specs = [
            ("bar_roi", "roi.bar", "#2EAD5B"),
            ("bite_roi", "roi.bite", "#F2994A"),
            ("success_roi", "roi.success", "#2F80D0"),
        ]
        areas = []
        missing_count = 0
        for roi_key, label_key, color in specs:
            roi = self.config.get(roi_key)
            valid = is_valid_roi(roi)
            if not valid:
                missing_count += 1
                continue
            areas.append(
                {
                    "roi": [int(value) for value in roi],
                    "label": self.t(label_key),
                    "color": color,
                }
            )
        return areas, missing_count

    def show_detection_area_preview(self):
        areas, missing_count = self.get_detection_preview_areas()
        if not areas:
            self.show_toast(self.t("toast.preview_no_areas"), color="#E08A1E")
            return

        self.root.withdraw()
        self.root.update()
        time.sleep(0.08)

        try:
            preview = DetectionAreaPreview(areas, language=self.language, parent=self.root)
            preview.root.wait_window()
        except Exception as e:
            self.restore_main_window()
            self.root.after(
                120,
                lambda: messagebox.showwarning(
                    self.t("dialog.region_error.title"),
                    str(e),
                    parent=self.root,
                ),
            )
            return

        self.restore_main_window()
        if missing_count:
            self.show_toast(self.t("toast.preview_missing"), color="#E08A1E")

    def build_ui(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title_label = ctk.CTkLabel(header, text="", font=("맑은 고딕", 24, "bold"), anchor="w")
        self.register_i18n(title_label, "app.title")
        title_label.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        language_frame = ctk.CTkFrame(header, fg_color="transparent")
        language_frame.grid(row=0, column=1, sticky="e", padx=(12, 0))
        language_label = ctk.CTkLabel(language_frame, text="", font=("맑은 고딕", 11, "bold"), text_color="#6F6F6F")
        self.register_i18n(language_label, "language.label")
        language_label.grid(row=0, column=0, padx=(0, 6))
        self.language_menu = ctk.CTkOptionMenu(
            language_frame,
            values=list(LANGUAGE_NAMES.values()),
            width=130,
            command=self.on_language_change,
        )
        self.language_menu.grid(row=0, column=1)
        self.language_menu.set(LANGUAGE_NAMES[self.language])

        self.perf_label = ctk.CTkLabel(
            header,
            text=self.t("perf.waiting"),
            font=("맑은 고딕", 11, "bold"),
            text_color="#6F6F6F",
            anchor="e",
        )
        self.perf_label.grid(row=1, column=1, sticky="e", padx=(12, 0), pady=(4, 0))

        self.status_label = ctk.CTkLabel(
            header,
            text=self.t("status.ready"),
            font=("맑은 고딕", 12, "bold"),
            text_color="#8A8A8A",
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.toast_label = ctk.CTkLabel(header, text="", font=("맑은 고딕", 12, "bold"), text_color="#47C878", anchor="w")
        self.toast_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        content = ctk.CTkScrollableFrame(self.root, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=4)
        content.grid_columnconfigure(0, weight=1)

        run_section, run_body = self._make_section(
            content,
            "section.status.title",
            "section.status.subtitle",
        )
        run_section.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(4):
            run_body.grid_columnconfigure(column, weight=1)
        self.run_state_label = self._make_runtime_chip(run_body, 0, "chip.macro", self.t("state.idle"))
        self.input_state_label = self._make_runtime_chip(run_body, 1, "chip.input", self.t("state.no_input"))
        self.fishing_state_label = self._make_runtime_chip(run_body, 2, "chip.success_detection", self.t("state.off"))
        self.retry_count_label = self._make_runtime_chip(run_body, 3, "chip.retry", self.t("state.off"))

        action_section, action_body = self._make_section(
            content,
            "section.roi.title",
            "section.roi.subtitle",
        )
        action_section.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        action_body.grid_columnconfigure(0, weight=1)
        self._make_roi_card(
            action_body,
            0,
            "roi.bar",
            "bar_roi",
            None,
            self.select_bar_region,
            "tooltip.roi.bar",
        )
        self._make_roi_card(
            action_body,
            1,
            "roi.bite",
            "bite_roi",
            BITE_REFERENCE_FILE,
            self.setup_bite_detection,
            "tooltip.roi.bite",
        )
        self._make_roi_card(
            action_body,
            2,
            "roi.success",
            "success_roi",
            SUCCESS_REFERENCE_FILE,
            self.setup_success_detection,
            "tooltip.roi.success",
        )
        preview_row = ctk.CTkFrame(action_body, fg_color="transparent")
        preview_row.grid(row=3, column=0, sticky="ew", padx=2, pady=(6, 0))
        preview_row.grid_columnconfigure(0, weight=1)
        preview_button = ctk.CTkButton(
            preview_row,
            text="",
            height=36,
            fg_color="#5F6B7A",
            hover_color="#4B5563",
            command=self.show_detection_area_preview,
        )
        self.register_i18n(preview_button, "button.preview_areas")
        preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.make_help_button(preview_row, "tooltip.preview_areas").grid(row=0, column=1, sticky="e")

        settings_section, settings_body = self._make_section(
            content,
            "section.detect.title",
            "section.detect.subtitle",
        )
        settings_section.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self.deadzone_var = tk.DoubleVar(value=float(self.config["deadzone"]))
        self.delay_var = tk.DoubleVar(value=float(self.config["loop_delay"]) * 1000)
        self.bite_match_var = tk.DoubleVar(value=float(self.config["bite_match_threshold"]))
        self.success_match_var = tk.DoubleVar(value=float(self.config["success_match_threshold"]))
        self._make_slider_row(
            settings_body,
            0,
            "deadzone",
            "setting.deadzone.title",
            "setting.deadzone.desc",
            self.deadzone_var,
            0,
            30,
            30,
            lambda value: f"{int(value)} px",
            "tooltip.deadzone",
        )
        self._make_slider_row(
            settings_body,
            1,
            "loop_delay",
            "setting.loop_delay.title",
            "setting.loop_delay.desc",
            self.delay_var,
            5,
            120,
            23,
            lambda value: f"{int(value)} ms",
            "tooltip.loop_delay",
        )
        self._make_slider_row(
            settings_body,
            2,
            "bite_match_threshold",
            "setting.bite_threshold.title",
            "setting.bite_threshold.desc",
            self.bite_match_var,
            0.50,
            0.95,
            45,
            lambda value: f"{float(value):.2f}",
            "tooltip.bite_threshold",
        )
        self._make_slider_row(
            settings_body,
            3,
            "success_match_threshold",
            "setting.success_threshold.title",
            "setting.success_threshold.desc",
            self.success_match_var,
            0.50,
            0.95,
            45,
            lambda value: f"{float(value):.2f}",
            "tooltip.success_threshold",
        )
        reset_button = ctk.CTkButton(
            settings_body,
            text="",
            height=36,
            fg_color="#5F6B7A",
            hover_color="#4B5563",
            command=self.reset_detection_defaults,
        )
        self.register_i18n(reset_button, "button.reset_defaults")
        reset_button.grid(row=4, column=0, sticky="ew", padx=2, pady=(0, 4))
        self.make_help_button(settings_body, "tooltip.reset_defaults").grid(row=5, column=0, sticky="e", padx=2, pady=(0, 0))

        option_section, option_body = self._make_section(content, "section.options.title")
        option_section.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        option_body.grid_columnconfigure(0, weight=1)
        self.invert_var = tk.BooleanVar(value=self.config.get("invert_control", False))
        invert_switch = ctk.CTkSwitch(
            option_body,
            text="",
            variable=self.invert_var,
            font=("맑은 고딕", 10),
        )
        self.register_i18n(invert_switch, "option.invert")
        invert_switch.grid(row=0, column=0, sticky="w", padx=4, pady=6)
        self.make_help_button(option_body, "tooltip.invert").grid(row=0, column=1, sticky="e", padx=4, pady=6)

        self.no_detection_retry_var = tk.BooleanVar(value=self.config.get("no_detection_retry_enabled", False))
        self.no_detection_retry_seconds_var = tk.DoubleVar(
            value=float(self.config.get("no_detection_retry_seconds", default_config["no_detection_retry_seconds"]))
        )
        retry_switch = ctk.CTkSwitch(
            option_body,
            text="",
            variable=self.no_detection_retry_var,
            font=("맑은 고딕", 10),
            command=self.queue_runtime_summary,
        )
        self.register_i18n(retry_switch, "option.no_detection_retry")
        retry_switch.grid(row=1, column=0, sticky="w", padx=4, pady=6)
        self.make_help_button(option_body, "tooltip.no_detection_retry").grid(row=1, column=1, sticky="e", padx=4, pady=6)
        self._make_slider_row(
            option_body,
            2,
            "no_detection_retry_seconds",
            "setting.retry_seconds.title",
            "setting.retry_seconds.desc",
            self.no_detection_retry_seconds_var,
            10,
            60,
            50,
            lambda value: f"{int(value)} s",
            "tooltip.no_detection_retry",
        )

        self.debug_var = tk.BooleanVar(value=False)
        debug_switch = ctk.CTkSwitch(
            option_body,
            text="",
            variable=self.debug_var,
            font=("맑은 고딕", 10),
            command=self.toggle_debug_window,
        )
        self.register_i18n(debug_switch, "option.debug")
        debug_switch.grid(row=3, column=0, sticky="w", padx=4, pady=6)
        self.make_help_button(option_body, "tooltip.debug").grid(row=3, column=1, sticky="e", padx=4, pady=6)

        self.debug_panel, debug_body = self._make_section(
            content,
            "section.debug.title",
            "section.debug.subtitle",
        )
        self.debug_panel.grid(row=4, column=0, sticky="ew", pady=(0, 16))
        debug_body.grid_columnconfigure(0, weight=1)
        self.debug_metrics_label = ctk.CTkLabel(
            debug_body,
            text=self.t("debug.placeholder"),
            font=("맑은 고딕", 11, "bold"),
            text_color="#6F6F6F",
            anchor="w",
        )
        self.debug_metrics_label.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 8))
        self.debug_image_label = tk.Label(
            debug_body,
            text=self.t("debug.image_waiting"),
            bg="#1F2328",
            fg="#FFFFFF",
            width=72,
            height=8,
            anchor="center",
        )
        self.debug_image_label.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        self.debug_panel.grid_remove()

        button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(8, 18))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=2)
        button_frame.grid_columnconfigure(2, weight=1)

        self.btn_save = ctk.CTkButton(
            button_frame,
            text="",
            font=("맑은 고딕", 13, "bold"),
            height=46,
            command=self.save_current_config,
        )
        self.register_i18n(self.btn_save, "button.save")
        self.make_help_button(button_frame, "tooltip.save").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=(4, 0))
        self.btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_start = ctk.CTkButton(
            button_frame,
            text=self.t("button.start"),
            font=("맑은 고딕", 14, "bold"),
            height=46,
            fg_color="#2EAD5B",
            hover_color="#238947",
            command=self.toggle_macro,
        )
        self.make_help_button(button_frame, "tooltip.start").grid(row=1, column=1, sticky="e", padx=6, pady=(4, 0))
        self.btn_start.grid(row=0, column=1, sticky="ew", padx=6)

        self.btn_exit = ctk.CTkButton(
            button_frame,
            text="",
            font=("맑은 고딕", 14, "bold"),
            height=46,
            fg_color="#4A4A4A",
            hover_color="#363636",
            command=self.on_close,
        )
        self.register_i18n(self.btn_exit, "button.exit")
        self.make_help_button(button_frame, "tooltip.exit").grid(row=1, column=2, sticky="e", padx=(6, 0), pady=(4, 0))
        self.btn_exit.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_roi_summary()
        self.refresh_runtime_summary()

    def select_bar_region(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.08)

        selector = RegionSelector("roi.bar", language=self.language, parent=self.root)
        selector.root.wait_window()

        self.restore_main_window()
        if selector.error_message:
            self.root.after(120, lambda: messagebox.showwarning(self.t("dialog.region_error.title"), selector.error_message, parent=self.root))
            return
        if selector.result is None:
            return

        roi, _ = selector.result
        self.config["bar_roi"] = roi
        self.save_current_config(show_message=False)
        self.refresh_roi_summary()
        self.show_toast(self.t("toast.bar_saved"))

    def setup_bite_detection(self):
        self.setup_reference_detection(
            title_key="roi.bite",
            roi_key="bite_roi",
            file_path=BITE_REFERENCE_FILE,
            done_key="toast.bite_saved",
        )

    def setup_success_detection(self):
        self.setup_reference_detection(
            title_key="roi.success",
            roi_key="success_roi",
            file_path=SUCCESS_REFERENCE_FILE,
            done_key="toast.success_saved",
        )

    def setup_reference_detection(self, title_key, roi_key, file_path, done_key):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.08)

        selector = RegionSelector(title_key, language=self.language, parent=self.root)
        selector.root.wait_window()

        self.restore_main_window()
        if selector.error_message:
            self.root.after(120, lambda: messagebox.showwarning(self.t("dialog.region_error.title"), selector.error_message, parent=self.root))
            return
        if selector.result is None:
            return

        roi, screenshot = selector.result
        x, y, w, h = roi
        self.config[roi_key] = roi
        cropped = screenshot.crop((x, y, x + w, y + h))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        cropped.save(file_path)
        self.save_current_config(show_message=False)
        self.refresh_roi_summary()
        self.show_toast(self.t(done_key))

    def restore_main_window(self):
        def restore():
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                pass

        self.root.after(50, restore)

    def show_toast(self, text, color="#47C878", duration=2000):
        if self.toast_label is None:
            return

        if self.toast_after_id is not None:
            try:
                self.root.after_cancel(self.toast_after_id)
            except tk.TclError:
                pass
            self.toast_after_id = None

        self.toast_label.configure(text=text, text_color=color)

        def clear():
            if self.toast_label is not None:
                self.toast_label.configure(text="")
            self.toast_after_id = None

        self.toast_after_id = self.root.after(duration, clear)

    def save_current_config(self, show_message=True):
        try:
            self.refresh_slider_labels()
            self.config["deadzone"] = int(round(float(self.deadzone_var.get())))
            self.config["loop_delay"] = round(float(self.delay_var.get()) / 1000, 3)
            self.config["bite_match_threshold"] = round(float(self.bite_match_var.get()), 2)
            self.config["success_match_threshold"] = round(float(self.success_match_var.get()), 2)
            self.config["invert_control"] = self.invert_var.get()
            self.config["no_detection_retry_enabled"] = self.no_detection_retry_var.get()
            self.config["no_detection_retry_seconds"] = int(round(float(self.no_detection_retry_seconds_var.get())))
            self.config["language"] = self.language
            save_config(self.config)
            if show_message:
                self.show_toast(self.t("toast.settings_saved"))
        except (ValueError, tk.TclError):
            messagebox.showerror(self.t("dialog.input_error.title"), self.t("dialog.input_error.body"), parent=self.root)

    def reset_detection_defaults(self):
        self.deadzone_var.set(float(default_config["deadzone"]))
        self.delay_var.set(float(default_config["loop_delay"]) * 1000)
        self.bite_match_var.set(float(default_config["bite_match_threshold"]))
        self.success_match_var.set(float(default_config["success_match_threshold"]))
        self.refresh_slider_labels()
        self.show_toast(self.t("toast.defaults_reset"))

    def press_hold(self, key):
        if self.pressed_key == key:
            return

        self.release_all()
        pydirectinput.keyDown(key)
        self.pressed_key = key
        self.queue_runtime_summary()

    def release_all(self):
        if self.pressed_key is not None:
            pydirectinput.keyUp(self.pressed_key)
            self.pressed_key = None
            self.queue_runtime_summary()

    def queue_runtime_summary(self):
        try:
            self.root.after(0, self.refresh_runtime_summary)
        except tk.TclError:
            pass

    def set_status(self, text, fg, force=False):
        now = time.time()
        if not force and now - self.last_status_update < STATUS_UPDATE_INTERVAL:
            return

        self.last_status_update = now

        def update():
            if self.status_label.winfo_exists():
                self.status_label.configure(text=text, text_color=fg)
            self.refresh_runtime_summary()

        try:
            self.root.after(0, update)
        except tk.TclError:
            pass

    def toggle_debug_window(self):
        self.toggle_debug_panel()

    def toggle_debug_panel(self):
        if self.debug_panel is None:
            return

        if self.debug_var.get():
            self.debug_panel.grid()
            if self.debug_metrics_label is not None:
                self.debug_metrics_label.configure(text=self.t("debug.waiting", summary=self.perf_stats.summary_text()))
        else:
            self.debug_panel.grid_remove()

    def ensure_debug_window(self):
        if not self.debug_var.get():
            self.debug_var.set(True)
        self.toggle_debug_panel()

    def close_debug_window(self):
        if self.debug_var.get():
            self.debug_var.set(False)
        self.toggle_debug_panel()
        self.debug_photo = None

    def schedule_debug_update(self, detection, diff=None):
        if not self.debug_var.get() or detection is None or detection.debug_frame is None:
            return

        now = time.time()
        if now - self.last_debug_update < DEBUG_UPDATE_INTERVAL:
            return
        self.last_debug_update = now

        frame = detection.debug_frame.copy()
        if diff is not None:
            cv2.putText(
                frame,
                f"diff={diff}",
                (8, 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        cv2.putText(
            frame,
            self.perf_stats.summary_text(),
            (8, 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        metrics_text = (
            f"{self.perf_stats.summary_text()} | "
            f"conf={detection.confidence:.2f} | "
            f"stale={detection.stale_frames}"
        )
        if diff is not None:
            metrics_text = f"{metrics_text} | diff={diff}"

        def update():
            if not self.debug_var.get():
                return
            self.toggle_debug_panel()
            image = Image.fromarray(frame)
            max_w = 620
            if image.width > max_w:
                new_h = max(1, int(image.height * max_w / image.width))
                image = image.resize((max_w, new_h), Image.Resampling.NEAREST)
            self.debug_photo = ImageTk.PhotoImage(image)
            self.debug_metrics_label.configure(text=metrics_text)
            self.debug_image_label.config(image=self.debug_photo, text="", width=0, height=0)

        try:
            self.root.after(0, update)
        except tk.TclError:
            pass

    def get_reference_image(self, image_file):
        if not os.path.exists(image_file):
            return None

        try:
            mtime = os.path.getmtime(image_file)
        except OSError:
            return None

        cached = self.reference_image_cache.get(image_file)
        if cached and cached["mtime"] == mtime:
            return cached["image"]

        image = cv2.imread(image_file)
        if image is None:
            return None
        self.reference_image_cache[image_file] = {"mtime": mtime, "image": image}
        return image

    def get_capture_region(self):
        rois = []
        for key in ("bar_roi", "bite_roi", "success_roi"):
            roi = self.config.get(key)
            if not is_valid_roi(roi):
                continue
            x, y, w, h = [int(v) for v in roi]
            rois.append((x, y, w, h))

        if not rois:
            return None

        try:
            screen_w, screen_h = self.capture_backend.size()
        except Exception:
            screen_w, screen_h = 0, 0

        margin = 6
        x1 = min(x for x, _, _, _ in rois) - margin
        y1 = min(y for _, y, _, _ in rois) - margin
        x2 = max(x + w for x, _, w, _ in rois) + margin
        y2 = max(y + h for _, y, _, h in rois) + margin

        x1 = max(0, x1)
        y1 = max(0, y1)
        if screen_w > 0:
            x2 = min(screen_w, x2)
        if screen_h > 0:
            y2 = min(screen_h, y2)

        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        return int(x1), int(y1), int(width), int(height)

    def capture_screen(self):
        region = self.get_capture_region()
        return self.capture_backend.grab(region)

    def crop_roi(self, screen, roi_key, offset=(0, 0)):
        if not is_valid_roi(self.config.get(roi_key)):
            return np.empty((0, 0, 3), dtype=screen.dtype)
        x, y, w, h = [int(v) for v in self.config[roi_key]]
        local_x = x - offset[0]
        local_y = y - offset[1]

        x1 = max(0, local_x)
        y1 = max(0, local_y)
        x2 = min(screen.shape[1], local_x + w)
        y2 = min(screen.shape[0], local_y + h)

        if x2 <= x1 or y2 <= y1:
            return screen[0:0, 0:0]
        return screen[y1:y2, x1:x2]

    def check_reference_image(self, screen, offset, roi_key, image_kind, threshold_key):
        resolved = resolve_reference_image(image_kind)
        if resolved is None:
            return False, 0.0

        reference = self.get_reference_image(resolved["path"])
        if reference is None:
            return False, 0.0

        roi = self.crop_roi(screen, roi_key, offset)
        if roi.size == 0:
            return False, 0.0

        roi_bgr = cv2.cvtColor(roi, cv2.COLOR_RGB2BGR)
        if reference.shape[0] > roi_bgr.shape[0] or reference.shape[1] > roi_bgr.shape[1]:
            return False, 0.0

        result = cv2.matchTemplate(roi_bgr, reference, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        detected = max_val >= self.config[threshold_key]
        return detected, max_val

    def make_mask(self, hsv, lower, upper):
        lower = np.array(lower, dtype=np.uint8)
        upper = np.array(upper, dtype=np.uint8)
        return cv2.inRange(hsv, lower, upper)

    def find_center_from_mask(self, mask):
        points = cv2.findNonZero(mask)
        if points is None:
            return None

        x, y, w, h = cv2.boundingRect(points)
        return x + w // 2

    def process_bar(self, screen, offset=(0, 0)):
        roi = self.crop_roi(screen, "bar_roi", offset)
        if roi.size == 0:
            self.release_all()
            return None

        detection = detect_bar_components(
            roi,
            self.config,
            self.last_bar_detection,
            make_debug=self.debug_var.get(),
        )
        if detection.green_center is not None and detection.yellow_center is not None:
            self.last_bar_detection = detection
        return detection

    def record_performance(self, capture_ms, detect_start):
        detect_ms = (time.perf_counter() - detect_start) * 1000 if detect_start else 0.0
        loop_ms = capture_ms + detect_ms + self.config.get("loop_delay", 0.0) * 1000
        self.perf_stats.add(capture_ms, detect_ms, loop_ms, self.capture_backend.last_backend)
        self.schedule_performance_update()

    def schedule_performance_update(self, force=False):
        now = time.time()
        if not force and now - self.last_perf_update < 0.3:
            return
        self.last_perf_update = now
        summary = self.perf_stats.summary_text()

        def update():
            if self.perf_label is not None and self.perf_label.winfo_exists():
                self.perf_label.configure(text=self.t("perf.prefix", summary=summary))
            if self.debug_var.get() and self.debug_metrics_label is not None:
                self.debug_metrics_label.configure(text=summary)

        try:
            self.root.after(0, update)
        except tk.TclError:
            pass

    def mark_detection_seen(self, now):
        self.no_detection_since = now

    def maybe_retry_no_detection(self, now):
        if not self.config.get("no_detection_retry_enabled", False):
            self.no_detection_since = now
            return False

        timeout = float(self.config.get("no_detection_retry_seconds", 12.0))
        if now - self.no_detection_since < timeout:
            return False

        self.release_all()
        pydirectinput.press("f")
        self.fishing_active = False
        self.no_detection_retry_count += 1
        self.no_detection_since = now
        self.queue_runtime_summary()
        self.set_status_key("status.no_detection_retry", "orange", force=True, seconds=timeout)
        return True

    def macro_loop(self):
        while self.running:
            try:
                capture_start = time.perf_counter()
                try:
                    screen, offset = self.capture_screen()
                except Exception as e:
                    self.release_all()
                    self.set_status_key("status.mss_failed", "red", force=True, error=e)
                    time.sleep(0.2)
                    continue
                capture_ms = (time.perf_counter() - capture_start) * 1000
                detect_start = time.perf_counter()
                now = time.time()

                bite_detected, bite_score = self.check_reference_image(
                    screen,
                    offset,
                    "bite_roi",
                    "bite",
                    "bite_match_threshold",
                )
                if bite_detected:
                    self.mark_detection_seen(now)
                if bite_detected and now - self.last_bite_time >= self.config["bite_cooldown"]:
                    self.release_all()
                    self.set_status_key("status.bite_detected", "orange", force=True, score=bite_score)
                    pydirectinput.press("f")
                    self.last_bite_time = now
                    self.fishing_active = True
                    time.sleep(0.3)

                success_score = 0.0
                if self.fishing_active:
                    success_detected, success_score = self.check_reference_image(
                        screen,
                        offset,
                        "success_roi",
                        "success",
                        "success_match_threshold",
                    )
                    if success_detected:
                        self.mark_detection_seen(now)
                    if (
                        success_detected
                        and now - self.last_success_time >= self.config["success_cooldown"]
                    ):
                        self.release_all()
                        self.set_status_key("status.success_detected", "cyan", force=True, score=success_score)
                        pydirectinput.press("esc")
                        time.sleep(0.3)
                        pydirectinput.press("f")
                        self.fishing_active = False
                        self.last_success_time = now
                        self.record_performance(capture_ms, detect_start)
                        time.sleep(self.config["success_cooldown"])
                        continue

                detection = self.process_bar(screen, offset)
                if detection is None:
                    self.release_all()
                    self.record_performance(capture_ms, detect_start)
                    self.maybe_retry_no_detection(now)
                    time.sleep(self.config["loop_delay"])
                    continue

                if detection.green_center is None or detection.yellow_center is None:
                    self.release_all()
                    self.record_performance(capture_ms, detect_start)
                    self.schedule_debug_update(detection)
                    self.maybe_retry_no_detection(now)
                    self.set_status_key("status.detect_failed", "orange", bite=bite_score, success=success_score)
                    time.sleep(self.config["loop_delay"])
                    continue

                self.mark_detection_seen(now)
                green_center = (
                    detection.predicted_green_center
                    if detection.predicted_green_center is not None
                    else detection.green_center
                )
                yellow_center = (
                    detection.predicted_yellow_center
                    if detection.predicted_yellow_center is not None
                    else detection.yellow_center
                )
                diff = yellow_center - green_center
                self.record_performance(capture_ms, detect_start)
                self.schedule_debug_update(detection, diff)
                deadzone = self.config["deadzone"]
                invert = self.config.get("invert_control", False)

                if abs(diff) <= deadzone:
                    self.release_all()
                    self.set_status_key(
                        "status.center_hold",
                        "blue",
                        success_state=self.t("state.on") if self.fishing_active else self.t("state.off"),
                    )
                else:
                    if diff < 0:
                        key = "d"
                    else:
                        key = "a"

                    if invert:
                        key = "a" if key == "d" else "d"

                    self.press_hold(key)
                    self.set_status_key(
                        "status.key_input",
                        "green",
                        key=key.upper(),
                        success_state=self.t("state.on") if self.fishing_active else self.t("state.off"),
                    )

                time.sleep(self.config["loop_delay"])
            except Exception as e:
                print("오류:", e)
                self.release_all()
                time.sleep(0.2)

        self.release_all()

    def toggle_macro(self):
        if self.running:
            self.stop_macro()
        else:
            self.start_macro()

    def start_macro(self):
        if self.running:
            return

        self.save_current_config(show_message=False)

        for roi_key, label_key in (
            ("bar_roi", "roi.bar"),
            ("bite_roi", "roi.bite"),
            ("success_roi", "roi.success"),
        ):
            if not is_valid_roi(self.config.get(roi_key)):
                messagebox.showwarning(
                    self.t("dialog.missing_area.title"),
                    self.t("dialog.missing_area.body", area=self.t(label_key)),
                    parent=self.root,
                )
                return

        if resolve_reference_image("bite") is None:
            messagebox.showwarning(self.t("dialog.missing_bite.title"), self.t("dialog.missing_bite.body"), parent=self.root)
            return

        if resolve_reference_image("success") is None:
            messagebox.showwarning(self.t("dialog.missing_success.title"), self.t("dialog.missing_success.body"), parent=self.root)
            return

        self.running = True
        self.fishing_active = False
        self.last_bar_detection = None
        self.no_detection_since = time.time()
        self.no_detection_retry_count = 0

        self.set_status_key("status.running_success_off", "green", force=True)
        self.queue_runtime_summary()
        self.btn_start.configure(text=self.t("button.stop"), fg_color="#D32F2F", hover_color="#A92727")

        self.thread = threading.Thread(target=self.macro_loop, daemon=True)
        self.thread.start()

    def stop_macro(self):
        self.running = False
        self.fishing_active = False
        self.release_all()
        self.set_status_key("status.stopped", "red", force=True)
        self.queue_runtime_summary()
        self.btn_start.configure(text=self.t("button.start"), fg_color="#2EAD5B", hover_color="#238947")

    def on_close(self):
        self.stop_macro()
        self.close_debug_window()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    pydirectinput.PAUSE = 0

    app = FishingMacroGUI()
    app.run()
