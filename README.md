# Bank Loan Calculator Dashboard
A Python tool that sets up bank-style financial calculator behaviour, manages and corrects cash flows, and reconciles the differences caused by loan prepayments. It includes an interactive Streamlit dashboard.


## Features
- **Configurable calculator settings:** rounding mode (half-up or banker's), number of decimals, payments per year, payment timing (begin or end of period), and day count (ACT/365, ACT/360, 30/360).
- **Cent-accurate arithmetic:** all money values use Python's `Decimal`, so results match bank calculators and avoid floating-point drift.
- **Cash flow correction:** merges same-date flows, removes zero entries, sorts by date, and rejects flows with sign errors.
- **Loan schedule with prepayments:** supports early repayments with two modes: shorten the term or reduce the monthly payment.
- **Reconciliation:** the final payment absorbs rounding differences so the balance ends at exactly zero. Built-in checks confirm that principal and totals tie out.
- **XIRR:** solved by bisection, with an NPV vs discount rate chart.
- **Interactive dashboard:** KPI cards, balance chart, payment split, cumulative interest, editable cash flow table, and CSV export of the schedule.


## How it works
1. **Payment:** `P × r / (1 − (1 + r)^−n)`, rounded using the selected rounding mode.
2. **Schedule:** interest is calculated on the opening balance each period. The last payment is adjusted to clear any remaining balance.
3. **Prepayments:** extra principal is applied in the chosen month, and the schedule either ends earlier or recalculates the payment.
4. **XIRR:** finds the annual rate at which the net present value of dated cash flows is zero.
