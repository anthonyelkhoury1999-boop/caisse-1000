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

# caisse_app_v3.py
# Boîte 1000$ — calcul de change + suggestion de retrait "mix" + ajustement manuel (saisie + boutons +/-) + rapport imprimable
#
# Objectif:
# 1) OPEN: contenu actuel (quantités)
# 2) IN: dépôt (quantités)
# 3) OUT: l'app suggère quoi retirer pour revenir à 1000$ (mix billets + pièces)
#    - Ajustement: tu peux ÉCRIRE la quantité OUT par dénomination + boutons ATM +/- (pas juste le spinner)
#    - Dès que tu modifies une ligne, elle devient "verrouillée" et le reste se recalcule automatiquement
#    - Tu peux déverrouiller tout, ou seulement les pièces
# 4) CLOSE: contenu final
# 5) Rapport imprimable OPEN / IN / OUT / CLOSE (bouton qui imprime le tableau seulement)
#
# Notes:
# - La boîte 1000$ sert à faire du change => on NE BLOQUE PAS si l'exact est impossible.
#   On affiche au pire un WARNING, mais on continue.

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import json
import hashlib

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


def sum_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}


def count_total_coins(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) for k in COIN_KEYS)


def build_allowed_from_checks(prefix: str) -> list:
    allowed = []
    for k in ORDER:
        if st.session_state.get(f"{prefix}{k}", True):
            allowed.append(k)
    return allowed


def greedy_fill(amount_cents: int, denom_list_desc: list, avail: dict, already: dict) -> tuple[dict, int]:
    """
    Greedy: utilise denom_list_desc (triée du +grand au +petit) pour couvrir amount_cents.
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
    Suggestion "mix" qui respecte already partout.
    """
    if withdraw_cents <= 0:
        return {k: 0 for k in DENOMS}, 0

    allowed_set = set(allowed)
    out = {k: 0 for k in DENOMS}
    remaining = int(withdraw_cents)

    bills_allowed = [k for k in BILL_KEYS if k in allowed_set]
    rolls_allowed = [k for k in ROLL_KEYS if k in allowed_set]
    coins_allowed = [k for k in COIN_KEYS if k in allowed_set]

    bills_desc = sorted(bills_allowed, key=lambda x: DENOMS[x], reverse=True)
    rolls_desc = sorted(rolls_allowed, key=lambda x: DENOMS[x], reverse=True)
    coins_asc = sorted(coins_allowed, key=lambda x: DENOMS[x])  # 0.05 -> 2$

    if not prefer_small:
        all_desc = sorted(allowed, key=lambda x: DENOMS[x], reverse=True)
        add1, rem1 = greedy_fill(remaining, all_desc, avail, already=already)
        out = sum_counts(out, add1)
        remaining = rem1
        return out, remaining

    # (1) Option: injecter quelques billets 10/5 d'abord
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

    # (3) Finir avec pièces, limité par coin_cap
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

    # (4) Fallback: tenter le reste avec tout (gros->petit)
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
    st.session_state.locked_set_1000 = set()  # denoms verrouillés

if "show_report_1000" not in st.session_state:
    st.session_state.show_report_1000 = False

if "report_payload_1000" not in st.session_state:
    st.session_state.report_payload_1000 = None

if "last_out_inputs_hash_1000" not in st.session_state:
    st.session_state.last_out_inputs_hash_1000 = None


# ------------------ UI ------------------
st.title("Boîte 1000 $ — Calcul de change")
st.caption("Après dépôt + retrait, la boîte vise **1000,00 $** (base).")
st.info("⚠️ Si tu utilises des **rouleaux**, évite de compter les mêmes pièces en vrac (double comptage).")
st.divider()

# 1) OPEN
st.header("1) OPEN — Contenu actuel (avant dépôt)")
open_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        open_counts[k] = st.number_input(k, min_value=0, step=1, value=0, key=f"open_{k}")

total_open = total_cents(open_counts)
st.success("TOTAL OPEN : " + cents_to_str(total_open))
st.divider()

