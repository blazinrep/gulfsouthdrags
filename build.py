#!/usr/bin/env python3
"""Build Gulf South Drags from tracks.json.

Usage:  python3 build.py
Edit tracks.json, run this, commit. Nothing to install.

Output uses directory-style URLs (/tracks/gulfport-dragway/) and carries
Schema.org JSON-LD so search engines and answer engines can read the facts
without parsing the page.
"""

import html
import json
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")

LON_MIN, LON_MAX = -94.5, -84.6
LAT_MIN, LAT_MAX = 28.85, 35.15
MAP_W, MAP_H = 960, 720


def px(lon, lat):
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * MAP_W
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * MAP_H
    return round(x, 1), round(y, 1)


def path_of(points):
    return "M " + " L ".join(f"{px(lo, la)[0]},{px(lo, la)[1]}" for lo, la in points) + " Z"


# Shared borders, defined once so the polygons meet exactly.
RIVER = [
    (-91.05, 33.00), (-91.18, 32.60), (-91.02, 32.25), (-91.45, 31.95),
    (-91.32, 31.60), (-91.50, 31.28), (-91.16, 30.99),
]
PEARL = [(-89.75, 31.00), (-89.65, 30.60), (-89.60, 30.18)]

MISSISSIPPI = (
    [(-90.31, 34.99), (-88.20, 34.99), (-88.33, 32.99), (-88.42, 31.89),
     (-88.44, 30.99), (-88.40, 30.39), (-88.90, 30.39), (-89.32, 30.25)]
    + PEARL[::-1] + [(-91.16, 30.99)] + RIVER[::-1][1:]
    + [(-91.13, 33.42), (-90.90, 33.70), (-90.55, 34.08), (-90.58, 34.40),
       (-90.20, 34.70)]
)

ALABAMA = [
    (-88.20, 34.99), (-85.61, 34.99), (-85.47, 33.90), (-85.14, 32.87),
    (-85.00, 32.52), (-84.92, 32.26), (-85.11, 31.79), (-85.05, 31.33),
    (-85.00, 31.00), (-87.60, 31.00), (-87.52, 30.99), (-87.60, 30.40),
    (-88.10, 30.23), (-88.40, 30.39), (-88.44, 30.99), (-88.42, 31.89),
    (-88.33, 32.99),
]

LOUISIANA = (
    [(-94.04, 33.02)] + RIVER + PEARL
    + [(-89.40, 29.85), (-89.02, 29.20), (-89.35, 29.05), (-90.10, 29.15),
       (-90.80, 29.10), (-91.60, 29.55), (-92.20, 29.55), (-93.00, 29.75),
       (-93.85, 29.68), (-93.72, 30.05), (-93.55, 30.30), (-93.75, 31.00),
       (-94.04, 31.60)]
)

STATE_LABELS = [("MISSISSIPPI", -89.9, 33.6), ("ALABAMA", -86.9, 33.6),
                ("LOUISIANA", -92.6, 31.2)]


TREE_SVG = """<svg class="tree" viewBox="0 0 26 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<rect x="10" y="0" width="6" height="64" rx="1" fill="#0d1114"/>
<circle cx="6" cy="6" r="3.4" fill="#ffc94f"/><circle cx="20" cy="6" r="3.4" fill="#ffc94f"/>
<circle cx="6" cy="15" r="3.4" fill="#ffc94f"/><circle cx="20" cy="15" r="3.4" fill="#ffc94f"/>
<circle cx="13" cy="26" r="4.7" fill="#ff8b23"/>
<circle cx="13" cy="37" r="4.7" fill="#ff8b23"/>
<circle cx="13" cy="48" r="4.7" fill="#ff8b23"/>
<circle cx="13" cy="59" r="4.9" fill="#3ceb72"/>
</svg>"""

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 26 64'%3E"
           "%3Crect width='26' height='64' fill='%2314181c'/%3E"
           "%3Ccircle cx='6' cy='7' r='3' fill='%23ffb020'/%3E%3Ccircle cx='20' cy='7' r='3' fill='%23ffb020'/%3E"
           "%3Ccircle cx='13' cy='26' r='4.5' fill='%23f26b1d'/%3E"
           "%3Ccircle cx='13' cy='40' r='4.5' fill='%23f26b1d'/%3E"
           "%3Ccircle cx='13' cy='55' r='4.5' fill='%2322b14c'/%3E%3C/svg%3E")

