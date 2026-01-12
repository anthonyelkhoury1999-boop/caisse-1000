import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
# --- Protection par mot de passe ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("Accès protégé")
    pwd = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if pwd == st.secrets["APP_PASSWORD"]:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    st.stop()
# --- Fin protection ---

# caisse_app_v2_fixed.py
# Boîte 1000$ — calcul de change + suggestion de retrait "mix" + ajustement manuel (saisie) + rapport imprimable

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import hashlib
import json

st.set_page_config(page_title="Boîte 1000 $ — Calcul de change", layout="centered")

# ------------------ PARAMÈTRES ------------------
TARGET = 100000  # 1000.00$ en cents

DENOMS = {
    # Billets
    "Billet 100 $": 10000,
    "Billet 50 $": 5000,
    "Billet 20 $": 2000,
    "Billet 10 $": 1000,
    "Billet 5 $": 500,

    # Rouleaux (Canada)
    "Rouleau 2 $ (25) — 50 $": 5000,
    "Rouleau 1 $ (25) — 25 $": 2500,
    "Rouleau 0,25 $ (40) — 10 $": 1000,
    "Rouleau 0,10 $ (50) — 5 $": 500,
    "Rouleau 0,05 $ (40) — 2 $": 200,

    # Pièces (vrac)
    "Pièce 2 $": 200,
    "Pièce 1 $": 100,
    "Pièce 0,25 $": 25,
    "Pièce 0,10 $": 10,
    "Pièce 0,05 $": 5,
}

ORDER = [
    "Billet 100 $",
    "Billet 50 $",
    "Billet 20 $",
    "Billet 10 $",
    "Billet 5 $",

    "Rouleau 2 $ (25) — 50 $",
    "Rouleau 1 $ (25) — 25 $",
    "Rouleau 0,25 $ (40) — 10 $",
    "Rouleau 0,10 $ (50) — 5 $",
    "Rouleau 0,05 $ (40) — 2 $",

    "Pièce 2 $",
    "Pièce 1 $",
    "Pièce 0,25 $",
    "Pièce 0,10 $",
    "Pièce 0,05 $",
]

COIN_KEYS = ["Pièce 2 $", "Pièce 1 $", "Pièce 0,25 $", "Pièce 0,10 $", "Pièce 0,05 $"]
BILL_KEYS = ["Billet 100 $", "Billet 50 $", "Billet 20 $", "Billet 10 $", "Billet 5 $"]
ROLL_KEYS = [
    "Rouleau 2 $ (25) — 50 $",
    "Rouleau 1 $ (25) — 25 $",
    "Rouleau 0,25 $ (40) — 10 $",
    "Rouleau 0,10 $ (50) — 5 $",
    "Rouleau 0,05 $ (40) — 2 $",
]


# ------------------ OUTILS ------------------
def cents_to_str(c: int) -> str:
    return f"{c / 100:.2f} $"


def total_cents(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)


def add_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}


def sub_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}


def clamp_to_avail(counts: dict, avail: dict) -> dict:
    out = {}
    for k in DENOMS:
        q = int(counts.get(k, 0))
        if q < 0:
            q = 0
        max_q = int(avail.get(k, 0))
        if q > max_q:
            q = max_q
        out[k] = q
    return out


def build_allowed_from_checks(prefix: str) -> list:
    allowed = []
    for k in ORDER:
        if st.session_state.get(f"{prefix}{k}", True):
            allowed.append(k)
    return allowed


def sum_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}


def count_total_coins(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) for k in COIN_KEYS)


