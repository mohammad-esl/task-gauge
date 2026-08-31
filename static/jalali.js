// Pure-JS Gregorian <-> Jalali (Shamsi/Persian) calendar conversion.
// No dependency: storage and backend stay Gregorian ("YYYY-MM-DD"); this is
// display-only, used to render/pick dates in Jalali across the UI.
// Core algorithm ported verbatim from jalaali-js (MIT License),
// https://github.com/jalaali/jalaali-js — Behrang Noruzi Niya / Roozbeh Pournader.

function div(a, b) { return ~~(a / b); }
function mod(a, b) { return a - ~~(a / b) * b; }

const J_BREAKS = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178
];

function jalCal(jy) {
    const bl = J_BREAKS.length;
    const gy = jy + 621;
    let leapJ = -14;
    let jp = J_BREAKS[0];
    if (jy < jp || jy >= J_BREAKS[bl - 1]) throw new Error('Invalid Jalaali year ' + jy);
    let jump = 0;
    for (let i = 1; i < bl; i += 1) {
        const jm = J_BREAKS[i];
        jump = jm - jp;
        if (jy < jm) break;
        leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
        jp = jm;
    }
    let n = jy - jp;
    leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
    if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
    const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
    const march = 20 + leapJ - leapG;
    if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
    let leap = mod(mod(n + 1, 33) - 1, 4);
    if (leap === -1) leap = 4;
    return { leap, gy, march };
}

function g2d(gy, gm, gd) {
    let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
        + div(153 * mod(gm + 9, 12) + 2, 5)
        + gd - 34840408;
    d = d - div(div(gy + div(gm - 8, 6) + 100100, 100) * 3, 4) + 752;
    return d;
}

function d2g(jdn) {
    let j = 4 * jdn + 139361631;
    j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    const i = div(mod(j, 1461), 4) * 5 + 308;
    const gd = div(mod(i, 153), 5) + 1;
    const gm = mod(div(i, 153), 12) + 1;
    const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
    return [gy, gm, gd];
}

function jalCalJd(jy, jm, jd) {
    const r = jalCal(jy);
    return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

function jdToJalaali(jdn) {
    const gy = d2g(jdn)[0];
    let jy = gy - 621;
    const r = jalCal(jy);
    const jdn1f = g2d(gy, 3, r.march);
    let k = jdn - jdn1f;
    if (k >= 0) {
        if (k <= 185) {
            const jm = 1 + div(k, 31);
            const jd = mod(k, 31) + 1;
            return [jy, jm, jd];
        }
        k -= 186;
    } else {
        jy -= 1;
        k += 179;
        if (r.leap) k += 1;
    }
    const jm = 7 + div(k, 30);
    const jd = mod(k, 30) + 1;
    return [jy, jm, jd];
}

function toJalali(gy, gm, gd) {
    return jdToJalaali(g2d(gy, gm, gd));
}

function toGregorian(jy, jm, jd) {
    return d2g(jalCalJd(jy, jm, jd));
}

function isLeapJalaaliYear(jy) {
    return jalCal(jy).leap === 0;
}

const JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
];

const JALALI_WEEKDAYS_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"]; // Sat..Fri

function pad2(n) { return String(n).padStart(2, '0'); }

// "YYYY-MM-DD" (Gregorian) -> "YYYY/MM/DD" (Jalali)
function gregorianStrToJalaliStr(gStr) {
    if (!gStr) return '';
    const [gy, gm, gd] = gStr.split('-').map(Number);
    const [jy, jm, jd] = toJalali(gy, gm, gd);
    return `${jy}/${pad2(jm)}/${pad2(jd)}`;
}

// "YYYY/MM/DD" (Jalali) -> "YYYY-MM-DD" (Gregorian)
function jalaliStrToGregorianStr(jStr) {
    if (!jStr) return '';
    const [jy, jm, jd] = jStr.split('/').map(Number);
    const [gy, gm, gd] = toGregorian(jy, jm, jd);
    return `${gy}-${pad2(gm)}-${pad2(gd)}`;
}

function jalaliMonthLength(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    return isLeapJalaaliYear(jy) ? 30 : 29;
}