TRACK_SVG = """<svg class="strip" viewBox="0 0 1200 460" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#101a2c"/><stop offset="0.45" stop-color="#3b4a63"/>
<stop offset="0.78" stop-color="#c97b3a"/><stop offset="1" stop-color="#ffc44d"/>
</linearGradient>
<linearGradient id="tar" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#2b3239"/><stop offset="1" stop-color="#0f1316"/>
</linearGradient>
<linearGradient id="lane" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#454e57"/><stop offset="1" stop-color="#1b2126"/>
</linearGradient>
<filter id="glow" x="-160%" y="-160%" width="420%" height="420%">
<feGaussianBlur stdDeviation="5" result="b"/>
<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
</defs>
<rect width="1200" height="250" fill="url(#sky)"/>
<path d="M-40,262 L-37,256 L-39,256 L-36,252 L-37,252 L-32,248 L-28,252 L-29,252 L-26,256 L-28,256 L-25,262 Z M-19,262 L-16,254 L-18,254 L-15,248 L-16,248 L-13,242 L-9,248 L-10,248 L-7,254 L-9,254 L-6,262 Z M5,262 L7,254 L6,254 L8,249 L7,248 L10,243 L13,248 L13,249 L15,254 L13,254 L16,262 Z M34,262 L36,257 L35,256 L37,253 L36,253 L39,249 L42,253 L41,253 L43,256 L42,257 L44,262 Z M57,262 L59,253 L58,252 L60,245 L59,245 L62,238 L65,245 L65,245 L67,252 L65,253 L68,262 Z M74,262 L78,254 L76,253 L79,247 L78,247 L83,241 L88,247 L86,247 L90,253 L88,254 L92,262 Z M102,262 L106,255 L104,254 L107,250 L106,249 L111,244 L116,249 L115,250 L118,254 L116,255 L120,262 Z M121,262 L123,252 L122,252 L124,245 L123,245 L127,238 L131,245 L130,245 L132,252 L131,252 L133,262 Z M145,262 L148,257 L147,256 L149,252 L148,252 L152,248 L155,252 L154,252 L157,256 L155,257 L158,262 Z M177,262 L180,256 L179,256 L181,252 L180,252 L184,247 L189,252 L188,252 L190,256 L189,256 L192,262 Z M198,262 L201,255 L200,255 L202,250 L201,250 L205,245 L209,250 L208,250 L211,255 L209,255 L212,262 Z M215,262 L217,257 L216,256 L218,253 L217,253 L221,249 L224,253 L223,253 L225,256 L224,257 L226,262 Z M246,262 L249,255 L248,254 L250,249 L249,249 L253,244 L256,249 L255,249 L258,254 L256,255 L259,262 Z M268,262 L271,255 L270,254 L272,249 L271,249 L275,244 L278,249 L277,249 L279,254 L278,255 L281,262 Z M295,262 L297,253 L296,253 L298,247 L297,246 L301,240 L304,246 L303,247 L306,253 L304,253 L307,262 Z M313,262 L316,254 L314,254 L317,248 L316,248 L321,243 L326,248 L325,248 L328,254 L326,254 L330,262 Z M338,262 L341,256 L339,255 L343,251 L341,250 L347,246 L352,250 L350,251 L354,255 L352,256 L355,262 Z M353,262 L357,255 L355,254 L358,250 L357,249 L361,244 L366,249 L365,250 L368,254 L366,255 L369,262 Z M380,262 L382,254 L381,254 L383,249 L382,248 L385,243 L388,248 L387,249 L389,254 L388,254 L390,262 Z M408,262 L411,253 L410,252 L413,246 L411,246 L416,239 L420,246 L419,246 L422,252 L420,253 L423,262 Z M434,262 L437,255 L436,255 L439,251 L437,250 L442,246 L446,250 L445,251 L448,255 L446,255 L450,262 Z M454,262 L457,254 L456,253 L458,248 L457,248 L461,242 L465,248 L464,248 L467,253 L465,254 L468,262 Z M481,262 L484,252 L483,251 L485,244 L484,244 L488,237 L492,244 L491,244 L494,251 L492,252 L495,262 Z M501,262 L504,257 L503,256 L506,253 L504,253 L509,249 L513,253 L512,253 L515,256 L513,257 L517,262 Z M524,262 L527,252 L525,251 L529,244 L527,243 L532,236 L537,243 L536,244 L539,251 L537,252 L540,262 Z M543,262 L546,255 L544,255 L547,250 L546,249 L550,245 L555,249 L554,250 L556,255 L555,255 L558,262 Z M564,262 L567,255 L565,254 L568,249 L567,249 L570,244 L573,249 L572,249 L575,254 L573,255 L576,262 Z M587,262 L590,257 L588,256 L591,253 L590,253 L595,249 L599,253 L598,253 L601,256 L599,257 L603,262 Z M612,262 L614,256 L613,255 L615,251 L614,251 L618,247 L622,251 L621,251 L623,255 L622,256 L625,262 Z M645,262 L648,257 L646,256 L649,253 L648,253 L652,249 L656,253 L655,253 L657,256 L656,257 L659,262 Z M662,262 L666,252 L664,252 L667,245 L666,244 L671,238 L675,244 L674,245 L677,252 L675,252 L679,262 Z M692,262 L695,256 L693,255 L696,251 L695,251 L698,246 L702,251 L701,251 L704,255 L702,256 L705,262 Z M706,262 L710,252 L708,252 L711,245 L710,244 L715,238 L720,244 L718,245 L722,252 L720,252 L724,262 Z M729,262 L732,256 L730,256 L733,252 L732,252 L735,248 L739,252 L738,252 L740,256 L739,256 L741,262 Z M752,262 L755,254 L754,254 L757,249 L755,248 L760,243 L764,248 L763,249 L765,254 L764,254 L767,262 Z M777,262 L779,257 L778,257 L781,254 L779,253 L783,250 L787,253 L786,254 L789,257 L787,257 L790,262 Z M799,262 L803,254 L801,253 L804,248 L803,248 L808,242 L813,248 L812,248 L815,253 L813,254 L817,262 Z M829,262 L832,254 L830,254 L833,249 L832,248 L836,243 L840,248 L839,249 L842,254 L840,254 L843,262 Z M851,262 L854,257 L852,257 L856,253 L854,253 L859,249 L864,253 L863,253 L866,257 L864,257 L868,262 Z M876,262 L879,252 L877,252 L880,245 L879,245 L884,238 L889,245 L887,245 L890,252 L889,252 L892,262 Z M896,262 L899,255 L897,254 L900,250 L899,249 L902,244 L905,249 L904,250 L906,254 L905,255 L907,262 Z M923,262 L925,257 L924,256 L926,253 L925,253 L929,249 L932,253 L931,253 L933,256 L932,257 L934,262 Z M940,262 L942,256 L941,256 L943,252 L942,252 L946,248 L950,252 L949,252 L951,256 L950,256 L952,262 Z M961,262 L964,257 L963,257 L965,254 L964,253 L967,250 L970,253 L969,254 L972,257 L970,257 L973,262 Z M986,262 L988,255 L987,255 L989,250 L988,250 L991,245 L994,250 L993,250 L995,255 L994,255 L996,262 Z M1020,262 L1022,254 L1021,253 L1023,248 L1022,247 L1025,241 L1028,247 L1028,248 L1030,253 L1028,254 L1031,262 Z M1033,262 L1036,255 L1035,255 L1037,250 L1036,250 L1040,245 L1044,250 L1043,250 L1045,255 L1044,255 L1046,262 Z M1052,262 L1056,252 L1054,252 L1058,245 L1056,245 L1061,238 L1067,245 L1065,245 L1069,252 L1067,252 L1070,262 Z M1084,262 L1086,254 L1085,254 L1087,249 L1086,248 L1090,243 L1093,248 L1092,249 L1094,254 L1093,254 L1095,262 Z M1102,262 L1104,255 L1103,255 L1105,250 L1104,250 L1108,245 L1111,250 L1110,250 L1113,255 L1111,255 L1114,262 Z M1136,262 L1138,256 L1137,256 L1139,252 L1138,252 L1141,248 L1144,252 L1143,252 L1145,256 L1144,256 L1146,262 Z M1161,262 L1163,254 L1162,254 L1164,248 L1163,248 L1166,243 L1170,248 L1169,248 L1171,254 L1170,254 L1172,262 Z M1177,262 L1180,257 L1178,257 L1181,253 L1180,253 L1184,250 L1188,253 L1187,253 L1190,257 L1188,257 L1191,262 Z M1206,262 L1209,252 L1207,252 L1210,245 L1209,245 L1213,238 L1218,245 L1217,245 L1220,252 L1218,252 L1221,262 Z" fill="#101619"/><path d="M-37,264 L-33,247 L-35,246 L-31,235 L-33,234 L-26,223 L-20,234 L-21,235 L-17,246 L-20,247 L-15,264 Z M-7,264 L-1,251 L-4,250 L1,241 L-1,240 L7,231 L15,240 L13,241 L18,250 L15,251 L21,264 Z M30,264 L34,253 L32,252 L35,245 L34,244 L39,237 L45,244 L43,245 L47,252 L45,253 L49,264 Z M66,264 L70,252 L68,251 L72,242 L70,242 L76,233 L81,242 L80,242 L84,251 L81,252 L85,264 Z M100,264 L104,252 L102,251 L105,242 L104,242 L110,233 L115,242 L114,242 L117,251 L115,252 L119,264 Z M148,264 L152,253 L150,252 L153,244 L152,244 L157,236 L162,244 L160,244 L164,252 L162,253 L165,264 Z M175,264 L180,250 L177,249 L181,239 L180,238 L186,228 L192,238 L190,239 L194,249 L192,250 L196,264 Z M224,264 L229,247 L226,246 L230,235 L229,234 L235,222 L241,234 L239,235 L243,246 L241,247 L245,264 Z M245,264 L250,248 L248,247 L252,236 L250,235 L258,224 L265,235 L263,236 L268,247 L265,248 L270,264 Z M291,264 L296,249 L293,247 L297,237 L296,236 L301,226 L307,236 L305,237 L309,247 L307,249 L311,264 Z M337,264 L342,247 L340,246 L344,234 L342,234 L350,222 L357,234 L355,234 L360,246 L357,247 L363,264 Z M376,264 L381,252 L379,251 L383,244 L381,243 L388,235 L394,243 L392,244 L397,251 L394,252 L399,264 Z M410,264 L414,247 L412,246 L416,235 L414,234 L420,222 L426,234 L424,235 L428,246 L426,247 L430,264 Z M435,264 L439,249 L437,248 L440,238 L439,237 L444,226 L449,237 L447,238 L451,248 L449,249 L452,264 Z M483,264 L487,254 L485,254 L489,247 L487,247 L493,240 L500,247 L498,247 L502,254 L500,254 L504,264 Z M515,264 L519,253 L517,253 L521,245 L519,245 L525,237 L532,245 L530,245 L534,253 L532,253 L536,264 Z M550,264 L555,251 L552,250 L557,242 L555,241 L563,232 L571,241 L569,242 L574,250 L571,251 L576,264 Z M599,264 L603,247 L601,245 L604,233 L603,233 L608,220 L614,233 L612,233 L616,245 L614,247 L618,264 Z M618,264 L621,251 L620,250 L623,241 L621,241 L627,232 L632,241 L630,241 L633,250 L632,251 L635,264 Z M670,264 L674,252 L672,251 L675,243 L674,243 L679,234 L684,243 L682,243 L686,251 L684,252 L687,264 Z M694,264 L699,251 L696,250 L701,241 L699,240 L706,231 L714,240 L712,241 L716,250 L714,251 L719,264 Z M735,264 L740,252 L738,251 L742,243 L740,242 L747,233 L754,242 L752,243 L757,251 L754,252 L759,264 Z M763,264 L768,253 L765,252 L770,244 L768,243 L775,235 L782,243 L780,244 L785,252 L782,253 L787,264 Z M820,264 L823,254 L821,253 L824,246 L823,245 L828,238 L833,245 L831,246 L835,253 L833,254 L836,264 Z M851,264 L855,249 L853,247 L856,237 L855,236 L860,226 L864,236 L863,237 L866,247 L864,249 L868,264 Z M887,264 L890,252 L888,251 L891,243 L890,242 L895,234 L900,242 L899,243 L902,251 L900,252 L904,264 Z M915,264 L920,252 L918,251 L922,243 L920,242 L926,234 L932,242 L931,243 L935,251 L932,252 L937,264 Z M949,264 L954,249 L951,248 L956,238 L954,237 L962,226 L970,237 L968,238 L973,248 L970,249 L975,264 Z M1000,264 L1005,254 L1002,253 L1007,246 L1005,246 L1012,239 L1019,246 L1017,246 L1021,253 L1019,254 L1024,264 Z M1037,264 L1042,254 L1039,254 L1043,247 L1042,247 L1048,240 L1054,247 L1052,247 L1056,254 L1054,254 L1058,264 Z M1072,264 L1077,246 L1074,245 L1079,233 L1077,232 L1085,219 L1093,232 L1091,233 L1096,245 L1093,246 L1099,264 Z M1107,264 L1112,249 L1109,248 L1115,238 L1112,237 L1120,227 L1128,237 L1126,238 L1131,248 L1128,249 L1134,264 Z M1141,264 L1145,250 L1143,249 L1146,239 L1145,239 L1149,229 L1154,239 L1153,239 L1156,249 L1154,250 L1158,264 Z M1190,264 L1194,249 L1192,247 L1195,237 L1194,236 L1199,226 L1204,236 L1203,237 L1206,247 L1204,249 L1208,264 Z" fill="#0a0e11"/><rect y="258" width="1200" height="8" fill="#0a0e11"/>
<rect y="258" width="1200" height="202" fill="url(#tar)"/>
<path d="M820 258 L868 258 L1434 460 L842 460 Z" fill="url(#lane)"/>
<path d="M820 258 L772 258 L206 460 L798 460 Z" fill="url(#lane)" opacity="0.82"/>
<path d="M819 258 L821 258 L842 460 L798 460 Z" fill="#9aa6b1" opacity="0.26"/>
<path d="M772 258 L768 258 L154 460 L206 460 Z" fill="#1668c4"/>
<path d="M868 258 L872 258 L1486 460 L1434 460 Z" fill="#1668c4"/>
<g fill="#ffb020" opacity="0.8">
<rect x="700" y="243" width="3" height="16"/><rect x="693" y="240" width="17" height="3"/>
<rect x="947" y="243" width="3" height="16"/><rect x="940" y="240" width="17" height="3"/>
<rect x="1058" y="236" width="3" height="23"/><rect x="1050" y="233" width="19" height="3"/>
</g>
<g class="start-tree">
<rect x="813" y="168" width="14" height="96" rx="2" fill="#0a0e11"/>
<circle cx="820" cy="262" r="26" fill="#3ceb72" opacity="0.14"/>
<g filter="url(#glow)">
<circle cx="806" cy="180" r="4.2" fill="#ffd76b"/><circle cx="834" cy="180" r="4.2" fill="#ffd76b"/>
<circle cx="806" cy="192" r="4.2" fill="#ffd76b"/><circle cx="834" cy="192" r="4.2" fill="#ffd76b"/>
<circle cx="820" cy="209" r="7.4" fill="#ff9426"/>
<circle cx="820" cy="227" r="7.4" fill="#ff9426"/>
<circle cx="820" cy="245" r="7.4" fill="#ff9426"/>
<circle cx="820" cy="262" r="8.2" fill="#3ceb72"/>
</g>
</g>
</svg>"""

