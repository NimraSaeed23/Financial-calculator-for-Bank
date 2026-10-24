from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import date
from typing import Dict, List, Optional, Tuple

getcontext().prec = 28
D = Decimal


@dataclass(frozen=True)
class CalcSettings:
    places: int = 2
    rounding: str = ROUND_HALF_UP
    payments_per_year: int = 12
    day_count: str = "ACT/365"
    payment_at_start: bool = False

    def q(self, x) -> Decimal:
        return D(x).quantize(D(1).scaleb(-self.places), rounding=self.rounding)

    def periodic_rate(self, annual_rate) -> Decimal:
        return D(str(annual_rate)) / self.payments_per_year


def year_fraction(d1: date, d2: date, convention: str) -> float:
    if convention == "ACT/365":
        return (d2 - d1).days / 365
    if convention == "ACT/360":
        return (d2 - d1).days / 360
    if convention == "30/360":
        dd1, dd2 = min(d1.day, 30), (min(d2.day, 30) if d1.day >= 30 else d2.day)
        return (360 * (d2.year - d1.year) + 30 * (d2.month - d1.month) + (dd2 - dd1)) / 360
    raise ValueError(f"Unknown day count: {convention}")


def pmt(principal, annual_rate, n: int, s: CalcSettings) -> Decimal:
    r, P = s.periodic_rate(annual_rate), D(principal)
    pay = P / n if r == 0 else P * r / (1 - (1 + r) ** -n)
    if s.payment_at_start:
        pay /= (1 + r)
    return s.q(pay)


def normalize_cash_flows(flows: List[Tuple[date, float]], s: CalcSettings):
    merged: Dict[date, Decimal] = {}
    for d, amt in flows:
        merged[d] = merged.get(d, D(0)) + D(str(amt))
    out = sorted((d, s.q(a)) for d, a in merged.items() if s.q(a) != 0)
    if not (any(a > 0 for _, a in out) and any(a < 0 for _, a in out)):
        raise ValueError("Cash flows need at least one inflow and one outflow.")
    return out


def xnpv(rate: float, flows, s: CalcSettings) -> float:
    t0 = flows[0][0]
    return sum(float(a) / (1 + rate) ** year_fraction(t0, d, s.day_count) for d, a in flows)


def xirr(flows, s: CalcSettings, lo=-0.99, hi=10.0, tol=1e-10) -> float:
    f_lo, f_hi = xnpv(lo, flows, s), xnpv(hi, flows, s)
    if f_lo * f_hi > 0:
        raise ValueError("IRR not bracketed.")
    for _ in range(300):
        mid = (lo + hi) / 2
        f_mid = xnpv(mid, flows, s)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def build_schedule(principal, annual_rate, n: int, s: CalcSettings,
                   reductions: Optional[Dict[int, float]] = None,
                   mode: str = "shorten_term") -> List[dict]:
    reductions = {k: D(str(v)) for k, v in (reductions or {}).items()}
    r = s.periodic_rate(annual_rate)
    bal, pay, end = s.q(principal), pmt(principal, annual_rate, n, s), n
    rows, k = [], 1
    while bal > 0 and k <= n:
        interest = s.q(bal * r)
        is_last = (k == end) or (pay >= bal + interest)
        payment = bal + interest if is_last else pay
        princ = payment - interest
        extra = min(s.q(reductions.get(k, 0)), bal - princ) if not is_last else D(0)
        bal = s.q(bal - princ - extra)
        rows.append(dict(period=k, payment=payment, interest=interest,
                         principal=princ, extra=extra, balance=bal))
        if extra > 0 and mode == "reduce_payment" and bal > 0:
            pay = pmt(bal, annual_rate, end - k, s)
        k += 1
    return rows


def reconcile(base, reduced, principal, s: CalcSettings) -> dict:
    tot = lambda rows, key: sum((x[key] for x in rows), D(0))
    P = s.q(principal)
    for name, rows in (("base", base), ("reduced", reduced)):
        paid = tot(rows, "principal") + tot(rows, "extra")
        assert paid == P, f"{name}: principal mismatch"
    return dict(
        interest_saved=tot(base, "interest") - tot(reduced, "interest"),
        periods_saved=len(base) - len(reduced),
        total_paid_base=tot(base, "payment"),
        total_paid_reduced=tot(reduced, "payment") + tot(reduced, "extra"),
    )