# 2) IN
st.header("2) IN — Dépôt (ce qui est ajouté)")
depot_counts = {}
d1, d2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (d1 if i % 2 == 0 else d2):
        depot_counts[k] = st.number_input(f"{k} (IN)", min_value=0, step=1, value=0, key=f"in_{k}")

total_in = total_cents(depot_counts)
after_in = add_counts(open_counts, depot_counts)
total_after = total_cents(after_in)

st.info("TOTAL IN : " + cents_to_str(total_in))
st.success("TOTAL APRÈS IN : " + cents_to_str(total_after))
st.divider()

# 3) OUT
st.header("3) OUT — Retrait (pour revenir à 1000 $)")
diff = total_after - TARGET  # à retirer

st.write(f"Cible: **{cents_to_str(TARGET)}**")
st.write(f"Écart (après IN - cible) : **{cents_to_str(diff)}**")

if diff < 0:
    st.warning("La boîte est sous 1000 $. Ici il faudrait **AJOUTER** de l’argent, pas retirer.")
    retrait_counts = {k: 0 for k in DENOMS}
    remaining = diff
else:
    st.subheader("Types autorisés (ce que tu veux donner en change)")
    st.caption("Décoche ce que tu ne veux PAS utiliser dans le retrait.")

    a1, a2 = st.columns(2)
    for i, k in enumerate(ORDER):
        with (a1 if i % 2 == 0 else a2):
            st.checkbox(k, value=True, key=f"allow_{k}")

    allowed = build_allowed_from_checks("allow_")

    prefer_mode = st.radio(
        "Priorité de suggestion",
        ["Petites coupures / pièces (mix équilibré)", "Grosses coupures (moins d’items)"],
        index=0,
    )
    prefer_small = (prefer_mode == "Petites coupures / pièces (mix équilibré)")

    st.subheader("Réglages de distribution (pour éviter de vider les pièces)")
    coin_cap = st.slider("Max total de pièces en OUT (limite)", 0, 600, 140, 10)
    want_bills_10_5 = st.checkbox("Inclure automatiquement des billets 10$ et 5$", value=True)

    bcol1, bcol2, bcol3 = st.columns([1.3, 1.3, 1.4])
    with bcol1:
        if st.button("RÉINITIALISER (déverrouiller tout)"):
            st.session_state.locked_set_1000 = set()
            for k in ORDER:
                key = f"out_{k}"
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with bcol2:
        if st.button("DÉVERROUILLER SEULEMENT LES PIÈCES"):
            st.session_state.locked_set_1000 = {k for k in st.session_state.locked_set_1000 if k not in COIN_KEYS}
            for k in COIN_KEYS:
                key = f"out_{k}"
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with bcol3:
        if st.button("VIDER OUT (tout à 0)"):
            # met tout à 0 et verrouille tout (comme “ATM remove all”)
            st.session_state.locked_set_1000 = set(allowed)
            for k in allowed:
                st.session_state[f"out_{k}"] = 0
            st.rerun()

    if not allowed:
        st.warning("Choisis au moins un type autorisé pour le retrait.")
        retrait_counts = {k: 0 for k in DENOMS}
        remaining = diff
    else:
        # Hash des paramètres pour rafraîchir les non-verrouillés
        refresh_payload = {
            "diff": diff,
            "allowed": allowed,
            "prefer_small": prefer_small,
            "coin_cap": coin_cap,
            "want_bills_10_5": want_bills_10_5,
            "avail": after_in,
        }
        cur_hash = hash_inputs(refresh_payload)
        hash_changed = (st.session_state.last_out_inputs_hash_1000 != cur_hash)

        def lock_this(denom: str):
            st.session_state.locked_set_1000 = set(st.session_state.locked_set_1000)
            st.session_state.locked_set_1000.add(denom)

        def bump(denom: str, delta: int):
            key = f"out_{denom}"
            cur = int(st.session_state.get(key, 0))
            nxt = cur + delta
            if nxt < 0:
                nxt = 0
            max_av = int(after_in.get(denom, 0))
            if nxt > max_av:
                nxt = max_av
            st.session_state[key] = nxt
            lock_this(denom)
            st.rerun()

        # Suggestion de base (sans locked)
        base_sugg, _ = suggest_with_mix(
            withdraw_cents=diff,
            allowed=allowed,
            avail=after_in,
            already={k: 0 for k in DENOMS},
            prefer_small=prefer_small,
            coin_cap=coin_cap,
            want_bills_10_5=want_bills_10_5,
        )

        # Init / refresh des OUT widgets (seulement non verrouillés)
        for k in allowed:
            wkey = f"out_{k}"
            if (wkey not in st.session_state) or (hash_changed and (k not in st.session_state.locked_set_1000)):
                st.session_state[wkey] = int(base_sugg.get(k, 0))

        # Locked dict = valeurs seulement des verrouillés
        locked_dict = {k: 0 for k in DENOMS}
        for k in st.session_state.locked_set_1000:
            locked_dict[k] = int(st.session_state.get(f"out_{k}", 0))
        locked_dict = clamp_to_avail(locked_dict, after_in)

        locked_value = total_cents(locked_dict)
        remaining_needed = diff - locked_value

        # Suggestion du reste en respectant locked
        rest_sugg = {k: 0 for k in DENOMS}
        if remaining_needed > 0:
            rest_sugg, _rem = suggest_with_mix(
                withdraw_cents=remaining_needed,
                allowed=allowed,
                avail=after_in,
                already=locked_dict,
                prefer_small=prefer_small,
                coin_cap=max(0, coin_cap - count_total_coins(locked_dict)),
                want_bills_10_5=want_bills_10_5,
            )
        # Combine
        retrait_counts = clamp_to_avail(sum_counts(locked_dict, rest_sugg), after_in)
        out_total = total_cents(retrait_counts)
        remaining = diff - out_total

        st.write(f"TOTAL OUT : **{cents_to_str(out_total)}**")

        if remaining > 0:
            st.warning(
                f"Reste non couvert: **{cents_to_str(remaining)}**. "
                "Impossible d’atteindre exact avec la dispo/types/limites actuels (on ne bloque pas)."
            )
        elif remaining < 0:
            st.warning(f"Tu as dépassé la cible de retrait de **{cents_to_str(-remaining)}** (trop retiré).")
        else:
            st.success("✅ Retrait exact atteint.")

        st.subheader("Ajuster le retrait (saisie + boutons +/-)")
        st.caption("Tape une valeur OU utilise les boutons. Toute ligne modifiée devient 🔒, le reste se recalcule.")

        # UI par ligne
        for k in ORDER:
            if k not in allowed:
                continue

            max_avail = int(after_in.get(k, 0))
            wkey = f"out_{k}"
            if wkey not in st.session_state:
                st.session_state[wkey] = 0

            cols = st.columns([3.0, 0.7, 1.4, 0.7, 1.0, 1.6])
            cols[0].write(k)

            cols[1].button("−", key=f"minus_{k}", on_click=bump, args=(k, -1), use_container_width=True)

            cols[2].number_input(
                "OUT",
                min_value=0,
                max_value=max_avail,
                value=int(st.session_state.get(wkey, 0)),
                step=1,
                key=wkey,
                label_visibility="collapsed",
                on_change=lock_this,
                args=(k,),
            )

            cols[3].button("+", key=f"plus_{k}", on_click=bump, args=(k, +1), use_container_width=True)

            is_locked = (k in st.session_state.locked_set_1000)
            cols[4].write("🔒" if is_locked else "↻ auto")
            cols[5].write(f"Dispo: {max_avail}")

        st.session_state.last_out_inputs_hash_1000 = cur_hash

st.divider()

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
    st.info("ℹ️ La boîte n’est pas exactement à 1000,00 $ (tolérance possible).")

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