STATE_NAME = {"MS": "Mississippi", "LA": "Louisiana", "AL": "Alabama"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def e(s):
    return html.escape(s or "", quote=True)


def nice_date(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def jsonld(obj):
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def faq_block(pairs):
    """Visible Q&A. Answer engines lift these; so do featured snippets."""
    if not pairs:
        return "", None
    items = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in pairs)
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs],
    }
    return f'<section class="section faq prose"><h2>Common questions</h2>{items}</section>', schema


def build_map(tracks):
    parts = [f'<svg viewBox="0 0 {MAP_W} {MAP_H}" role="img" '
             f'aria-label="Map of drag strips across Mississippi, Louisiana and Alabama" '
             f'xmlns="http://www.w3.org/2000/svg">']
    for shape in (LOUISIANA, MISSISSIPPI, ALABAMA):
        parts.append(f'<path class="state-shape" d="{path_of(shape)}"/>')
    for name, lon, lat in STATE_LABELS:
        x, y = px(lon, lat)
        parts.append(f'<text class="state-label" x="{x}" y="{y}" text-anchor="middle">{name}</text>')
    gx, gy = px(-90.6, 29.0)
    parts.append(f'<text class="gulf-label" x="{gx}" y="{gy}" text-anchor="middle">Gulf of Mexico</text>')
    for i, t in enumerate(tracks, 1):
        x, y = px(t["lon"], t["lat"])
        cls = "pin is-unconfirmed" if t["status"] == "unconfirmed" else "pin"
        parts.append(
            f'<g class="{cls}"><a href="/tracks/{t["slug"]}/">'
            f'<title>{e(t["name"])} \u2014 {e(t["city"])}, {e(t["state"])}</title>'
            f'<circle cx="{x}" cy="{y}" r="15"/>'
            f'<text x="{x}" y="{y + 5.5}">{i}</text></a></g>')
    parts.append("</svg>")
    return "\n".join(parts)