def greedy_fill(amount_cents: int, denom_list_desc: list, avail: dict, already: dict) -> tuple[dict, int]:
    """
    Greedy: utilise denom_list_desc (déjà triée du +grand au +petit) pour couvrir amount_cents.
    Respecte les disponibilités (avail) ET ce qui est déjà pris (already).
    Retourne (added_counts, remaining_cents)
    """
    out = {k: 0 for k in DENOMS}
    remaining = int(amount_cents)

    for k in denom_list_desc:
        v = DENOMS[k]
        can_take = int(avail.get(k, 0)) - int(already.get(k, 0)) - int(out.get(k, 0))
        if can_take < 0:
            can_take = 0
        take = min(remaining // v, can_take)
        if take > 0:
            out[k] += int(take)
            remaining -= int(take) * v
        if remaining == 0:
            break

    return out, remaining


def suggest_with_mix(
    withdraw_cents: int,
    allowed: list,
    avail: dict,
    already: dict,
    prefer_small: bool,
    coin_cap: int,
    want_bills_10_5: bool,
) -> tuple[dict, int]:
    """
    Suggestion "mix" qui RESPECTE déjà (already) partout.
    """
    if withdraw_cents <= 0:
        return {k: 0 for k in DENOMS}, 0

    allowed_set = set(allowed)
    out = {k: 0 for k in DENOMS}
    remaining = int(withdraw_cents)

    # Pools autorisés
    bills_allowed = [k for k in BILL_KEYS if k in allowed_set]
    rolls_allowed = [k for k in ROLL_KEYS if k in allowed_set]
    coins_allowed = [k for k in COIN_KEYS if k in allowed_set]

    bills_desc = sorted(bills_allowed, key=lambda x: DENOMS[x], reverse=True)
    rolls_desc = sorted(rolls_allowed, key=lambda x: DENOMS[x], reverse=True)
    coins_desc = sorted(coins_allowed, key=lambda x: DENOMS[x], reverse=True)  # 2$ -> 0.05
    coins_asc = sorted(coins_allowed, key=lambda x: DENOMS[x])                # 0.05 -> 2$

    if not prefer_small:
        all_desc = sorted(allowed, key=lambda x: DENOMS[x], reverse=True)
        add1, rem1 = greedy_fill(remaining, all_desc, avail, already=already)
        out = sum_counts(out, add1)
        remaining = rem1
        return out, remaining

    # --- prefer_small = True (mix) ---

    # (1) Option: injecter quelques billets 10/5, sans dépasser la dispo (en tenant compte de already)
    if want_bills_10_5:
        for bk, desired in [("Billet 10 $", 2), ("Billet 5 $", 2)]:
            if bk in allowed_set and remaining >= DENOMS[bk]:
                can_take = int(avail.get(bk, 0)) - int(already.get(bk, 0)) - int(out.get(bk, 0))
                if can_take < 0:
                    can_take = 0
                take = min(desired, can_take, remaining // DENOMS[bk])
                if take > 0:
                    out[bk] += int(take)
                    remaining -= int(take) * DENOMS[bk]

    # (2) Couvrir le gros avec billets + rouleaux (sans pièces)
    big_pool = bills_desc + rolls_desc
    if big_pool and remaining > 0:
        add2, rem2 = greedy_fill(remaining, big_pool, avail, already=sum_counts(already, out))
        out = sum_counts(out, add2)
        remaining = rem2

    # (3) Finir avec pièces, limité coin_cap, en tenant compte de already
    if coins_allowed and remaining > 0:
        for ck in coins_asc:
            if remaining <= 0:
                break
            v = DENOMS[ck]
            can_take = int(avail.get(ck, 0)) - int(already.get(ck, 0)) - int(out.get(ck, 0))
            if can_take < 0:
                can_take = 0

            cap_left = max(0, coin_cap - count_total_coins(out))
            if cap_left <= 0:
                break

            take = min(remaining // v, can_take, cap_left)
            if take > 0:
                out[ck] += int(take)
                remaining -= int(take) * v

    # (4) Fallback: tenter le reste avec tout (gros->petit) en respectant already
    if remaining > 0:
        all_desc = sorted(allowed, key=lambda x: DENOMS[x], reverse=True)
        add4, rem4 = greedy_fill(remaining, all_desc, avail, already=sum_counts(already, out))
        out = sum_counts(out, add4)
        remaining = rem4

    return out, remaining


def hash_inputs(obj) -> str:
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def rows_report(open_c, depot_c, retrait_c, close_c):
    rows = []
    t_o = t_d = t_r = t_c = 0

    for k in ORDER:
        o = int(open_c.get(k, 0))
        d = int(depot_c.get(k, 0))
        r = int(retrait_c.get(k, 0))
        c = int(close_c.get(k, 0))

        rows.append({"Dénomination": k, "OPEN": o, "IN": d, "OUT": r, "CLOSE": c})

        t_o += o * DENOMS[k]
        t_d += d * DENOMS[k]
        t_r += r * DENOMS[k]
        t_c += c * DENOMS[k]

    rows.append(
        {
            "Dénomination": "TOTAL ($)",
            "OPEN": f"{t_o / 100:.2f}",
            "IN": f"{t_d / 100:.2f}",
            "OUT": f"{t_r / 100:.2f}",
            "CLOSE": f"{t_c / 100:.2f}",
        }
    )
    return rows


def build_print_html(rows, meta_line: str):
    body = ""
    for r in rows:
        body += (
            "<tr>"
            f"<td>{r['Dénomination']}</td>"
            f"<td>{r['OPEN']}</td>"
            f"<td>{r['IN']}</td>"
            f"<td>{r['OUT']}</td>"
            f"<td>{r['CLOSE']}</td>"
            "</tr>"
        )

    report_inner = f"""
      <div>
        <h2 style="margin:0;">Rapport — Boîte 1000 $</h2>
        <div style="opacity:0.75; font-size:12px; margin-top:4px;">{meta_line}</div>
      </div>
      <div style="height:12px;"></div>
      <table style="width:100%; border-collapse:collapse; font-size:14px; background:#ffffff; color:#000000;"
             border="1" cellpadding="6" cellspacing="0">
        <thead>
          <tr style="background:#f3f3f3; color:#000;">
            <th>Dénomination</th>
            <th>OPEN</th>
            <th>IN</th>
            <th>OUT</th>
            <th>CLOSE</th>
          </tr>
        </thead>
        <tbody>
          {body}
        </tbody>
      </table>
    """
    report_inner_js = report_inner.replace("`", "\\`")

    html = f"""
    <div style="font-family: Arial, sans-serif;">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
        <div>
          <h3 style="margin:0;">Aperçu du rapport</h3>
          <div style="opacity:0.7; font-size:12px;">Imprime uniquement le tableau.</div>
        </div>
        <button id="print-btn" style="
          padding:10px 14px;
          border-radius:10px;
          border:1px solid #ccc;
          cursor:pointer;
          font-weight:600;
          background:white;
        ">🖨️ Imprimer le rapport</button>
      </div>

      <div style="height:10px;"></div>
      <div id="report">{report_inner}</div>
    </div>

    <script>
      function printOnlyReport() {{
        var reportHtml = `{report_inner_js}`;
        var w = window.open('', '_blank', 'width=900,height=700');
        w.document.open();
        w.document.write('<html><head><title>Rapport boîte 1000</title>');
        w.document.write('<style>');
        w.document.write('body{{font-family:Arial,sans-serif;padding:18px;background:#fff;color:#000;}}');
        w.document.write('table{{width:100%;border-collapse:collapse;}}');
        w.document.write('th,td{{border:1px solid #000;padding:6px;}}');
        w.document.write('th{{background:#f3f3f3;}}');
        w.document.write('</style>');
        w.document.write('</head><body>');
        w.document.write(reportHtml);
        w.document.write('</body></html>');
        w.document.close();
        w.focus();
        w.print();
      }}
      const btn = document.getElementById('print-btn');
      if (btn) btn.addEventListener('click', printOnlyReport);
    </script>
    """
    return html


# ------------------ ÉTAT ------------------
if "locked_set_1000" not in st.session_state:
    st.session_state.locked_set_1000 = set()  # quelles dénominations sont "verrouillées"

if "show_report_1000" not in st.session_state:
    st.session_state.show_report_1000 = False

if "report_payload_1000" not in st.session_state:
    st.session_state.report_payload_1000 = None

if "last_out_inputs_hash_1000" not in st.session_state:
    st.session_state.last_out_inputs_hash_1000 = None


# ------------------ UI ------------------
# --- inside: for k in ORDER: ... ---

max_avail = int(after_in.get(k, 0))
widget_key = f"out_{k}"

# ensure key exists
if widget_key not in st.session_state:
    st.session_state[widget_key] = 0

def lock_this(denom: str):
    st.session_state.locked_set_1000 = set(st.session_state.locked_set_1000)
    st.session_state.locked_set_1000.add(denom)

def bump(denom: str, delta: int):
    key = f"out_{denom}"
    cur = int(st.session_state.get(key, 0))
    nxt = cur + delta
    if nxt < 0:
        nxt = 0
    if nxt > int(after_in.get(denom, 0)):
        nxt = int(after_in.get(denom, 0))
    st.session_state[key] = nxt
    lock_this(denom)
    st.rerun()

cols = st.columns([3.0, 0.7, 1.3, 0.7, 1.0, 1.6])
cols[0].write(k)

# ATM-style minus
cols[1].button("−", key=f"minus_{k}", on_click=bump, args=(k, -1), use_container_width=True)

# input (still typeable)
cols[2].number_input(
    "OUT",
    min_value=0,
    max_value=max_avail,
    value=int(st.session_state.get(widget_key, 0)),
    step=1,
    key=widget_key,
    label_visibility="collapsed",
    on_change=lock_this,
    args=(k,),
)

# ATM-style plus
cols[3].button("+", key=f"plus_{k}", on_click=bump, args=(k, +1), use_container_width=True)

is_locked = (k in st.session_state.locked_set_1000)
cols[4].write("🔒" if is_locked else "↻ auto")
cols[5].write(f"Dispo: {max_avail}")

# 4) CLOSE
st.header("4) CLOSE — Contenu final")

if diff < 0:
    close_counts = after_in
else:
    close_counts = sub_counts(after_in, retrait_counts)

total_close = total_cents(close_counts)
st.success("TOTAL CLOSE : " + cents_to_str(total_close))

if total_close == TARGET:
    st.success("✅ La boîte est revenue exactement à 1000,00 $.")
else:
    st.info("ℹ️ La boîte n’est pas exactement à 1000,00 $ (tolérance possible selon règles internes).")

st.divider()

# 5) Rapport imprimable
st.header("5) Rapport imprimable (tableau seulement)")

colA, colB = st.columns([1, 1])
with colA:
    gen = st.button("GÉNÉRER LE RAPPORT")
with colB:
    clear = st.button("EFFACER LE RAPPORT")

if clear:
    st.session_state.show_report_1000 = False
    st.session_state.report_payload_1000 = None

if gen:
    rows = rows_report(
        open_counts,
        depot_counts,
        retrait_counts if diff >= 0 else {k: 0 for k in DENOMS},
        close_counts,
    )
    meta = "Généré le " + datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.report_payload_1000 = {"rows": rows, "meta": meta}
    st.session_state.show_report_1000 = True

if st.session_state.show_report_1000 and st.session_state.report_payload_1000:
    html = build_print_html(
        st.session_state.report_payload_1000["rows"],
        st.session_state.report_payload_1000["meta"],
    )
    components.html(html, height=560, scrolling=True)
