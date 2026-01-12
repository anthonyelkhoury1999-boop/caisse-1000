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

# caisse_app_v2.py
# Boîte 1000$ — calcul de change + suggestion de retrait "mix" + ajustement manuel (saisie) + rapport imprimable
#
# Objectif:
# 1) OPEN: contenu actuel (quantités)
# 2) IN: dépôt (quantités)
# 3) OUT: l'app suggère quoi retirer pour revenir à 1000$ (mix billets + pièces)
#    - Ajustement: tu peux ÉCRIRE la quantité OUT par dénomination (pas juste +/-)
#    - Si tu changes une dénomination, le reste se recalcule automatiquement
# 4) CLOSE: contenu final
# 5) Rapport imprimable OPEN / IN / OUT / CLOSE (bouton qui imprime le tableau seulement)
#
# Notes:
# - La boîte 1000$ sert à faire du change => on NE BLOQUE PAS si l'exact est impossible.
#   On affiche au pire un WARNING, mais on continue.

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

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


def greedy_fill(amount_cents: int, denom_list_desc: list, avail: dict, already: dict) -> tuple[dict, int]:
    """
    Greedy: utilise denom_list_desc (déjà triée du +grand au +petit) pour couvrir amount_cents.
    Respecte les disponibilités (avail) et ce qui est déjà pris (already).
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


def sum_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}


def count_total_coins(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) for k in COIN_KEYS)


def value_of_keys(counts: dict, keys: list) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in keys)


def suggest_with_mix(
    withdraw_cents: int,
    allowed: list,
    avail: dict,
    prefer_small: bool,
    coin_cap: int,
    want_bills_10_5: bool,
) -> tuple[dict, int]:
    """
    Suggestion "mix" pour éviter de vider toutes les pièces.
    Stratégie:
      - Si prefer_small:
          1) (option) prendre quelques billets 10/5 d'abord (1-2) si ça aide
          2) couvrir le gros du montant avec billets/rouleaux (gros->petit) mais sans aller dans les pièces
          3) finir le reste avec pièces (petit->grand ou grand->petit, mais limité par coin_cap)
          4) si encore non couvert, on tente de nouveau avec tout ce qui reste (sans bloquer)
      - Si prefer_small = False:
          Greedy gros->petit classique (incluant tout)
    """
    if withdraw_cents <= 0:
        return {k: 0 for k in DENOMS}, 0

    allowed_set = set(allowed)
    out = {k: 0 for k in DENOMS}
    remaining = int(withdraw_cents)

    # Listes autorisées
    bills_allowed = [k for k in BILL_KEYS if k in allowed_set]
    rolls_allowed = [k for k in ROLL_KEYS if k in allowed_set]
    coins_allowed = [k for k in COIN_KEYS if k in allowed_set]

    # Tri utilitaires
    bills_desc = sorted(bills_allowed, key=lambda x: DENOMS[x], reverse=True)
    rolls_desc = sorted(rolls_allowed, key=lambda x: DENOMS[x], reverse=True)
    coins_desc = sorted(coins_allowed, key=lambda x: DENOMS[x], reverse=True)  # 2$ -> 0.05
    coins_asc = sorted(coins_allowed, key=lambda x: DENOMS[x])                # 0.05 -> 2$

    if not prefer_small:
        # Gros->petit sur tout
        all_desc = sorted(allowed, key=lambda x: DENOMS[x], reverse=True)
        add1, rem1 = greedy_fill(remaining, all_desc, avail, out)
        out = sum_counts(out, add1)
        remaining = rem1
        return out, remaining

    # --- prefer_small = True (mix) ---

    # (1) Option: forcer quelques billets 10/5 (sans vider)
    if want_bills_10_5:
        for bk, desired in [("Billet 10 $", 2), ("Billet 5 $", 2)]:
            if bk in allowed_set:
                max_av = int(avail.get(bk, 0))
                if max_av > 0 and remaining >= DENOMS[bk]:
                    take = min(desired, max_av, remaining // DENOMS[bk])
                    out[bk] += int(take)
                    remaining -= int(take) * DENOMS[bk]

    # (2) Couvrir le gros avec billets + rouleaux (sans pièces)
    big_pool = bills_desc + rolls_desc
    if big_pool:
        add2, rem2 = greedy_fill(remaining, big_pool, avail, out)
        out = sum_counts(out, add2)
        remaining = rem2

    # (3) Finir avec pièces, mais LIMITÉ par coin_cap
    if coins_allowed and remaining > 0:
        # remplir en petites (0.05->...) pour mieux "finir"
        for ck in coins_asc:
            if remaining <= 0:
                break
            v = DENOMS[ck]
            can_take = int(avail.get(ck, 0)) - int(out.get(ck, 0))
            if can_take < 0:
                can_take = 0

            # limite coins totale
            cap_left = max(0, coin_cap - count_total_coins(out))
            if cap_left <= 0:
                break

            take = min(remaining // v, can_take, cap_left)
            if take > 0:
                out[ck] += int(take)
                remaining -= int(take) * v

    # (4) Si encore restant, on tente un fallback (sans bloquer)
    if remaining > 0:
        # On autorise cette fois tout (gros->petit) pour réduire remaining, mais ça peut laisser un reste
        all_desc = sorted(allowed, key=lambda x: DENOMS[x], reverse=True)
        add4, rem4 = greedy_fill(remaining, all_desc, avail, out)
        out = sum_counts(out, add4)
        remaining = rem4

    return out, remaining


def recompute_after_manual_locked(
    target_withdraw: int,
    allowed: list,
    avail: dict,
    locked: dict,
    prefer_small: bool,
    coin_cap: int,
    want_bills_10_5: bool,
) -> tuple[dict, int]:
    """
    Combine:
      - locked quantities (manuel) appliquées d'abord
      - puis suggestion sur le reste (mix) avec les types autorisés
    """
    locked = clamp_to_avail(locked, avail)

    out = {k: 0 for k in DENOMS}
    for k, q in locked.items():
        out[k] = int(q)

    locked_value = total_cents(out)
    remaining_needed = target_withdraw - locked_value

    if remaining_needed < 0:
        # dépassement (locked trop haut)
        return out, remaining_needed

    # Suggestion sur le reste, en respectant "out" comme déjà pris
    # -> on passe un avail diminué implicitement via "out"
    sugg, rem = suggest_with_mix(
        withdraw_cents=remaining_needed,
        allowed=allowed,
        avail=avail,
        prefer_small=prefer_small,
        coin_cap=max(0, coin_cap - count_total_coins(out)),
        want_bills_10_5=want_bills_10_5,
    )

    # sugg doit aussi respecter ce qui est déjà pris (out). On clamp.
    # (suggest_with_mix tient compte de avail, mais pas de out existant sur les mêmes keys)
    # Donc: on clamp final.
    combined = sum_counts(out, sugg)
    combined = clamp_to_avail(combined, avail)

    # Recalculer remaining global
    remaining_global = target_withdraw - total_cents(combined)
    return combined, remaining_global


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

    # Fond blanc forcé pour lisibilité (dark mode)
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
if "locked_retrait_1000" not in st.session_state:
    st.session_state.locked_retrait_1000 = {}  # denom->qty (manuel)

if "show_report_1000" not in st.session_state:
    st.session_state.show_report_1000 = False

if "report_payload_1000" not in st.session_state:
    st.session_state.report_payload_1000 = None

if "last_inputs_hash" not in st.session_state:
    st.session_state.last_inputs_hash = None


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
diff = total_after - TARGET  # montant à retirer

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
    coin_cap = st.slider(
        "Max total de pièces en OUT (limite)",
        min_value=0,
        max_value=600,
        value=140,
        step=10,
    )
    want_bills_10_5 = st.checkbox("Inclure automatiquement des billets 10$ et 5$", value=True)

    bcol1, bcol2, bcol3 = st.columns([1.1, 1.3, 2.6])
    with bcol1:
        if st.button("SUGGÉRER RETRAIT"):
            # reset manuel -> on repart de la suggestion
            st.session_state.locked_retrait_1000 = {}
            st.rerun()
    with bcol2:
        if st.button("RÉINITIALISER MANUEL"):
            st.session_state.locked_retrait_1000 = {}
            st.rerun()

    if not allowed:
        st.warning("Choisis au moins un type autorisé pour le retrait.")
        retrait_counts = {k: 0 for k in DENOMS}
        remaining = diff
    else:
        # Recalcule en tenant compte du manuel (locked)
        locked = dict(st.session_state.locked_retrait_1000)

        retrait_counts, remaining = recompute_after_manual_locked(
            target_withdraw=diff,
            allowed=allowed,
            avail=after_in,
            locked=locked,
            prefer_small=prefer_small,
            coin_cap=coin_cap,
            want_bills_10_5=want_bills_10_5,
        )

        out_total = total_cents(retrait_counts)
        st.write(f"TOTAL OUT (proposé + manuel): **{cents_to_str(out_total)}**")

        # Boîte 1000$ => on ne bloque jamais
        if remaining > 0:
            st.warning(
                f"Reste non couvert: **{cents_to_str(remaining)}**. "
                "La boîte ne peut pas couvrir exactement avec les types autorisés + la dispo."
            )
        elif remaining < 0:
            st.warning(
                f"Tu as dépassé la cible de retrait de **{cents_to_str(-remaining)}** "
                "(manuel trop élevé)."
            )
        else:
            st.success("✅ Retrait exact atteint.")

        st.subheader("Ajuster le retrait (saisie)")
        st.caption("Écris directement la quantité OUT par dénomination. Le reste se recalcule.")

        # Table d'ajustement
        for k in ORDER:
            if k not in allowed:
                continue

            max_avail = int(after_in.get(k, 0))
            suggested = int(retrait_counts.get(k, 0))

            cols = st.columns([3.0, 1.2, 1.6])
            cols[0].write(k)

            current_locked = int(st.session_state.locked_retrait_1000.get(k, suggested))
            new_val = cols[1].number_input(
                "OUT",
                min_value=0,
                max_value=max_avail,
                value=current_locked,
                step=1,
                key=f"manual_out_{k}",
                label_visibility="collapsed",
            )
            cols[2].write(f"Dispo: {max_avail}")

            if new_val != current_locked:
                st.session_state.locked_retrait_1000[k] = int(new_val)
                st.rerun()

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
    st.info("ℹ️ La boîte n’est pas exactement à 1000,00 $ (selon règles internes, tolérance possible).")

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