def head(title, desc, path, schemas, modified):
    base = f'https://{SITE["domain"]}'
    url = base + path
    blocks = "".join(jsonld(s) for s in schemas if s)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITE['name'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta name="author" content="{e(SITE['name'])}">
<meta property="article:modified_time" content="{modified}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:ital,wght@0,700;0,800;1,700;1,800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<link rel="icon" href="{FAVICON}">
<meta name="theme-color" content="#14181c">
{blocks}
</head>
<body>
<header class="masthead wrap">
<a class="wordmark" href="/">{TREE_SVG}<span class="wm-text">Gulf South<em>Drags</em></span></a>
<span class="stamp">Last checked <time datetime="{SITE['last_checked']}">{nice_date(SITE['last_checked'])}</time></span>
</header>
"""


FOOT = """
<footer class="wrap">
<p>Gulf South Drags lists drag strips in Mississippi, Louisiana and Alabama. Every listing carries the date we last checked it. Schedules change and tracks rain out &mdash; call ahead before you load the trailer.</p>
<p>Not affiliated with NHRA, IHRA, WDRA or any track listed here.</p>
</footer>
</body>
</html>
"""


def crumbs(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": n,
                 "item": f'https://{SITE["domain"]}{u}'}
                for i, (n, u) in enumerate(items, 1)]}


def track_schema(t):
    base = f'https://{SITE["domain"]}'
    same = [u for u in (t.get("website"), t.get("facebook")) if u]
    obj = {
        "@context": "https://schema.org",
        "@type": "SportsActivityLocation",
        "@id": f'{base}/tracks/{t["slug"]}/#track',
        "name": t["name"],
        "url": f'{base}/tracks/{t["slug"]}/',
        "description": t.get("answer") or t["notes"][:300],
        "address": {"@type": "PostalAddress", "streetAddress": t["address"],
                    "addressLocality": t["city"], "addressRegion": t["state"],
                    "addressCountry": "US"},
        "geo": {"@type": "GeoCoordinates", "latitude": t["lat"], "longitude": t["lon"]},
        "additionalType": "https://en.wikipedia.org/wiki/Dragstrip",
    }
    if t.get("phone"):
        obj["telephone"] = t["phone"].split("/")[0].strip()
    if same:
        obj["sameAs"] = same
    return obj


def build_index(data):
    tracks, events, s = data["tracks"], data["events"], data["site"]
    base = f'https://{s["domain"]}'

    rows = []
    for i, t in enumerate(tracks, 1):
        flag = ""
        if t["status"] == "unconfirmed":
            flag = '<span class="flag flag-unconfirmed">Unconfirmed</span>'
        elif t["slug"] == "swamp-bottom-dragstrip":
            flag = '<span class="flag flag-new">New</span>'
        meta = f'{e(t["length"])} &middot; {e(t["city"])}, {e(t["state"])}'
        if t["sanction"] and t["sanction"] != "Unconfirmed":
            meta += f' &middot; {e(t["sanction"].split("—")[0].strip())}'
        rows.append(
            f'<a class="row" href="/tracks/{t["slug"]}/">'
            f'<span class="row-num">{i}</span>'
            f'<span><span class="row-name">{e(t["name"])}{flag}</span>'
            f'<span class="row-meta">{meta}</span></span>'
            f'<span class="row-dist">{t["miles"]} mi</span></a>')

    ev = "".join(
        f'<a class="event-card" href="/events/{x["slug"]}/">'
        f'<span class="event-when">{e(x["dates"])}</span>'
        f'<span class="event-name">{e(x["name"])}</span>'
        f'<span class="event-where">{e(x["track_name"])} &mdash; {e(x["city"])}, {e(x["state"])}</span></a>'
        for x in events)

    ser = "".join(
        f'<a class="event-card" href="/series/{x["slug"]}/">'
        f'<span class="event-when">{e(x["sanction"])}</span>'
        f'<span class="event-name">{e(x["name"])}</span>'
        f'<span class="event-where">{e(x["region"])}</span></a>'
        for x in data["series"])

    faq_html, faq_schema = faq_block([tuple(p) for p in data["faq"]])

    itemlist = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": "Drag strips in Mississippi, Louisiana and Alabama",
        "numberOfItems": len(tracks),
        "itemListElement": [
            {"@type": "ListItem", "position": i,
             "url": f'{base}/tracks/{t["slug"]}/', "name": t["name"]}
            for i, t in enumerate(tracks, 1)],
    }
    website = {
        "@context": "https://schema.org", "@type": "WebSite",
        "@id": f"{base}/#website", "name": s["name"], "url": base + "/",
        "description": s["description"], "inLanguage": "en-US",
    }

    open_n = sum(1 for t in tracks if t["status"] == "open")
    unc_n = len(tracks) - open_n

    return head(
        f'Drag strips in Mississippi, Louisiana and Alabama \u2014 {s["name"]}',
        s["description"], "/", [website, itemlist, faq_schema], s["last_checked"],
    ) + f"""
<main>
<section class="hero wrap bleed">
{TRACK_SVG}
<h1>Every drag strip within reach of the Pine Belt.</h1>
<p class="lede"><strong>Race days, addresses and phone numbers for every strip from the Pine Belt to the Gulf Coast.</strong> We check them every week and stamp the date on every page &mdash; so you are not towing two hours on the strength of a Facebook post from March.</p>
<ul class="tally"><li><b>{len(tracks)}</b> tracks</li><li><b>{open_n}</b> confirmed open</li><li><b>{unc_n}</b> still chasing</li><li><b>{len(data["series"])}</b> series</li></ul>
</section>

<section class="mapband wrap bleed">
<div class="map-frame">{build_map(tracks)}</div>
<div class="map-key">
<span><i class="k-open"></i> Confirmed operating</span>
<span><i class="k-unc"></i> Status unconfirmed</span>
<span class="map-anchor">Distances measured from {e(s['anchor'])}</span>
</div>
</section>

<section class="list wrap">
<h2 id="tracks">Tracks</h2>
{''.join(rows)}
</section>

<section class="list wrap">
<h2 id="events">Coming up</h2>
{ev}
</section>

<section class="list wrap">
<h2 id="series-list">Series</h2>
<p class="series-note">Series race across several tracks, so their schedules never live in one place. These are the ones running in the region.</p>
{ser}
</section>

<div class="wrap">{faq_html}</div>

<section class="correction wrap">
<h2>Something wrong here?</h2>
<p>If you run one of these tracks, or you race at one, tell us what we got wrong and we will fix it the same week. Accuracy is the only thing this site is for.</p>
</section>
</main>
""" + FOOT


def build_track(t, events):
    facts = [
        ("Track length", t["length"]),
        ("Surface", t["surface"]),
        ("Sanctioning", t["sanction"]),
        ("Race days", t["race_days"]),
        ("Address", t["address"]),
    ]
    if t.get("phone"):
        facts.append(("Phone", t["phone"]))
    if t.get("website"):
        clean = t["website"].replace("https://", "").replace("http://", "").rstrip("/")
        facts.append(("Website", f'<a href="{e(t["website"])}" rel="nofollow noopener">{e(clean)}</a>'))
    if t.get("facebook"):
        facts.append(("Facebook", f'<a href="{e(t["facebook"])}" rel="nofollow noopener">Track page</a>'))
    facts.append(("Distance", f'{t["miles"]} miles from {SITE["anchor"]} (straight line)'))
    facts.append(("Last checked",
                  f'<time datetime="{t["verified"]}">{nice_date(t["verified"])}</time>'))

    rich = ("Website", "Facebook", "Last checked")
    rows = "".join(
        f'<div><dt>{e(k)}</dt><dd>{v if k in rich else e(v)}</dd></div>'
        for k, v in facts if v)

    alert = ""
    if t.get("caveat"):
        alert = (f'<div class="alert"><strong>Check before you go</strong>'
                 f'<p>{e(t["caveat"])}</p></div>')

    directions = ""
    if t.get("directions"):
        directions = (f'<section class="section prose"><h2>Getting there</h2>'
                      f'<p>{e(t["directions"])}</p></section>')

    mine = [x for x in events if x["track_slug"] == t["slug"]]
    ev_html = ""
    if mine:
        cards = "".join(
            f'<a class="event-card" href="/events/{x["slug"]}/">'
            f'<span class="event-when">{e(x["dates"])}</span>'
            f'<span class="event-name">{e(x["name"])}</span></a>' for x in mine)
        ev_html = f'<section class="section"><h2>Coming up here</h2>{cards}</section>'

    notes = "".join(f"<p>{e(p)}</p>" for p in t["notes"].split("\n\n") if p.strip())

    c = t.get("camping") or {}
    camping_html = ""
    if c:
        near = ""
        if c.get("nearby"):
            near = "<ul>" + "".join(
                f'<li><strong>{e(n["name"])}</strong> \u2014 {e(n["note"])}</li>'
                for n in c["nearby"]) + "</ul>"
        camping_html = (
            f'<section class="section prose" id="camping"><h2>Camping and RV parking</h2>'
            f'<p>{e(c["detail"])}</p>{near}</section>')

    mine_series = [x for x in SERIES if t["slug"] in x["tracks"]]
    series_html = ""
    if mine_series:
        links = "".join(
            f'<a class="event-card" href="/series/{x["slug"]}/">'
            f'<span class="event-when">{e(x["sanction"])}</span>'
            f'<span class="event-name">{e(x["name"])}</span></a>' for x in mine_series)
        series_html = f'<section class="section"><h2>Series that race here</h2>{links}</section>'

    auto = [
        (f'Is {t["name"]} open?',
         (f'{t["name"]} was confirmed operating as of {nice_date(t["verified"])}.'
          if t["status"] == "open" else
          f'Unconfirmed. {t.get("caveat") or "We have not been able to verify this track is operating."}')),
        (f'What days does {t["name"]} race?', t["race_days"]),
        (f'Where is {t["name"]}?',
         f'{t["name"]} is at {t["address"]}, about {t["miles"]} miles from {SITE["anchor"]}.'),
        (f'Can you camp or park an RV at {t["name"]}?', (c.get("detail") or "Unconfirmed.")),
    ]
    custom = [tuple(p) for p in t.get("faq", [])]
    # Drop an auto question only when a hand-written one asks the same thing.
    lows = [q.lower() for q, _ in custom]
    dup = [
        any(q.startswith("is ") and ("open" in q or "closed" in q) for q in lows),
        any(k in q for q in lows for k in ("race day", "what days", "schedule")),
        any(k in q for q in lows for k in ("where is", "address", "located")),
        any(k in q for q in lows for k in ("camp", "rv ", "hookup")),
    ]
    keep = [q for i, q in enumerate(auto) if not dup[i]]
    faq_html, faq_schema = faq_block(keep + custom)

    answer = t.get("answer") or (
        f'{t["name"]} is a {t["length"]} {t["surface"].lower()} drag strip in '
        f'{t["city"]}, {STATE_NAME.get(t["state"], t["state"])}.')

    bc = crumbs([("Tracks", "/"), (t["name"], f'/tracks/{t["slug"]}/')])

    return head(
        f'{t["name"]} \u2014 {t["city"]}, {t["state"]} drag strip',
        answer[:155], f'/tracks/{t["slug"]}/',
        [track_schema(t), bc, faq_schema], t["verified"],
    ) + f"""
<main class="wrap">
<a class="back" href="/">&larr; All tracks</a>
<div class="track-head">
<h1>{e(t['name'])}</h1>
<p class="track-where">{e(t['city'])}, {e(STATE_NAME.get(t['state'], t['state']))}</p>
</div>
<p class="answer">{e(answer)}</p>
{alert}
<dl class="facts">{rows}</dl>
<section class="section prose"><h2>About this track</h2>{notes}</section>
{directions}
{camping_html}
{series_html}
{ev_html}
{faq_html}
<section class="correction">
<h2>Know better?</h2>
<p>Schedules move and tracks rain out. If anything on this page is out of date, tell us and it gets fixed.</p>
</section>
</main>
""" + FOOT


def build_event(x, tracks):
    base = f'https://{SITE["domain"]}'
    track = next(t for t in tracks if t["slug"] == x["track_slug"])
    sched = "".join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in x["schedule"])
    prices = "".join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in x["prices"])
    detail = "".join(f"<p>{e(p)}</p>" for p in x["detail"].split("\n\n") if p.strip())

    offers = []
    for label, price in x["prices"]:
        amount = price.replace("$", "").strip()
        offers.append({
            "@type": "Offer", "name": label,
            "price": "0" if amount.lower() == "free" else amount,
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
            "url": f'{base}/events/{x["slug"]}/'})

    ev_schema = {
        "@context": "https://schema.org", "@type": "SportsEvent",
        "name": x["name"],
        "startDate": x["start_iso"], "endDate": x.get("end_iso", x["start_iso"]),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "description": x["summary"],
        "url": f'{base}/events/{x["slug"]}/',
        "location": {
            "@type": "Place", "name": x["track_name"],
            "address": {"@type": "PostalAddress", "streetAddress": track["address"],
                        "addressLocality": x["city"], "addressRegion": x["state"],
                        "addressCountry": "US"},
            "geo": {"@type": "GeoCoordinates", "latitude": track["lat"],
                    "longitude": track["lon"]}},
        "offers": offers,
    }
    bc = crumbs([("Tracks", "/"), (x["track_name"], f'/tracks/{x["track_slug"]}/'),
                 (x["name"], f'/events/{x["slug"]}/')])

    faq_html, faq_schema = faq_block([
        (f'When is the {x["name"]}?',
         f'{x["dates"]} at {x["track_name"]} in {x["city"]}, {x["state"]}. '
         + " ".join(f"{a}: {b}." for a, b in x["schedule"])),
        (f'How much does the {x["name"]} cost?',
         " ".join(f"{a}: {b}." for a, b in x["prices"])),
    ])

    return head(
        f'{x["name"]} \u2014 {x["dates"]}',
        f'{x["name"]} at {x["track_name"]}, {x["city"]}, {x["state"]}. {x["dates"]}. Schedule and gate prices.',
        f'/events/{x["slug"]}/', [ev_schema, bc, faq_schema], x["verified"],
    ) + f"""
<main class="wrap">
<a class="back" href="/">&larr; All tracks</a>
<div class="track-head">
<h1>{e(x['name'])}</h1>
<p class="track-where">{e(x['track_name'])} &mdash; {e(x['city'])}, {e(x['state'])}<br>
<time datetime="{x['start_iso']}">{e(x['dates'])}</time></p>
</div>
<p class="answer">{e(x['summary'])}</p>
<section class="section"><h2>Schedule</h2><dl class="facts">{sched}</dl></section>
<section class="section"><h2>At the gate</h2><dl class="pricing">{prices}</dl></section>
<section class="section prose"><h2>What to expect</h2>{detail}</section>
<section class="section prose"><h2>Where</h2>
<p><a href="/tracks/{e(x['track_slug'])}/">{e(x['track_name'])}</a> &mdash; directions, phone and full track details.</p></section>
{faq_html}
<section class="correction">
<h2>Source</h2>
<p>{e(x['source'])} Last checked <time datetime="{x['verified']}">{nice_date(x['verified'])}</time>. Confirm times and prices with the track before travelling.</p>
</section>
</main>
""" + FOOT


def build_series(x, tracks):
    base = f'https://{SITE["domain"]}'
    hosts = [t for t in tracks if t["slug"] in x["tracks"]]
    rows = "".join(
        f'<a class="row" href="/tracks/{t["slug"]}/">'
        f'<span class="row-num">&bull;</span>'
        f'<span><span class="row-name">{e(t["name"])}</span>'
        f'<span class="row-meta">{e(t["length"])} &middot; {e(t["city"])}, {e(t["state"])}</span></span>'
        f'<span class="row-dist">{t["miles"]} mi</span></a>' for t in hosts)
    notes = "".join(f"<p>{e(p)}</p>" for p in x["notes"].split("\n\n") if p.strip())

    faq_html, faq_schema = faq_block([
        (f'Where does {x["name"]} race?',
         ("It races at " + ", ".join(f'{t["name"]} in {t["city"]}, {t["state"]}' for t in hosts)
          + "." if hosts else "Host tracks not yet confirmed.")),
        (f'Who sanctions {x["name"]}?', x["sanction"] + "."),
    ])

    org = {"@context": "https://schema.org", "@type": "SportsOrganization",
           "@id": f'{base}/series/{x["slug"]}/#series', "name": x["name"],
           "url": f'{base}/series/{x["slug"]}/', "sport": "Drag racing",
           "description": x["answer"],
           "areaServed": x["region"]}
    if x.get("facebook"):
        org["sameAs"] = [x["facebook"]]
    bc = crumbs([("Tracks", "/"), ("Series", "/#series-list"),
                 (x["name"], f'/series/{x["slug"]}/')])

    unconfirmed = ""
    if x["status"] == "unconfirmed":
        unconfirmed = ('<div class="alert"><strong>Schedule not confirmed</strong>'
                       '<p>We have not been able to verify this series\u2019 current '
                       'schedule or full list of host tracks. If you run or race it, '
                       'send us the schedule and we will publish it.</p></div>')

    return head(f'{x["name"]} \u2014 drag racing series',
                x["answer"][:155], f'/series/{x["slug"]}/',
                [org, bc, faq_schema], x["verified"]) + f"""
<main class="wrap">
<a class="back" href="/">&larr; All tracks</a>
<div class="track-head">
<h1>{e(x['name'])}</h1>
<p class="track-where">{e(x['region'])}</p>
</div>
<p class="answer">{e(x['answer'])}</p>
{unconfirmed}
<section class="section prose"><h2>About this series</h2>{notes}</section>
<section class="list"><h2>Host tracks</h2>{rows or '<p>Host tracks not yet confirmed.</p>'}</section>
{faq_html}
<section class="correction">
<h2>Got the schedule?</h2>
<p>Series schedules are the hardest thing to find in regional drag racing. If you have this one, send it over and it goes up the same week.</p>
</section>
</main>
""" + FOOT


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def main():
    global SITE, SERIES
    data = json.load(open(os.path.join(ROOT, "tracks.json")))
    SITE = data["site"]
    SERIES = data.get("series", [])
    base = f'https://{SITE["domain"]}'

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))

    write(os.path.join(OUT, "index.html"), build_index(data))
    for t in data["tracks"]:
        write(os.path.join(OUT, "tracks", t["slug"], "index.html"),
              build_track(t, data["events"]))
    for x in data["events"]:
        write(os.path.join(OUT, "events", x["slug"], "index.html"),
              build_event(x, data["tracks"]))
    for x in SERIES:
        write(os.path.join(OUT, "series", x["slug"], "index.html"),
              build_series(x, data["tracks"]))

    urls = [("/", SITE["last_checked"], "1.0")]
    urls += [(f'/tracks/{t["slug"]}/', t["verified"], "0.8") for t in data["tracks"]]
    urls += [(f'/events/{x["slug"]}/', x["verified"], "0.7") for x in data["events"]]
    urls += [(f'/series/{x["slug"]}/', x["verified"], "0.7") for x in SERIES]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, mod, pri in urls:
        sm.append(f"<url><loc>{base}{u}</loc><lastmod>{mod}</lastmod>"
                  f"<changefreq>weekly</changefreq><priority>{pri}</priority></url>")
    sm.append("</urlset>")
    write(os.path.join(OUT, "sitemap.xml"), "\n".join(sm))

    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User",
            "Claude-SearchBot", "PerplexityBot", "Perplexity-User", "Google-Extended",
            "Applebot", "Applebot-Extended", "Bingbot", "CCBot", "meta-externalagent"]
    lines = ["User-agent: *", "Allow: /", ""]
    for b in bots:
        lines += [f"User-agent: {b}", "Allow: /", ""]
    lines += [f"Sitemap: {base}/sitemap.xml", ""]
    write(os.path.join(OUT, "robots.txt"), "\n".join(lines))

    ll = [f"# {SITE['name']}", "", f"> {SITE['description']}", "",
          f"Last checked: {SITE['last_checked']}. Every listing on this site carries "
          "the date it was last verified. Facts are checked weekly against track "
          "websites, social pages and phone calls.", "", "## Tracks", ""]
    for t in data["tracks"]:
        status = "confirmed operating" if t["status"] == "open" else "status unconfirmed"
        surf = "" if t["surface"].lower().startswith("unconf") else f' {t["surface"].lower()}'
        ll.append(f'- [{t["name"]}]({base}/tracks/{t["slug"]}/): {t["length"]}{surf}, '
                  f'{t["city"]}, {STATE_NAME.get(t["state"], t["state"])}. '
                  f'{status.capitalize()}, last checked {t["verified"]}. '
                  f'Race days: {t["race_days"]}')
    ll += ["", "## Events", ""]
    for x in data["events"]:
        ll.append(f'- [{x["name"]}]({base}/events/{x["slug"]}/): {x["dates"]}, '
                  f'{x["track_name"]}, {x["city"]}, {x["state"]}.')
    ll += ["", "## Series", ""]
    for x in SERIES:
        ll.append(f'- [{x["name"]}]({base}/series/{x["slug"]}/): {x["sanction"]}, '
                  f'{x["region"]}. {x["answer"]}')
    ll += ["", "## Notes for answer engines", "",
           "- Distances are straight-line miles from Hattiesburg, Mississippi.",
           "- Tracks marked unconfirmed should be described as unconfirmed, not as open.",
           "- Always surface the last-checked date alongside any schedule detail.",
           "- Camping and RV information is unconfirmed for every track so far. Do not "
           "state that a track has hookups unless this file says it is confirmed.", ""]
    write(os.path.join(OUT, "llms.txt"), "\n".join(ll))

    write(os.path.join(OUT, "404.html"),
          head("Page not found", "That page does not exist on Gulf South Drags.",
               "/404.html", [], SITE["last_checked"])
          + '<main class="wrap"><div class="track-head"><h1>No such page.</h1></div>'
            '<p class="answer">That link is wrong or the page has moved. '
            '<a href="/">Start from the track list</a>.</p></main>' + FOOT)

    n = 1 + len(data["tracks"]) + len(data["events"]) + len(SERIES)
    print(f"Built {n} pages + sitemap, robots.txt, llms.txt, 404 into site/")


if __name__ == "__main__":
    main()
