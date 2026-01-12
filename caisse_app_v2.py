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

st.set_page_config(page_title="Caisse 1000 $ — Boîte de change", layout="centered")

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


# ------------------ OUTILS ------------------
def cents_to_str(c: int) -> str:
    return f"{c/100:.2f} $"

def total_cents(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)

def add_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}

def sub_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}

def clamp_locked(locked: dict, max_available: dict) -> dict:
    out = dict(locked)
    for k in list(out.keys()):
        out[k] = int(out[k])
        if out[k] < 0:
            out[k] = 0
        if out[k] > int(max_available.get(k, 0)):
            out[k] = int(max_available.get(k, 0))
    return out

def fill_greedy(target_withdraw_cents: int, allowed: list, available: dict, locked: dict, prefer_small: bool):
    """
    Calcule un retrait EXACT (si possible).
    - locked: quantités verrouillées par l'utilisateur
    - prefer_small=True: propose d'abord les petites valeurs (souvent mieux pour "faire du change")
      prefer_small=False: propose d'abord les grosses valeurs (moins de pièces/billets)
    Retour: (out_counts, remaining_cents_after)
    """
    out = {k: 0 for k in DENOMS}

    # Appliquer verrouillage
    for k, q in locked.items():
        out[k] = int(q)

    remaining = target_withdraw_cents - sum(out[k] * DENOMS[k] for k in DENOMS)
    if remaining < 0:
        return out, remaining  # retrait trop grand

    allowed_sorted = sorted(allowed, key=lambda x: DENOMS[x])  # SMALL → BIG

    for k in allowed_sorted:
        if k in locked:
            continue
        v = DENOMS[k]
        max_can_take = int(available.get(k, 0)) - int(out.get(k, 0))
        if max_can_take < 0:
            max_can_take = 0
        take = min(remaining // v, max_can_take)
        out[k] += int(take)
        remaining -= int(take) * v

    return out, remaining

def rows_report(open_c, depot_c, retrait_c, close_c):
    """
    Tableau: Dénomination | OPEN | DÉPÔT | RETRAIT | FERMETURE
    + ligne TOTAL($)
    """
    rows = []
    t_o = t_d = t_r = t_c = 0

    for k in ORDER:
        o = int(open_c.get(k, 0))
        d = int(depot_c.get(k, 0))
        r = int(retrait_c.get(k, 0))
        c = int(close_c.get(k, 0))

        rows.append({
            "Dénomination": k,
            "OPEN": o,
            "DÉPÔT": d,
            "RETRAIT": r,
            "FERMETURE": c,
        })

        t_o += o * DENOMS[k]
        t_d += d * DENOMS[k]
        t_r += r * DENOMS[k]
        t_c += c * DENOMS[k]

    rows.append({
        "Dénomination": "TOTAL ($)",
        "OPEN": f"{t_o/100:.2f}",
        "DÉPÔT": f"{t_d/100:.2f}",
        "RETRAIT": f"{t_r/100:.2f}",
        "FERMETURE": f"{t_c/100:.2f}",
    })
    return rows

def build_print_html(rows, meta_line: str):
    body = ""
    for r in rows:
        body += (
            "<tr>"
            f"<td>{r['Dénomination']}</td>"
            f"<td>{r['OPEN']}</td>"
            f"<td>{r['DÉPÔT']}</td>"
            f"<td>{r['RETRAIT']}</td>"
            f"<td>{r['FERMETURE']}</td>"
            "</tr>"
        )

    # Force fond blanc + texte noir pour être lisible en dark mode
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
            <th>DÉPÔT</th>
            <th>RETRAIT</th>
            <th>FERMETURE</th>
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
    st.session_state.locked_retrait_1000 = {}

if "show_report_1000" not in st.session_state:
    st.session_state.show_report_1000 = False

if "report_payload_1000" not in st.session_state:
    st.session_state.report_payload_1000 = None


# ------------------ UI ------------------
st.title("Boîte 1000 $ — Calcul de change")
st.caption("Objectif: après dépôt + retrait, la boîte doit revenir à **1000,00 $**.")

st.info("⚠️ Si vous utilisez des **rouleaux**, évitez de compter en plus les **mêmes pièces en vrac** (sinon double comptage).")

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

# 2) DÉPÔT
st.header("2) DÉPÔT — Ce qui est ajouté dans la boîte")
depot_counts = {}
d1, d2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (d1 if i % 2 == 0 else d2):
        depot_counts[k] = st.number_input(f"{k} (DÉPÔT)", min_value=0, step=1, value=0, key=f"depot_{k}")

total_depot = total_cents(depot_counts)
after_in = add_counts(open_counts, depot_counts)
total_after = total_cents(after_in)

st.info("TOTAL DÉPÔT : " + cents_to_str(total_depot))
st.success("TOTAL APRÈS DÉPÔT : " + cents_to_str(total_after))

st.divider()

# 3) RETRAIT recommandé + ajustable
st.header("3) RETRAIT — Pour revenir à 1000 $")

diff = total_after - TARGET  # montant à retirer
st.write("Cible: **" + cents_to_str(TARGET) + "**")
st.write("Écart (après dépôt - cible): **" + cents_to_str(diff) + "**")

if diff < 0:
    st.warning("La boîte est en dessous de 1000 $. Ici il faudrait AJOUTER de l’argent, pas retirer.")
    retrait_counts = {k: 0 for k in DENOMS}
    remaining_after = diff
else:
    st.subheader("Types autorisés (ce que tu veux donner en change)")
    st.caption("Décoche les types que tu ne veux pas utiliser pour le retrait.")
    allowed = []
    a1, a2 = st.columns(2)
    for i, k in enumerate(ORDER):
        with (a1 if i % 2 == 0 else a2):
            if st.checkbox(k, value=True, key=f"allow_{k}"):
                allowed.append(k)

    prefer_mode = st.radio(
        "Priorité de suggestion",
        ["Petites coupures / pièces", "Grosses coupures (moins d’items)"],
        index=0
    )
    prefer_small = (prefer_mode == "Petites coupures / pièces")

    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("SUGGÉRER RETRAIT"):
            st.session_state.locked_retrait_1000 = {}
    with cols[1]:
        if st.button("RÉINITIALISER AJUSTEMENTS"):
            st.session_state.locked_retrait_1000 = {}

    # sécuriser le lock selon la dispo
    st.session_state.locked_retrait_1000 = clamp_locked(st.session_state.locked_retrait_1000, after_in)

    if not allowed:
        st.error("Choisis au moins un type autorisé pour le retrait.")
        retrait_counts = {k: 0 for k in DENOMS}
        remaining_after = diff
    else:
        retrait_counts, remaining_after = fill_greedy(
            target_withdraw_cents=diff,
            allowed=allowed,
            available=after_in,
            locked=st.session_state.locked_retrait_1000,
            prefer_small=prefer_small
        )
        
       if remaining > 0:
            st.warning(f"Impossible de couvrir le reste ({cents_to_str(remaining)}) " "avec le contenu actuel de la caisse.")
           
        if remaining_after == 0:
            st.success("RETRAIT proposé : " + cents_to_str(total_cents(retrait_counts)))
        else:
          # For the 1000$ box, we NEVER block
          # Remaining will be handled by smaller denominations
         st.write("Montant restant non couvert : **" + cents_to_str(remaining_after) + "**")

        st.subheader("Ajuster le retrait")
        st.caption("Clique ➖/➕ pour ajuster une dénomination, puis l’app recalcule le reste automatiquement.")

        # UI d’ajustement (➕ visible, pas le caractère '+')
        for k in ORDER:
            if k not in allowed:
                continue

            q = int(retrait_counts.get(k, 0))
            max_avail = int(after_in.get(k, 0))

            row = st.columns([2.8, 1.1, 1.1, 1.4, 1.6])
            row[0].write(k)

            minus = row[1].button("➖", key=f"minus1000_{k}")
            plus  = row[2].button("➕", key=f"plus1000_{k}")

            row[3].write(f"RETRAIT: **{q}**")
            row[4].write(f"Dispo: {max_avail}")

            if minus or plus:
                locked = dict(st.session_state.locked_retrait_1000)

                # démarrer le lock sur la proposition actuelle
                if k not in locked:
                    locked[k] = q

                if minus:
                    locked[k] = int(locked[k]) - 1
                if plus:
                    locked[k] = int(locked[k]) + 1

                if locked[k] < 0:
                    locked[k] = 0
                if locked[k] > max_avail:
                    locked[k] = max_avail

                st.session_state.locked_retrait_1000 = locked
                st.rerun()

# 4) FERMETURE (après retrait)
st.divider()
st.header("4) FERMETURE — Contenu final de la boîte")

if diff < 0:
    close_counts = after_in  # aucun retrait
else:
    close_counts = sub_counts(after_in, retrait_counts)

total_close = total_cents(close_counts)
st.success("TOTAL FERMETURE : " + cents_to_str(total_close))

if total_close != TARGET:
    st.warning("⚠️ La boîte n’est pas exactement à 1000,00 $. Ajuste le retrait / types autorisés.")
else:
    st.success("✅ La boîte est revenue exactement à 1000,00 $.")

st.divider()

# 5) Rapport imprimable
st.header("5) Rapport imprimable")

colA, colB = st.columns([1, 1])
with colA:
    gen = st.button("GÉNÉRER LE RAPPORT")
with colB:
    clear = st.button("EFFACER LE RAPPORT")

if clear:
    st.session_state.show_report_1000 = False
    st.session_state.report_payload_1000 = None

if gen:
    rows = rows_report(open_counts, depot_counts, retrait_counts if diff >= 0 else {k: 0 for k in DENOMS}, close_counts)
    meta = "Généré le " + datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.report_payload_1000 = {"rows": rows, "meta": meta}
    st.session_state.show_report_1000 = True

if st.session_state.show_report_1000 and st.session_state.report_payload_1000:
    html = build_print_html(st.session_state.report_payload_1000["rows"], st.session_state.report_payload_1000["meta"])
    components.html(html, height=560, scrolling=True)
